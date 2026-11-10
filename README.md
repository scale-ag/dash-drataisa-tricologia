# Dashboard de Captação de Leads · Dra.Taísa (Tricologia)

Dashboard **100% na nuvem** do funil de **Tricologia** da **Dra. Taísa**, cruzando a
mídia paga (Meta Ads) com os leads cadastrados nas **landing pages** de tricologia
(`lp-tricologia-v1` … `v5`). Mesmo modelo/abas da `dash-giaco-sdc-form7`
(Visão Geral · Meta Ads · Insights de IA), adaptado a **funil de landing page**.
Build estático (HTML/CSS/JS puro + Chart.js via CDN) publicado no **GitHub Pages**
e reconstruído a cada ~30 min pelo GitHub Actions (disparado pelo cron-job.org).

**URL pública:** https://scale-ag.github.io/dash-drataisa-tricologia/

Somente leitura das planilhas. O build **nunca** escreve de volta.

---

## O que a dash mostra

Funil: **Gasto → Impressões → Alcance → Cliques → Page Views → Leads**, com CPM,
Frequência, CTR, CPC, **CR** (Connect Rate = Page Views ÷ Cliques), **CPV**
(Gasto ÷ Page Views), **ConvLP** (Leads ÷ Page Views) e CPL. Três páginas:

1. **Visão Geral** — funil + evolução diária (Leads × Gasto × CPL) + tabela
   diária com heatmap, 8 KPIs secundários e 4 distribuições (conjunto, página/LP,
   plataforma, posicionamento).
2. **Meta Ads** (só mídia paga) — mesmo funil + combinação diária, indicadores por
   dia (CPM/CTR · Connect Rate/ConvLP · CPL/Frequência), leads por anúncio, donut
   de conversão da LP, compilado de anúncios por CPL, as 3 tabelas hierárquicas
   (Campanha → Conjunto → Anúncio) com gráfico de CPL por dia e filtro cruzado
   bidirecional, e a lista de leads do período (mascarada).
3. **Insights de IA** — espelha a Visão Geral + painel editável de metas (Meta
   CPL, volume mínimo, N dias p/ corte) + **Top Anúncios** com status
   Escalar/Manter/Observar/Cortar + bloco "Insights de Tráfego" (vazio até a
   Routine do Claude ser criada — ver `CLAUDE.md`).

### Regra de LEAD VÁLIDO (`build/build.py` → `lead_discard_reason`)
1. linha da planilha **≥ 16** (`LEADS_FIRST_ROW`) — as linhas 2–15 são testes de UTM;
2. **nome** e **telefone** preenchidos;
3. não é teste (nome "Teste …", página `teste`/`debug`, URL `file://`, utm_source de teste).

**Origem:** lead de **mídia paga** quando o `utm_source` é do Meta (Facebook-Ads…)
ou a `utm_campaign` casa com uma campanha da aba de Queries; sem UTM = **Orgânico /
sem UTM**. A Visão Geral considera todos os leads válidos; a aba Meta Ads só os pagos.

O build imprime no log quantos leads foram descartados e por quê.

### Imposto da mídia paga
`TAX_FACTOR = 1.13806` (13,806%) aplicado **somente** ao gasto do Meta Ads. O
toggle "Imposto Meta" **já vem ligado**; desligá-lo mostra o gasto bruto.

## Fontes de dados (Google Sheets, somente leitura)

| Planilha | ID | Aba (gid) | Colunas usadas |
|---|---|---|---|
| Leads — `MedClinic \| Captção Pages \| Todos`, aba `Tricologia - Pages` | `1POUa1YFL4HnuWCt8ib3I4EYOQSBCQZWBSfasLRvQhHY` | `0` | `Nome` · `Email` · `Telefone` · `Pagina` · `Utm_source` · `Utm_medium` · `Utm_campaign` · `Utm_content` · `Utm_term` · `Url` · `dia/horario` |
| Meta Ads — `Queries - Dra Taisa`, aba `Queries Meta \| Dra Taisa` | `1tBBVOSEOBeHrkHDPBMVB6W1Ot5zAN4E96m_GmzW9ojs` | `0` | `Day` · `Campaign Name` · `Ad Set Name` · `Ad Name` · `Amount Spent` · `Impressions` · `Reach` · `Link Clicks` · `Landing Page Views` |

Casamento pelas UTMs (normalizado: sem acento, minúsculo, espaços colapsados, `%XX` decodificado):
`utm_campaign` = `Campaign Name` · `utm_medium` = `Ad Set Name` · `utm_content` = `Ad Name`.
`utm_term` (`{{placement}}`) vira Plataforma/Posicionamento.

URL de export CSV: `https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>`

## Rodar/testar local

```bash
python build/build.py --leads-file leads.csv --meta-file queries.csv --out dist/index.html
```

Sem `--leads-file`/`--meta-file` o script busca os CSVs públicos direto do Google Sheets.

## Automação

- `.github/workflows/deploy.yml` — roda `build/build.py` e publica no Pages.
  Dispara por `workflow_dispatch` (cron-job.org a cada 30 min), `schedule` de
  backup e `push` na `main`.
- `.github/workflows/briefing.yml` — coleta os números dos Insights. Agendamento
  **desligado** até existir a Routine do Claude que escreve os textos.

Valores exatos para o cron-job.org: **`SETUP-CRON.md`**.
