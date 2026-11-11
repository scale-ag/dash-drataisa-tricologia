#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a dashboard estatica (index.html) de Captacao de Leads "Dra. Taisa (Tricologia)"
a partir de DUAS planilhas do Google Sheets (somente leitura):

  - "MedClinic | Captcao Pages | Todos", aba "Tricologia - Pages" (gid 0): fonte
    PRINCIPAL de leads — cada linha e um cadastro feito na LANDING PAGE de
    tricologia (lp-tricologia-v1..v5), com as UTMs do anuncio
    (utm_source=Facebook-Ads · utm_medium={{adset.name}} · utm_campaign={{campaign.name}}
     · utm_content={{ad.name}} · utm_term={{placement}}).
  - "Queries - Dra Taisa", aba "Queries Meta | Dra Taisa" (gid 0): investimento,
    impressoes, alcance, cliques no link e Landing Page Views do gerenciador
    (Meta Ads), uma linha por dia x campanha x conjunto x anuncio.

TESTES DE UTM: os cadastros ate o ultimo teste (10/11/2026 08:27:33 UTC — antiga
linha 15 da planilha) sao testes de UTM/formulario — o build IGNORA tudo com
"dia/horario" <= LEADS_START_UTC (decisao do gestor). O corte e por DATA/HORA, nao
por numero de linha: as linhas de teste podem ser apagadas/reordenadas sem quebrar.

LEAD VALIDO — ver lead_discard_reason():
  1. "dia/horario" preenchido e DEPOIS de LEADS_START_UTC;
  2. nome e telefone preenchidos (a LP nao coleta e-mail obrigatorio);
  3. nao e cadastro de teste (nome "Teste ...", pagina de teste/debug,
     URL local file://, utm_source de teste).

ORIGEM: lead de MIDIA PAGA (src="meta") quando o utm_source e do Meta
(Facebook/Instagram) ou a utm_campaign casa com uma campanha da aba de Queries.
Sem UTM = "Organico / sem UTM" (src="org"): entra na Visao Geral (total de leads
da LP) mas NAO entra na aba Meta Ads (que so olha midia paga).

O casamento com o Meta Ads e por nome, normalizado (sem acento, minusculo,
espacos colapsados, %XX/+ decodificados):
    utm_campaign == Campaign Name · utm_medium == Ad Set Name · utm_content == Ad Name
Quando casa, o lead recebe o nome CANONICO do gerenciador (para somar na mesma
linha das tabelas).

FUNIL DESTA CONTA (landing page):
    Gasto -> Impressoes -> Alcance -> Cliques -> Page Views -> Leads
com CPM · Frequencia (Impr./Alcance) · CTR · CPC · CR (Page Views/Cliques) ·
CPV (Gasto/Page Views) · ConvLP (Leads/Page Views) · CPL.
A coluna "Leads" da aba de Queries (contagem do proprio Meta) NAO e usada: a
fonte de verdade dos leads e a planilha da LP.

Este script apenas LE as planilhas (export CSV publico) e emite os REGISTROS
BRUTOS (leads[] e meta[]) dentro do HTML. Todos os filtros, agregacoes, KPIs,
tabelas e graficos sao calculados no navegador (client-side). Nunca escreve
nada de volta.

Teste local: --leads-file / --meta-file apontando para CSVs baixados.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

# Planilha de Leads ("MedClinic | Captção Pages | Todos"), aba "Tricologia - Pages".
SPREADSHEET_ID_LEADS = "1POUa1YFL4HnuWCt8ib3I4EYOQSBCQZWBSfasLRvQhHY"
GID_LEADS = "0"
# Planilha "Queries - Dra Taisa", aba "Queries Meta | Dra Taisa" — mídia paga.
SPREADSHEET_ID_META = "1tBBVOSEOBeHrkHDPBMVB6W1Ot5zAN4E96m_GmzW9ojs"
GID_META = "0"
EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"

# Testes de UTM: tudo até o último teste ("mariana", 2026-11-10T08:27:33.726Z — era a
# linha 15 da planilha) é descartado. Corte por DATA/HORA (UTC), não por nº de linha,
# porque as linhas de teste foram apagadas e o 1º lead real "subiu" para a linha 3.
LEADS_START_UTC = datetime(2026, 11, 10, 8, 27, 34, tzinfo=timezone.utc)

# Identificação do cliente/conta (usada só em textos/relatórios — não afeta o cruzamento de dados).
CLIENT_NAME = "Dra. Taísa"
MAIN_PRODUCT = "Tricologia"
# Sigla comum às campanhas da conta:
#   DTS | E2-CAP | P2-FRIO | LEAD | ABO | 2026-11-10 | Teste de Ads LPV4
#   ^^^ sigla (DTS = "Dra. Taísa Santana") — só informativa nesta dash.
MAIN_PRODUCT_PREFIX = "DTS"

# --------------------------------------------------------------------------- #
# Fusos horarios — "dia/horario" do lead vem em ISO UTC (ex.: 2026-11-10T08:27:33.726Z)
# e o "Day" do Meta Ads ja vem fechado no fuso da conta. O dia do lead e convertido
# para ACCOUNT_TZ antes de virar data.
LEADS_TZ_NAME = "America/Sao_Paulo"    # fuso assumido quando o horario vier SEM offset
ACCOUNT_TZ_NAME = "America/Sao_Paulo"  # fuso da conta de anuncios (dia de referencia da dash)
try:                                    # tzdata do sistema (runner do Actions tem)
    from zoneinfo import ZoneInfo
    LEADS_TZ = ZoneInfo(LEADS_TZ_NAME)
    ACCOUNT_TZ = ZoneInfo(ACCOUNT_TZ_NAME)
except Exception:                       # sem tz database: offset fixo equivalente
    LEADS_TZ = timezone(timedelta(hours=-3))
    ACCOUNT_TZ = timezone(timedelta(hours=-3))

BRT = timezone(timedelta(hours=-3))   # horario de Brasilia (so p/ o carimbo "ultima atualizacao")
TAX_FACTOR = 1.13806   # fator de imposto/taxa sobre o gasto de mídia paga (Meta Ads) = 13,806%.
                       # O toggle "Imposto Meta" ja vem LIGADO (app.js STATE.tax=true): gasto e
                       # derivados (CPM, CPC, CPV, CPL) saem com o imposto. Desligar mostra o gasto bruto.

# --------------------------------------------------------------------------- #
# Regras da aba Insights de IA (Top Anúncios)
# --------------------------------------------------------------------------- #
# Amostra mínima para JULGAR um anúncio (Escalar/Manter/Cortar). Abaixo disso ele
# fica "Observar" — nunca é classificado só porque teve 1 lead com pouco gasto.
SAMPLE_MIN_SPEND = 100.0   # gasto mínimo (R$, sem imposto) para amostra relevante
SAMPLE_MIN_LEADS = 3       # leads mínimos para julgar o anúncio
TOP_ADS_N = 10             # nº de linhas de referência dos rankings

# Metas & parâmetros da conta (DEFAULTS do painel editável da aba Insights de IA).
# São só o valor inicial: o gestor edita no navegador (localStorage) e a tabela
# de anúncios recolore o CPL e reavalia o Status ao vivo. None = "não definida".
META_CPL = None            # meta de CPL (R$/lead); None = não definida
VOLUME_MIN_AMOSTRAL = SAMPLE_MIN_LEADS  # leads mínimos p/ amostra confiável
N_DIAS_CORTE = 5           # dias consecutivos acima do teto p/ considerar corte


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #
FETCH_RETRIES = 3       # tentativas totais em caso de timeout/erro de rede no export CSV
FETCH_RETRY_DELAY = 15  # segundos entre tentativas (o Google Sheets às vezes trava a resposta)


def fetch_csv(url: str) -> list[list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "dash-drataisa-tricologia-bot/1.0"})
    last_err: Exception | None = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return list(csv.reader(io.StringIO(raw)))
        except (TimeoutError, urllib.error.URLError) as exc:
            last_err = exc
            if attempt < FETCH_RETRIES:
                print(f"[fetch_csv] tentativa {attempt}/{FETCH_RETRIES} falhou ({exc!r}); "
                      f"tentando de novo em {FETCH_RETRY_DELAY}s...", file=sys.stderr)
                time.sleep(FETCH_RETRY_DELAY)
    raise last_err


def read_csv_file(path: str) -> list[list[str]]:
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        return list(csv.reader(f))


def load_rows(url: str, local: str | None) -> list[list[str]]:
    return read_csv_file(local) if local else fetch_csv(url)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str | None) -> str:
    return strip_accents((s or "").strip().lower())


def to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v).strip())
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(v: str) -> str | None:
    """Dia SEM conversao de fuso — usado no "Day" do Meta Ads, que ja vem fechado
    no fuso da conta. Para os leads use parse_lead_date()."""
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    s = s.split()[0]          # "08/09/2026 15:15" -> "08/09/2026"
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def lead_datetime(v: str) -> datetime | None:
    """"dia/horario" do lead como datetime COM fuso (None se vazio/ilegível).

    Vem em ISO UTC, ex.: "2026-11-10T15:57:42.339Z"; com offset também serve.
    Sem offset (ou dd/mm/aaaa hh:mm), assume LEADS_TZ."""
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    if s.endswith("Z") or s.endswith("z"):      # "2026-11-10T08:27:33.726Z" (UTC)
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=LEADS_TZ)
    except ValueError:
        pass
    s2 = re.sub(r"\s+", " ", s)
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s2, fmt).replace(tzinfo=LEADS_TZ)
        except ValueError:
            continue
    return None


def parse_lead_date(v: str) -> str | None:
    """Dia do lead ("YYYY-MM-DD") no fuso da conta de anuncios (ACCOUNT_TZ)."""
    dt = lead_datetime(v)
    return dt.astimezone(ACCOUNT_TZ).strftime("%Y-%m-%d") if dt else None


# --------------------------------------------------------------------------- #
# Regra de LEAD VÁLIDO
# --------------------------------------------------------------------------- #
# Cadastro de teste: nome cuja 1ª palavra é "teste"/"test" (ex.: "Teste Diagnostico"),
# e-mail de domínio de teste, página de teste/debug, URL local (file://) ou
# utm_source de teste ("meta_test", "teste7"...). Nunca bate em nome real que só
# contenha essas letras no meio (ex.: "Celeste").
_TEST_WORD_RE = re.compile(r"^(teste|test)\d*$")
_TEST_ANY_RE = re.compile(r"(^|[^a-z])(teste?|debug)")
_TEST_EMAIL_DOMAINS = ("teste.com", "test.com", "example.com", "meta.com")


def is_test_lead(name: str, email: str, pagina: str = "", url: str = "", utm_source: str = "") -> bool:
    first = (norm(name).split() or [""])[0]
    if _TEST_WORD_RE.match(first):
        return True
    e = norm(email)
    if "@" in e:
        local, _, domain = e.partition("@")
        if domain in _TEST_EMAIL_DOMAINS or _TEST_WORD_RE.match(local):
            return True
    if _TEST_ANY_RE.search(norm(pagina)) or _TEST_ANY_RE.search(norm(utm_source)):
        return True
    if norm(url).startswith("file:"):
        return True
    return False


def lead_discard_reason(created: datetime | None, name: str, email: str, phone: str,
                        pagina: str, url: str, utm_source: str) -> str | None:
    """None = lead válido. Senão, o motivo do descarte (para o log do build)."""
    if created is None:
        return "sem_data"
    if created <= LEADS_START_UTC:
        return "testes_utm"
    if not (name.strip() and phone.strip()):
        return "incompleto"
    if is_test_lead(name, email, pagina, url, utm_source):
        return "teste"
    return None


def first_last_initial(name: str) -> str:
    parts = (name or "").strip().split()
    if not parts:
        return "—"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][:1]}."


def mask_email(e: str) -> str:
    e = (e or "").strip()
    if "@" not in e:
        return "—"
    user, dom = e.split("@", 1)
    keep = user[:2] if len(user) > 2 else user[:1]
    return f"{keep}****@{dom}"


def mask_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    return f"…{digits[-4:]}" if len(digits) >= 4 else "—"


# --------------------------------------------------------------------------- #
# UTMs -> origem / plataforma / posicionamento
# --------------------------------------------------------------------------- #
ORG_LABEL = "Orgânico / sem UTM"
_META_SOURCES = ("facebook", "instagram", "meta", "fb", "ig")


def clean_utm(v: str) -> str:
    """Valor de UTM utilizável: decodifica %XX, descarta macro não substituída
    ({{adset.name}} — clique fora do anúncio/preview) e valores vazios."""
    s = (v or "").strip()
    try:
        s = urllib.parse.unquote_plus(s)   # a LP grava espaço como "+" (AUTO+|+H+|+...)
    except Exception:
        pass
    s = s.strip()
    if not s or "{{" in s or "}}" in s:
        return ""
    return s


def mkey(s: str) -> str:
    """Chave de casamento leads x Meta: sem acento, minúsculo, '+' = espaço,
    espaços colapsados (o nome do conjunto tem espaço duplo: 'BAURU |  AD04')."""
    s = clean_utm(s).replace("+", " ")
    return re.sub(r"\s+", " ", norm(s)).strip()


_META_SOURCE_RE = re.compile(r"facebook|instagram|meta|^fb([^a-z]|$)|^ig([^a-z]|$)")


def is_meta_source(src: str) -> bool:
    """utm_source de mídia paga do Meta (Facebook-Ads, facebook, ig, instagram...)."""
    return bool(_META_SOURCE_RE.search(norm(clean_utm(src))))


def pretty_platform(placement: str, source: str, paid: bool) -> str:
    """Plataforma pelo utm_term ({{placement}}: Instagram_Feed, Facebook_Mobile_Feed...)."""
    if not paid:
        return ORG_LABEL
    p = norm(placement)
    for keys, label in ((("instagram", "ig_"), "Instagram"), (("facebook", "fb_"), "Facebook"),
                        (("messenger",), "Messenger"), (("threads",), "Threads"),
                        (("audience", "an_"), "Audience Network")):
        if any(p.startswith(k) or k in p for k in keys):
            return label
    s = norm(source)
    if "instagram" in s or s == "ig":
        return "Instagram"
    return "Não informado"


def pretty_placement(placement: str, paid: bool) -> str:
    if not paid:
        return ORG_LABEL
    s = clean_utm(placement)
    if not s:
        return "Não informado"
    s = re.sub(r"\s+", " ", s.replace("_", " ")).strip()
    return s[:1].upper() + s[1:]


def pretty_page(v: str) -> str:
    s = (v or "").strip()
    return s or "Não informado"


# --------------------------------------------------------------------------- #
# Indexacao das colunas
# --------------------------------------------------------------------------- #
def header_index(header, wanted, fallback):
    """1º passe: nome exato (normalizado); 2º passe: cabeçalho que CONTÉM o alias."""
    idx = {}
    hn = [norm(h) for h in header]
    for key, aliases in wanted.items():
        found = None
        for a in aliases:
            a = norm(a)
            for i, h in enumerate(hn):
                if h == a:
                    found = i
                    break
            if found is not None:
                break
        if found is None:
            for a in aliases:
                a = norm(a)
                for i, h in enumerate(hn):
                    if a and a in h:
                        found = i
                        break
                if found is not None:
                    break
        idx[key] = found if found is not None else fallback.get(key)
    return idx


def cell(row, i):
    if i is None or i < 0 or i >= len(row):
        return ""
    return (row[i] or "").strip()


# --------------------------------------------------------------------------- #
# Processamento -> registros brutos
# --------------------------------------------------------------------------- #
def process(leads_rows, meta_rows):
    # ---- Meta Ads (Queries Meta | Dra Taisa) ----
    mheader = meta_rows[0] if meta_rows else []
    midx = header_index(
        mheader,
        {"day": ["day", "data"], "campaign": ["campaign name", "campaign"],
         "adset": ["ad set name", "adset name", "adset"], "ad": ["ad name"],
         "spent": ["amount spent", "valor gasto", "gasto"], "impr": ["impressions", "impressoes"],
         "clicks": ["link clicks", "cliques no link"], "reach": ["reach", "alcance"],
         "pv": ["landing page views", "visualizacoes da pagina de destino"]},
        {"day": 0, "campaign": 1, "adset": 2, "ad": 3, "spent": 4, "impr": 5, "reach": 6,
         "clicks": 7, "pv": 9},
    )
    print(f"  [meta] colunas mapeadas: {midx}", file=sys.stderr)

    meta = []
    # chaves normalizadas -> nome canônico do gerenciador (para o lead somar na mesma linha)
    camp_canon: dict[str, str] = {}
    adset_canon: dict[tuple[str, str], str] = {}
    ad_canon: dict[tuple[str, str, str], str] = {}
    ad_by_camp: dict[tuple[str, str], set] = {}
    for row in meta_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        day = parse_date(cell(row, midx["day"]))
        camp = cell(row, midx["campaign"])
        if not day and not camp:
            continue
        adset = cell(row, midx["adset"]) or "(sem conjunto)"
        ad = cell(row, midx["ad"]) or "(sem anúncio)"
        camp = camp or "(sem campanha)"
        kc, ka, kd = mkey(camp), mkey(adset), mkey(ad)
        camp_canon.setdefault(kc, camp)
        adset_canon.setdefault((kc, ka), adset)
        ad_canon.setdefault((kc, ka, kd), ad)
        ad_by_camp.setdefault((kc, kd), set()).add((adset, ad))
        meta.append({
            "d": day,
            "camp": camp,
            "adset": adset,
            "ad": ad,
            "sp": round(to_float(cell(row, midx["spent"])), 4),
            "im": to_float(cell(row, midx["impr"])),
            "cl": to_float(cell(row, midx["clicks"])),
            "rc": to_float(cell(row, midx["reach"])),
            "pv": to_float(cell(row, midx["pv"])),
        })

    # ---- Leads (landing page) ----
    lheader = leads_rows[0] if leads_rows else []
    lidx = header_index(
        lheader,
        {"created": ["dia/horario", "data/hora", "created_time", "timestamp"],
         "name": ["nome", "full_name"], "email": ["email", "e-mail"],
         "phone": ["telefone", "phone_number", "whatsapp"], "page": ["pagina", "page"],
         "source": ["utm_source"], "medium": ["utm_medium"], "campaign": ["utm_campaign"],
         "content": ["utm_content"], "term": ["utm_term"], "url": ["url"]},
        {"name": 0, "email": 1, "phone": 2, "page": 3, "source": 4, "medium": 5, "campaign": 6,
         "content": 7, "term": 8, "url": 9, "created": 10},
    )
    print(f"  [leads] colunas mapeadas: {lidx}", file=sys.stderr)

    leads = []
    descartados = {"testes_utm": 0, "sem_data": 0, "incompleto": 0, "teste": 0}
    sem_meta = 0
    organicos = 0
    for row in leads_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        name = cell(row, lidx["name"])
        email = cell(row, lidx["email"])
        phone = cell(row, lidx["phone"])
        page = cell(row, lidx["page"])
        url = cell(row, lidx["url"])
        source = cell(row, lidx["source"])
        created = lead_datetime(cell(row, lidx["created"]))
        why = lead_discard_reason(created, name, email, phone, page, url, source)
        if why:
            descartados[why] += 1
            continue

        u_camp = clean_utm(cell(row, lidx["campaign"]))
        u_adset = clean_utm(cell(row, lidx["medium"]))
        u_ad = clean_utm(cell(row, lidx["content"]))
        kc, ka, kd = mkey(u_camp), mkey(u_adset), mkey(u_ad)
        camp_ok = kc in camp_canon
        paid = camp_ok or (is_meta_source(source) and bool(u_camp))
        if paid:
            camp = camp_canon.get(kc, u_camp)
            adset = adset_canon.get((kc, ka)) or u_adset or "(sem conjunto)"
            ad = ad_canon.get((kc, ka, kd))
            if ad is None and camp_ok:
                # conjunto não casou (nome mudou/UTM cortada): anúncio único na campanha
                cands = ad_by_camp.get((kc, kd)) or set()
                if len(cands) == 1:
                    adset, ad = next(iter(cands))
            trk = 1 if ad is not None else 0
            ad = ad or u_ad or "(sem anúncio)"
            sem_meta += 1 - trk
        else:
            camp = adset = ad = ORG_LABEL
            trk = 0
            organicos += 1
        placement = cell(row, lidx["term"])
        leads.append({
            "d": created.astimezone(ACCOUNT_TZ).strftime("%Y-%m-%d"),
            # "meta" = mídia paga (UTM do Meta) · "org" = orgânico / sem UTM
            "src": "meta" if paid else "org",
            "plat": pretty_platform(placement, source, paid),
            "pos": pretty_placement(placement, paid),
            "lp": pretty_page(page),
            "camp": camp,
            "adset": adset,
            "ad": ad,
            # 1 = o anúncio (campanha+conjunto+anúncio) existe na aba de Queries
            # (tem gasto/impressões rastreados); 0 = lead sem mídia correspondente.
            "trk": trk,
            "nm": first_last_initial(name),
            "em": mask_email(email),
            "ph": mask_phone(phone),
        })

    dates = sorted({d for d in ([l["d"] for l in leads if l["d"]] + [m["d"] for m in meta if m["d"]])})
    now_brt = datetime.now(BRT)              # carimbo "ultima atualizacao" (hora local do gestor)
    hoje_conta = datetime.now(ACCOUNT_TZ)    # "hoje" do funil = dia no fuso da conta de anuncios
    return {
        "build": {
            "generated_at_brt": now_brt.strftime("%d/%m/%Y %H:%M"),
            "build_id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "today": hoje_conta.strftime("%Y-%m-%d"),
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "tax_factor": TAX_FACTOR,
            "account_tz": ACCOUNT_TZ_NAME,
            "client_name": CLIENT_NAME,
            "main_product": MAIN_PRODUCT,
            # config da aba Insights de IA (lida pelo front)
            "sample_min_spend": SAMPLE_MIN_SPEND,
            "sample_min_leads": SAMPLE_MIN_LEADS,
            "top_ads_n": TOP_ADS_N,
            # metas & parâmetros (defaults do painel editável; None = não definida)
            "meta_cpl": META_CPL,
            "volume_min_amostral": VOLUME_MIN_AMOSTRAL,
            "n_dias_corte": N_DIAS_CORTE,
            # diagnóstico (log do build)
            "leads_descartados": descartados,
            "leads_sem_meta": sem_meta,
            "leads_organicos": organicos,
        },
        "leads": leads,
        "meta": meta,
        # Insights de Tráfego (texto pré-escrito, lido de relatorios.json). Preenchido
        # em main() via load_briefings(); fica {} se relatorios.json não existir.
        "briefings": {},
    }


# --------------------------------------------------------------------------- #
# Insights de Tráfego (aba Insights de IA)
# --------------------------------------------------------------------------- #
def load_briefings(path: str) -> dict:
    """Lê build/relatorios.json. Estrutura:
        {"generated_at": "...", "periodos": {"<preset>": {...}, ...}}
    Retorna o dict inteiro (ou {} se o arquivo não existir/for inválido).
    A geração NÃO acontece aqui — este build só lê o texto já pronto, sem
    chamar nenhuma API (custo zero no build/no navegador)."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (ValueError, OSError):
        return {}


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(data, template_path):
    # A dashboard e montada a partir de arquivos separados (visual x logica):
    #   template.html          -> esqueleto HTML (placeholders __STYLES__/__APP_JS__)
    #   identidade-visual.css  -> TODAS as cores (edite aqui p/ mexer so em cor)
    #   estilos.css            -> layout/componentes
    #   app.js                 -> logica + renderizacao
    # Esta funcao so COSTURA os arquivos e injeta os dados; nao altera nada deles.
    base = os.path.dirname(os.path.abspath(template_path))

    def readf(name):
        with open(os.path.join(base, name), "r", encoding="utf-8") as f:
            return f.read()

    with open(template_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    styles = readf("identidade-visual.css") + "\n" + readf("estilos.css")
    # "</" dentro do JSON fecharia o <script> do payload antes da hora
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    tpl = tpl.replace("__STYLES__", styles)
    tpl = tpl.replace("__APP_JS__", readf("app.js"))
    tpl = tpl.replace("__DATA_JSON__", payload)
    tpl = tpl.replace("__BUILD_ID__", data["build"]["build_id"])
    tpl = tpl.replace("__GENERATED_BRT__", data["build"]["generated_at_brt"])
    return tpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads-file", help="CSV local da aba 'Tricologia - Pages' (leads da LP)")
    ap.add_argument("--meta-file", help="CSV local da aba 'Queries Meta | Dra Taisa' (Meta Ads)")
    ap.add_argument("--template", default="build/template.html")
    ap.add_argument("--out", default="dist/index.html")
    args = ap.parse_args()

    leads_rows = load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID_LEADS, gid=GID_LEADS), args.leads_file)
    meta_rows = load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID_META, gid=GID_META), args.meta_file)

    data = process(leads_rows, meta_rows)

    # Insights de Tráfego (texto pré-escrito) — lidos do arquivo versionado ao
    # lado do template. Sem chamada de API no build.
    briefings_path = os.path.join(os.path.dirname(os.path.abspath(args.template)), "relatorios.json")
    data["briefings"] = load_briefings(briefings_path)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(data, args.template))

    b = data["build"]
    d = b["leads_descartados"]
    sp = sum(m["sp"] for m in data["meta"])
    pv = sum(m["pv"] for m in data["meta"])
    print("== build ok ==", file=sys.stderr)
    print(f"  periodo    : {b['date_min']} -> {b['date_max']} (hoje {b['today']})", file=sys.stderr)
    print(f"  leads      : {len(data['leads'])} válidos "
          f"({len(data['leads']) - b['leads_organicos']} mídia paga · {b['leads_organicos']} orgânicos/sem UTM)",
          file=sys.stderr)
    print(f"  descartados: {d['testes_utm']} testes de UTM (até {LEADS_START_UTC:%d/%m/%Y %H:%M} UTC) · "
          f"{d['sem_data']} sem dia/horário · {d['incompleto']} incompletos · {d['teste']} de teste",
          file=sys.stderr)
    print(f"  sem mídia  : {b['leads_sem_meta']} lead(s) pago(s) cujo anúncio não aparece na aba de Queries",
          file=sys.stderr)
    print(f"  meta       : {len(data['meta'])} linhas · gasto R$ {sp:,.2f} "
          f"(sem imposto; fator {TAX_FACTOR}) · {pv:,.0f} page views", file=sys.stderr)
    print(f"  out        : {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
