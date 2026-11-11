# AGENTS.md — Dash Captação de Leads · Dra.Taísa (Tricologia)

> Contexto completo em **`CLAUDE.md`** (mesma pasta) — leia-o antes de mexer no projeto.

## O essencial

- **Repo:** `scale-ag/dash-drataisa-tricologia` · **Pages:** https://scale-ag.github.io/dash-drataisa-tricologia/
- **Modelo:** cópia de `dash-giaco-sdc-form7` (Visão Geral · Meta Ads · Insights de IA), adaptada a landing page.
- **Fontes:** planilha de leads da LP (aba `Tricologia - Pages`) + aba `Queries Meta | Dra Taisa`, somente leitura. IDs/gids no topo de `build/build.py`.
- **Funil:** `Gasto → Impressões → Alcance → Cliques → Page Views → Leads` (CR, CPV, ConvLP). Termina no lead.
- **Lead válido:** `dia/horario` > `LEADS_START_UTC` (após os testes de UTM; corte por data, não por linha) **e** nome/telefone preenchidos **e** não é teste.
- **Origem:** UTM do Meta = mídia paga; sem UTM = orgânico (só na Visão Geral).
- **Casamento:** `utm_campaign`/`utm_medium`/`utm_content` = `Campaign/Ad Set/Ad Name` (normalizado).
- **Imposto:** `TAX_FACTOR=1.13806`; toggle "Imposto Meta" ligado por padrão.
- **Build:** `python build/build.py --leads-file leads.csv --meta-file queries.csv --out dist/index.html`.

## Onde mexer

| Quero mudar… | Arquivo |
|---|---|
| IDs/gids das planilhas, corte dos testes (`LEADS_START_UTC`), regra de lead válido, imposto, fuso | `build/build.py` |
| Só as cores (tema claro/escuro) | `build/identidade-visual.css` |
| Layout/componentes | `build/estilos.css` |
| KPIs, funil, tabelas, gráficos, filtro cruzado | `build/app.js` |
| Título, logo, textos fixos da página | `build/template.html` |
| Publicação | `.github/workflows/deploy.yml` · `SETUP-CRON.md` |
