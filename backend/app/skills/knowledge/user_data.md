# USER KNOWLEDGE BASE

> Rules for using this file: every fact below is confirmed by the candidate unless marked **(estimate)**.
> Estimates were never tracked formally by the employer — do NOT put them in resumes, LinkedIn or cover letters; use them only in interview prep, always explained as estimates.
> Current consulting clients are under NDA: never name them or hint at them beyond "large Brazilian corporate groups", and never name the sector of the modeling work beyond "infrastructure".
> The candidate was never a partner or owner of MPB Engineering — never write "partner", "co-founder" or "owner" for it.

## 1. Positioning — two markets
Engineer (sanitary & environmental) and former CFO, 15+ years in infrastructure engineering and corporate finance, now also building data, modeling and AI systems. Based in Florianópolis, Brazil (UTC−3). No EU citizenship; needs visa sponsorship for relocation. Open to: remote now with immigration later, immediate relocation with sponsorship, or remote only.

**Brazil (write in Portuguese):** lead with Engineering and Sanitation, then technical-financial Modeling, Finance and Data/AI. Targets: sanitation and infrastructure engineering, concessions and PPPs, technical-financial modeling, utilities, engineering consultancies, infrastructure funds and development banks. Headline: "Engenheiro Sanitarista e Ambiental | Modelagem Técnico-Financeira, Dados e IA | Saneamento, Concessões e Infraestrutura | ex-Diretor Financeiro". Master CV: config/resume_pt.md.

**Abroad — US and Europe (write in English):** lead with Data, Finance and Modeling; AI as the way of building; engineering and sanitation only as domain background (except for infrastructure/energy project-finance roles, where the engineering record is the differentiator). Targets: financial modeling, data science and analytics, FP&A and finance automation, AI for finance, fintech, infrastructure/energy finance and advisory. Headline: "Data, Financial Modeling & AI | Forecasting, Valuation & Analytics | ex-CFO · 15+ yrs Infrastructure Finance". Master CV: config/resume_en.md.

## 2. Core Competencies
*   **AI & LLM:** AI agents, tool calling, MCP, prompt engineering, guardrails and prompt-injection defense, human-in-the-loop, knowledge bases, multi-provider routing (OpenRouter, Gemini, Claude, NVIDIA NIM, Ollama), TimesFM forecasting, n8n.
*   **Software:** Python (FastAPI, Flask, psycopg), TypeScript (Next.js, React, React Native), PostgreSQL (PL/pgSQL, RLS, pgTAP, pgmq), Supabase, Docker, GitHub Actions, Coolify/Traefik.
*   **Finance:** DCF feasibility studies, CAPEX/OPEX, tariff modeling, annual budgeting, KPI design, cost accounting/allocation, proposal pricing, Power BI.
*   **Engineering & management:** water, wastewater, drainage and solid waste; municipal sanitation plans; QCBS/LCS public procurement; project management; ERP, SharePoint, Power Platform; BIM; ISO 9001.

## 3. Professional Experience

### Applied AI Engineer — Self-employed
*Feb 2026 – Present*
*   **CentralOps** (Sep 2026 – Present): AI-native retail ERP + omnichannel platform for a fashion-retail business, built solo with Claude Code. Next.js 16/TypeScript, async Python workers (pgmq), PostgreSQL/Supabase. ~95k hand-written lines (excluding ~10k generated types), 133 migrations, 2,000+ pgTAP tests, CI/CD with manually approved production migrations, 8 ADRs. POS, inventory ledger, double-entry accounting with allocation at settlement, cash flow, P&L, HR/payroll, Brazilian tax (Simples/DAS, eSocial, NF-e/NFC-e).
*   CentralOps agent: MCP server with 16 tools; acts only via `agent.call_tool` under a no-table-access DB role; organization/customer/conversation come from a signed 10-minute JWT context token revalidated in the DB; prices, stock and totals computed in the DB; guardrail validator checks numbers against tool results of the same run; autopilot only for whitelisted intents with confidence ≥ 0.75; every tool call logged.
*   CentralOps staff assistant ("Central"): tool loop on the server with the user's own JWT (RLS), voice, camera (barcode, payment slip, Pix, invoice) and PDF/photo reading; writes only through confirmation cards.
*   **Trading Copilot** (Oct 2026 – Present): Python/Flask, B3 market. Analyst-signal monitor, order tickets, MetaTrader 5 execution with confirmation, broker-statement parser reconciling executions, real P&L with costs and slippage, monthly capital-gains tax (IRPF/DARF), backtests, screeners, TimesFM forecasts, live quotes via SSE. ~18k lines, 100+ tests.
*   **Mr Irrelevant** (Sep 2026 – Present): multi-tenant WhatsApp agent for fantasy-football leagues (Hermes Agent + Evolution API + Sleeper API). Tool with 40 queries, per-league isolation (persona, secrets, sessions, cron, knowledge base), LLM fallback chain ending in deterministic text, cron editorial, charts, live alerts. ~28k lines, 300+ tests including end-to-end.
*   **Election-night projection model** (inside Mr Irrelevant, Sep–Oct 2026): league/eleicao_modelo.py, eleicao_backtest.py, eleicao_tse.py. Projects the 2026 presidential runoff during the count from official TSE data, no AI: per-municipality expected share from 1st round + vote-transfer prior; deviation modeled in log-odds with Gaussian priors (national, region, state effects, leftover-vote and size covariates, municipal effect) solved in closed form (regularized weighted least squares) → hierarchical shrinkage; UF residual so national totals match TSE exactly; turnout scaling; analytic uncertainty with a misspecification floor calibrated by backtests of the 2014/2018/2022 runoffs replayed zone by zone in real arrival order (TSE open data read via HTTP Range, ~6 MB instead of ~1.4 GB); P(win)=Φ((S−½)/sd). Live feed: TSE results CDN, Ed25519 JWS signature verification, ETag polling within rate limits, governors/senators/SC deputies (seat allocation by party-list rules cross-checked with TSE), charts, WhatsApp delivery. ~2.6k lines, 56 tests. Do not claim accuracy numbers until backtest results are confirmed.
*   **CareerOps** (Feb 2026 – Jun 2026): FastAPI + React/TS + Chrome extension (MV3), PostgreSQL JSONB, Jinja2 prompt skills, Gemini/NVIDIA NIM/Ollama, MarkItDown, Gotenberg PDFs, human-in-the-loop validation.
*   **Public Tender Radar** (Feb 2026 – Mar 2026): Flask + Firebase Genkit + Gemini classifying tenders from the PNCP API.
*   **JãoBolão** (2026): Next.js 15, React Native/Expo, Supabase, Stripe, RevenueCat, WhatsApp bot.
*   Homelab: Docker, Coolify, Traefik, nginx, self-hosted Supabase, Vaultwarden, Evolution API, backups.

### Independent Consultant — Infrastructure Engineering & Project Finance
*Feb 2026 – Present*
*   Advises large Brazilian corporate groups (names under NDA) on major infrastructure projects.
*   General coordination of sanitation engineering projects.
*   Engineering-financial modeling for infrastructure projects.

### MPB Engineering — Finance Director (CFO)
*Feb 2023 – Jan 2026 (tenure at MPB: May 2008 – Jan 2026, nearly 18 years)*
*   Led a 5-person finance team.
*   Implemented the annual budget with monthly monitoring.
*   Defined and implemented KPIs to monitor operational goals.
*   BI management reports: department performance, major expenses (cost reduction), project performance.
*   New ERP with database migration, cost centers and labor-cost allocation from employee timesheets.
*   AI-powered automation with n8n and LLM APIs; Power Apps/Power Automate integrated with ERP and SharePoint.

### MPB Engineering — Engineer / Commercial Analyst / Project Manager
*Aug 2011 – Jan 2023*
*   Managed 5–7 concurrent consulting contracts, ~R$20M a year in total (~US$4M at ~R$5.4/US$). Typical contract: R$1–2M for engineering/advisory on infrastructure investments of R$100–800M (~US$20–150M).
*   Lagoas do Norte Program, Teresina (PI), World Bank–financed, client: Prefeitura de Teresina (SEMPLAN), Feb 2014 – Jul 2019: coordinated the proposal; general coordinator and technical lead (ARTs 08446548-8 and complements) for sewerage (312,560 inhabitants), drainage (28.2 km), water supply, roads, biogas (1,000 kW), urban design modeled in BIM, and social-environmental-economic program; ~1,300 ha.
*   CREA-SC technical record (CAT 252026185269, issued 24 Aug 2026): 46 ARTs in the candidate's own name (CREA-SC 108928-7). Highlights: Mearim basin plan, SECID-MA (2013–2018, 99,010 km², hydrological modeling, coordination); CASAN regional water system Xanxerê/Xaxim/Cordilheira Alta/Chapecó (2012–2013, 1,252 L/s, 57.8 km mains, 9,500 m³ reservoirs, project coordination); SANEPAR Guaratuba/Matinhos/Morretes (2018–2020, 148 km network, 600 L/s intake); SAMAE Brusque intake (2018–2020, 400 L/s, coordination); DNIT BR-470 duplication, environmental supervision then sector coordinator (2013–2023, 73 km); DEINFRA SC-477/SC-112, environmental management coordinator (2014–2017, 72.6 km); Autopista Litoral Sul, Florianópolis Beltway fauna-monitoring program (2018–2023); FUNASA water systems for 4 quilombola communities (2018–2022); CASAN Rio do Sul water-loss reduction (2023–2024); Governador Celso Ramos master-plan revision (2020–2024).
*   Never mix with the father's record (Eng. Paulo José Aragão, CREA 017445-1).
*   Spreadsheet 'Acervo_Tecnico_MPB_Aragao.xlsx', sheet 02 (40 certificates, Paulo Jr only) adds: Proactiva Meio Ambiente sanitary landfill ECA + basic design, 86 ha, 2014–2017; concession analyses Penha (2014–15), Camboriú (2015–16), Bombinhas (2015–16), Pomerode PMI + PMSB review (2014–15); CASAN Criciúma water system (2014–16, 311,696 → 431,187 people, 549 km network); 14 CASAN treatment projects (2013–15); Poços de Caldas ETA V (900 L/s, 2019–23); CAJ Joinville ETE Jardim Paraíso (50,230 people) and ETE Espinheiros; SAMAE Brusque ETA Cristalina (400 L/s, 12,600 m³ reservoirs); Mafra sewer system (247 km, 216 L/s plant); Bacanga basin drainage plan (234,123 people); Arteris fauna monitoring along the whole concession (356.6 km, 23 municipalities, 2020–22) and Florianópolis Beltway environmental construction program (2016–20); Concórdia flood-control dam (2020–22); SC-108/SC-465 highway designs (2017–22); Três Barras water/sewer O&M (2024); Imaruí design-build-operate water system (2022–24); Balneário Camboriú water/sewer diagnosis for Instituto +BC (2023–24). Each row has links to the individual CAT, company certificate and full folder.
*   DCF feasibility studies for full municipal water and wastewater concessions (tariff, CAPEX/OPEX, tax, regulation, demand, efficiency), for public and private clients.
*   Municipal sanitation plans (water, sewage, urban drainage, solid waste): diagnosis, prognosis, investment programs, service targets.
*   CAPEX/OPEX alternatives analysis for engineering solutions.
*   Financial proposals in QCBS and LCS processes; the firm bids on ~90 proposals a year. Created a pricing methodology based on objective metrics (project type, size, risk) that significantly reduced bid-preparation time and labor.
*   Project management in environmental, water, wastewater and hydraulics/hydrology: scope, schedule, specs, budget, risk, reports with clients and sub-consultants.
*   SharePoint 2010 → Online migration with in-house staff only; Power Apps/Power Automate; SharePoint–ERP integration.
*   ISO 9001 procedures (document naming/versioning, folders, backups, commercial/admin tasks).
*   BIM adoption: consultants, training, procedures, best-practice manuals, standard BEP, family library, hardware and licenses.

### MPB Engineering — Engineering Intern
*May 2008 – Aug 2011*
*   Financial proposals, sewage and wastewater-treatment design, alternatives analysis, cost estimates, technical reports.

### P.F. Chang's — Back Waiter (J-1 Work & Travel)
*Dec 2007 – Mar 2008, Fort Lauderdale, FL*
*   Busser and food runner during college vacation; found the job independently; improved English. Not for the CV — mention only as "lived and worked in the US".

## 4. Achievements and estimates
*   Pricing methodology: significantly reduced bid-preparation time and labor (confirmed, not measured). Bid win rate +18% **(estimate)**.
*   Automation (n8n, Power Platform): ~120 manual hours/month saved **(estimate)**; ~30% faster bid preparation **(estimate)**.
*   BIM adoption: ~25% shorter project delivery **(estimate)**.

## 5. STAR Cases

### Pricing Methodology Optimization
*   **Situation:** The firm bid on about 90 proposals a year (QCBS/LCS) with inconsistent, labor-intensive pricing.
*   **Task:** Create an objective, faster way to price proposals.
*   **Action:** Designed a pricing model based on objective metrics (project type, size, historical labor allocation, risk factors), integrating data from similar finished projects.
*   **Result:** Significantly reduced bid-preparation time and labor; win rate rose by an estimated ~18% (not formally tracked — explain the estimate).

### Budget, KPIs and Cost Accounting as CFO
*   **Situation:** The firm had no annual budget or KPI tracking, and labor costs were not allocated by project.
*   **Task:** Give the partners financial visibility by department and project.
*   **Action:** Implemented the annual budget with monthly monitoring, defined operational KPIs, redesigned cost centers and timesheet-based labor allocation in the new ERP, and built BI management reports.
*   **Result:** Monthly view of department and project performance and of major expenses for cost reduction.

### Digital Transformation and Process Automation
*   **Situation:** Fragmented legacy systems (SharePoint 2010, old ERP) caused manual re-entry of data.
*   **Task:** Modernize internal systems with the existing team.
*   **Action:** Led the SharePoint Online migration with in-house staff only, built Power Apps/Power Automate tools, integrated SharePoint with the ERP, and later added n8n + LLM automations.
*   **Result:** Eliminated manual data entry between systems; ~120 hours/month saved (estimate).

### BIM Methodology Implementation
*   **Situation:** The design department needed to modernize to stay competitive.
*   **Task:** Coordinate full BIM adoption.
*   **Action:** Hired consultants and training, reviewed procedures, wrote best-practice manuals and the standard BEP, managed the family library, hardware and licenses.
*   **Result:** Design department moved to BIM-based delivery (estimated ~25% shorter delivery).

### Making an LLM Agent Safe to Touch Money (CentralOps)
*   **Situation:** A customer-service agent on WhatsApp/Instagram could reserve items, create orders and send payment links; customer text is untrusted input (prompt injection).
*   **Task:** Let the agent act without being able to leak other customers' data or invent prices or discounts.
*   **Action:** Agent acts only through an MCP server calling one DB function under a role with no table access; context comes from a signed short-lived JWT revalidated in the DB and model-supplied IDs are discarded; prices and totals computed in the DB; a guardrail validator checks every number against that run's tool results; autopilot only for whitelisted intents above 0.75 confidence; all tool calls logged; human takeover at any time.
*   **Result:** A malicious prompt cannot reach another customer's data or values the database did not compute; swapping the model provider does not change the guarantees.

### Rebuilding a Prototype into a Tested Product (CentralOps)
*   **Situation:** The first version was a Python/JSON prototype that could not grow into an ERP.
*   **Task:** Rebuild it as a maintainable product as a solo developer.
*   **Action:** Made PostgreSQL the system of record and message bus (transactional SQL functions, outbox/pgmq), documented 8 ADRs, wrote pgTAP tests for RLS, ledger, inventory, HR and fiscal rules, and set up CI/CD with gated production migrations, using Claude Code for implementation.
*   **Result:** ~95k hand-written lines, 133 migrations and 2,000+ database tests in about five weeks (162 commits since 22 Sep 2026).

## 6. Education
*   **B.Eng., Sanitary & Environmental Engineering** | Federal University of Santa Catarina (UFSC) | Aug 2011
*   **MBA in Business Management** (executive postgraduate program) | Fundação Getulio Vargas (FGV) | Nov 2015
*   **MBA in Building Information Modeling** (postgraduate program) | Universidade Paulista (UNIP) | Dec 2021

## 7. Languages
Portuguese (native) · English (fluent, C1) · Spanish (intermediate, B1)
