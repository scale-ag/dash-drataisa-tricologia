# CLAUDE.md — Dashboard Dra.Taísa (Tricologia)

> Lido automaticamente pelo Claude Code ao abrir o repositório. Mantenha atualizado.
> Repositório: `scale-ag/dash-drataisa-tricologia` · Pages: `https://scale-ag.github.io/dash-drataisa-tricologia/`

## Configuração do cliente

- **Cliente:** Dra. Taísa (sigla das campanhas **DTS**) · **Funil:** Tricologia · captação por **landing page**
  (`lp-tricologia-v1` … `v5`, domínio `tricologia-vN.taisasantana.com.br`).
- **Modelo:** cópia de `scale-ag/dash-giaco-sdc-form7` (**Visão Geral · Meta Ads · Insights de IA** —
  ids internos `geral`/`meta`/`rel`), adaptada a **funil de landing page** (Page Views/CR/CPV/ConvLP).
- **Leads:** planilha `1POUa1YFL4HnuWCt8ib3I4EYOQSBCQZWBSfasLRvQhHY`, aba `Tricologia - Pages`, gid `0`.
  **Testes de UTM:** tudo com `dia/horario` ≤ `LEADS_START_UTC` (2026-11-10 08:27:34 UTC, logo após o último
  teste — a antiga linha 15) é descartado. O corte é por **data/hora**, NÃO por nº de linha: as linhas de
  teste foram apagadas em 11/11 e o 1º lead real "subiu" para a linha 3 (a regra antiga `linha ≥ 16` o descartava).
- **Meta Ads:** planilha `1tBBVOSEOBeHrkHDPBMVB6W1Ot5zAN4E96m_GmzW9ojs`, aba `Queries Meta | Dra Taisa`, gid `0`.
  (A aba `Google Queries`, gid `1609119011`, existe mas não é usada.)
- **Sem qualificação:** não há MQL, agendamentos, vendas, faturamento, CAC ou ROAS.
  O funil termina no **Lead**. Não introduzir sem pedido + fonte de dados.
- `TAX_FACTOR = 1.13806` (toggle "Imposto Meta" ligado por padrão).

---

## Funil (landing page)

`Gasto → Impressões → Alcance → Cliques → Page Views → Leads`, com
**CPM · Frequência (Impr. ÷ Alcance) · CTR · CPC · CR (Page Views ÷ Cliques) · CPV (Gasto ÷ Page Views) ·
ConvLP (Leads ÷ Page Views) · CPL**.

- **Page Views** = coluna `Landing Page Views` da aba de Queries.
- **Alcance** é a soma das linhas diárias por anúncio (o Meta não deduplica), então a
  Frequência é uma média aproximada.
- **CPL só existe com gasto > 0** (`derive()` em `app.js`, `derived()` em `relatorio_lib.py`).
- A coluna `Leads` da aba de Queries (contagem do Meta) **não** é usada — a fonte de
  verdade é a planilha da LP.

## Regra de LEAD VÁLIDO (`build.py` → `lead_discard_reason`)

1. `dia/horario` preenchido e **depois** de `LEADS_START_UTC` (senão: `sem_data` / `testes_utm`);
2. `Nome` e `Telefone` preenchidos (a LP não exige e-mail);
3. não é teste: 1ª palavra do nome `teste`/`test`, e-mail de domínio de teste,
   `Pagina`/`Utm_source` com `teste`/`test`/`debug`, `Url` começando com `file:`.

### Origem (mídia paga × orgânico)
- `src="meta"` quando `Utm_source` é do Meta (Facebook-Ads, facebook, ig…) **e** há
  `Utm_campaign`, ou quando a `Utm_campaign` casa com uma campanha da aba de Queries.
- Senão `src="org"` → campanha/conjunto/anúncio/plataforma = "Orgânico / sem UTM".
- **Visão Geral / Insights** usam TODOS os leads válidos (CPL geral); KPIs por anúncio
  e Top Anúncios usam só os pagos. **Meta Ads** usa só `src==='meta'` (`metaScope`).
- Macro não substituída (`{{adset.name}}` etc.) é tratada como UTM vazia.

### Casamento leads × Meta Ads
`Utm_campaign`/`Utm_medium`/`Utm_content` == `Campaign Name`/`Ad Set Name`/`Ad Name`,
comparados por `mkey()` (sem acento, minúsculo, `%XX`/`+` decodificados — a LP grava `AUTO+|+H+|+…` —, espaços
colapsados — o nome do conjunto tem espaço duplo, ex. `BAURU |  AD04`). Quando casa, o lead
recebe o nome **canônico** do gerenciador. `trk=1` quando a tripla existe na aba de Queries
(KPI "% Eficácia Rastr."). `Utm_term` (`{{placement}}`) → Plataforma e Posicionamento.

### Fuso horário
`dia/horario` vem em ISO UTC (`…Z`); `parse_lead_date()` converte para
`ACCOUNT_TZ` (America/Sao_Paulo) antes de pegar o dia. O `Day` do Meta entra como está.

## Arquitetura / arquivos

```
build/build.py            # lê os 2 CSVs (read-only), aplica a regra de lead válido, emite REGISTROS BRUTOS (leads[]/meta[]); render() costura os arquivos abaixo
build/template.html       # esqueleto HTML. Placeholders __STYLES__, __APP_JS__, __DATA_JSON__, __BUILD_ID__, __GENERATED_BRT__
build/identidade-visual.css  # TODAS as cores (tema claro/escuro)
build/estilos.css         # layout/componentes (sidebar, topbar, period-picker, funil, tabelas, gráficos, aba Insights)
build/app.js              # lógica + renderização (KPIs, funil, tabelas, filtro cruzado, period-picker, heatmap, Insights)
build/relatorios.json     # Insights de Tráfego por período — VERSIONADO; hoje {} (Routine não criada)
build/relatorios_dados.json      # números brutos por período (insumo da Routine) — não lido pelo site. Hoje {}.
build/relatorio_lib.py           # datas/agregação compartilhadas (usada por coletar_dados_relatorio.py)
build/coletar_dados_relatorio.py # gera relatorios_dados.json (só números) — roda no briefing.yml (agendamento DESLIGADO)
build/GUIA-RELATORIOS.md            # formato dos Insights (contexto/estrutura dos textos)
build/GUIA-INTERPRETACAO-METRICAS.md # regras de diagnóstico por métrica
.github/workflows/deploy.yml    # roda build.py e publica no Pages (workflow_dispatch + schedule + push)
.github/workflows/briefing.yml  # roda coletar_dados_relatorio.py (só workflow_dispatch por enquanto)
dist/index.html           # saída gerada (gitignored; o Actions reconstrói)
GUIA-REPLICACAO.md        # como replicar este modelo
SETUP-CRON.md             # valores exatos do cron-job.org
```

O `build.py` **não agrega**: exporta as linhas cruas e TODA a lógica (filtros de
data, filtro cruzado, KPIs, tabelas, gráficos, heatmap, imposto) roda no navegador.

## Especificação funcional

1. **Visão Geral** (`geral`) — funil vertical (Gasto → Impressões → Alcance → Cliques → Page Views → Leads);
   evolução diária (Leads barras · Gasto · CPL) + tabela diária com heatmap
   (`DAILY_COLS`: Data · Dia · Gasto · CPM · Freq. · CTR · CPC · CR · ConvLP · Leads · CPL);
   8 KPIs secundários; distribuição por conjunto · página (LP) · plataforma · posicionamento.
2. **Meta Ads** (`meta`, só mídia paga) — mesmo funil; combinação diária; indicadores por dia
   (CPM/CTR · Connect Rate/ConvLP · CPL/Frequência); leads por anúncio; donut de conversão da LP
   (Page Views → Leads); compilado de anúncios; 3 tabelas hierárquicas Campanha → Conjunto →
   Anúncio com gráfico de CPL por dia; lista de leads do período (mascarada).
3. **Insights de IA** (`rel`) — espelha a Visão Geral + painel de Metas + **Top Anúncios**
   (Escalar/Manter/Cortar/Observar) + Insights de Tráfego (lidos de `build/relatorios.json`).

**Regras obrigatórias das tabelas:** cabeçalho sticky; ordenação tri‑state; colunas
redimensionáveis (persist localStorage); linha "Total Geral" fixa; dimensão nunca
truncada; seleção com toggle + Ctrl multi; filtro cruzado bidirecional; tabela diária
com último dia no topo; heatmap de cor fixa por métrica.

`localStorage`: `dm_metas:<repo>` e `dm_colw:<repo>` (chave com o nome do repo, porque
`scale-ag.github.io` é a mesma origem para todas as dashs da conta); `dm_theme` é global.

## Briefing automático (Insights de IA) — INATIVO

`build/relatorios.json`/`build/relatorios_dados.json` estão `{}` e o `schedule` do
`briefing.yml` está comentado. Para ativar: (1) descomentar o `schedule`, (2) criar a
Routine do Claude que lê `build/relatorios_dados.json` + os 2 guias e escreve
`build/relatorios.json` na `main`.

## Rodar/testar local

```bash
python build/build.py --leads-file leads.csv --meta-file queries.csv --out dist/index.html
```

## Publicação — problemas conhecidos
1. **cron-job.org só funciona na `main`** (`workflow_dispatch` só existe na branch padrão).
2. **Pages** em modo "GitHub Actions".
3. **Token exposto:** se um token foi colado no chat, **revogar e gerar um novo**.
