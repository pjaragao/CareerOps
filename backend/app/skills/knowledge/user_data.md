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
*   **Data & BI:** Power BI end to end (data modeling, star schema, DAX, R, reporting); SQL; Python (Pandas, NumPy). Coding history: VBA since the sanitary-engineering years (hydraulic modeling, pump curves, standardized reports generated with the calculations); Python and SQL self-taught from 2018.
*   **IT infrastructure (since 2016, MPB):** Active Directory, 30+ TB file server, company-wide Microsoft 365 (200+ employees), VPN between offices, 2 redundant servers, UPS, backups, 3 internet links with failover, SharePoint Online migration (2018).
*   **Finance:** DCF feasibility studies, CAPEX/OPEX, tariff modeling, annual budgeting, KPI design, cost accounting/allocation, proposal pricing, Power BI.
*   **Engineering & management:** water, wastewater and drainage; municipal sanitation plans; QCBS/LCS public procurement; project management; ERP, SharePoint, Power Platform; BIM; ISO 9001.

## 3. Professional Experience

### Applied AI Engineer — Self-employed
*Feb 2026 – Present*
*   **CentralOps** (Sep 2026 – Present): AI-native retail ERP + omnichannel platform for a fashion-retail business, built solo with Claude Code. Next.js 16/TypeScript, async Python workers (pgmq), PostgreSQL/Supabase. ~95k hand-written lines (excluding ~10k generated types), 133 migrations, 2,000+ pgTAP tests, CI/CD with manually approved production migrations, 8 ADRs. POS, inventory ledger, double-entry accounting with allocation at settlement, cash flow, P&L, HR/payroll, Brazilian tax (Simples/DAS, eSocial, NF-e/NFC-e).
*   CentralOps agent: MCP server with 16 tools; acts only via `agent.call_tool` under a no-table-access DB role; organization/customer/conversation come from a signed 10-minute JWT context token revalidated in the DB; prices, stock and totals computed in the DB; guardrail validator checks numbers against tool results of the same run; autopilot only for whitelisted intents with confidence ≥ 0.75; every tool call logged.
*   CentralOps staff assistant ("Central"): tool loop on the server with the user's own JWT (RLS), voice, camera (barcode, payment slip, Pix, invoice) and PDF/photo reading; writes only through confirmation cards.
*   **Trading Copilot** (Oct 2026 – Present): Python/Flask, B3 market. Analyst-signal monitor, order tickets, MetaTrader 5 execution with confirmation, broker-statement parser reconciling executions, real P&L with costs and slippage, monthly capital-gains tax (IRPF/DARF), backtests, screeners, TimesFM forecasts, live quotes via SSE. ~18k lines, 100+ tests.
*   **Mr Irrelevant** (Sep 2026 – Present): multi-tenant WhatsApp agent for fantasy-football leagues (Hermes Agent + Evolution API + Sleeper API). Tool with 40 queries, per-league isolation (persona, secrets, sessions, cron, knowledge base), LLM fallback chain ending in deterministic text, cron editorial, charts, live alerts. ~28k lines, 300+ tests including end-to-end.
*   **Election-night projection model** (inside Mr Irrelevant, Sep–Oct 2026): league/eleicao_modelo.py, eleicao_backtest.py, eleicao_tse.py. Projects the 2026 presidential runoff during the count from official TSE data, no AI: per-municipality expected share from 1st round + vote-transfer prior; deviation modeled in log-odds with Gaussian priors (national, region, state effects, leftover-vote and size covariates, municipal effect) solved in closed form (regularized weighted least squares) → hierarchical shrinkage; UF residual so national totals match TSE exactly; turnout scaling; analytic uncertainty with a misspecification floor calibrated by backtests of the 2014/2018/2022 runoffs replayed zone by zone in real arrival order (TSE open data read via HTTP Range, ~6 MB instead of ~1.4 GB); P(win)=Φ((S−½)/sd). Live feed: TSE results CDN, Ed25519 JWS signature verification, ETag polling within rate limits, governors/senators/SC deputies (seat allocation by party-list rules cross-checked with TSE), charts, WhatsApp delivery. ~2.6k lines, 56 tests. Confirmed backtest (2014/2018/2022 runoffs, n=90 checkpoints): from 5% of votes counted, mean error of the national share 0.28 pp; 90% intervals covered the result 84% of the time; never confident and wrong (0 cases of P(win) ≥ 95% for the eventual loser). Use only these numbers.
*   **CareerOps** (Feb 2026 – Jun 2026): FastAPI + React/TS + Chrome extension (MV3), PostgreSQL JSONB, Jinja2 prompt skills, Gemini/NVIDIA NIM/Ollama, MarkItDown, Gotenberg PDFs, human-in-the-loop validation.
*   **Public Tender Radar** (Feb 2026 – Mar 2026): Flask + Firebase Genkit + Gemini classifying tenders from the PNCP API.
*   **JãoBolão** (2026): Next.js 15, React Native/Expo, Supabase, Stripe, RevenueCat, WhatsApp bot.
*   Platform: Docker, Coolify (GitOps deploys), Traefik, nginx, Supabase/PostgreSQL, Vaultwarden, Evolution API, Tailscale, daily backups. Never call it "self-hosted" or "homelab" in resumes, LinkedIn or cover letters — describe it as "my own Docker/Coolify production platform" or just "in production".

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
*   **AI accounts payable (enterprise, in production):** payables used to arrive by email, Teams and WhatsApp and were typed in by hand. Centralized intake (3 channels → 1) in a folder read through the Microsoft 365 API; n8n flow converts PDF/Office with Docling (images go to a multimodal model as fallback); an LLM classifies against a closed list of the active cost centers and chart of accounts pulled from the ERP (it cannot invent a value); a person reviews 100% of entries in a queue; approved payables are posted through the Sienge ERP API. Monthly feedback loop: confirmed classifications go back into the prompt as examples. No accuracy or time-saved numbers were tracked — do not invent them.
*   **Timesheet and labor-cost allocation system (enterprise, in production):** Power Apps canvas app inside Microsoft Teams where staff log % of time per project; entries stored in a SQL database; two-level approval (staff log, directors approve or send back); approved hours merged with payroll and allocated to redesigned Sienge cost centers; feeds the annual budget, project margin and KPI dashboards. First real labor cost per project at the firm. Diagnosis first: the gap was a missing process, not a missing report.

### MPB Engineering — Engineer / Commercial Analyst / Project Manager
*Aug 2011 – Jan 2023*
*   Managed 5–7 concurrent consulting contracts, ~R$20M a year in total (~US$4M at ~R$5.4/US$). Typical contract: R$1–2M for engineering/advisory on infrastructure investments of R$100–800M (~US$20–150M).
*   Lagoas do Norte Program, Teresina (PI), World Bank–financed, client: Prefeitura de Teresina (SEMPLAN), Feb 2014 – Jul 2019: coordinated the proposal; general coordinator and technical lead (ARTs 08446548-8 and complements) for sewerage (312,560 inhabitants), drainage (28.2 km), water supply, roads, biogas (1,000 kW), urban design modeled in BIM, and social-environmental-economic program; ~1,300 ha.
*   CREA-SC technical record (CAT 252026185269, issued 24 Aug 2026): 46 ARTs in the candidate's own name (CREA-SC 108928-7). Highlights: Mearim basin plan, SECID-MA (2013–2018, 99,010 km², hydrological modeling, coordination); CASAN regional water system Xanxerê/Xaxim/Cordilheira Alta/Chapecó (2012–2013, 1,252 L/s, 57.8 km mains, 9,500 m³ reservoirs, project coordination); SANEPAR Guaratuba/Matinhos/Morretes (2018–2020, 148 km network, 600 L/s intake); SAMAE Brusque intake (2018–2020, 400 L/s, coordination); DNIT BR-470 duplication, environmental supervision then sector coordinator (2013–2023, 73 km); DEINFRA SC-477/SC-112, environmental management coordinator (2014–2017, 72.6 km); Autopista Litoral Sul, Florianópolis Beltway fauna-monitoring program (2018–2023); FUNASA water systems for 4 quilombola communities (2018–2022); CASAN Rio do Sul water-loss reduction (2023–2024); Governador Celso Ramos master-plan revision (2020–2024).
*   Never mix with the father's record (Eng. Paulo José Aragão, CREA 017445-1).
*   Spreadsheet 'Acervo_Tecnico_MPB_Aragao.xlsx', sheet 02 (40 certificates, Paulo Jr only) adds: concession analyses Penha (2014–15), Camboriú (2015–16), Bombinhas (2015–16), Pomerode PMI + PMSB review (2014–15); CASAN Criciúma water system (2014–16, 311,696 → 431,187 people, 549 km network); 14 CASAN treatment projects (2013–15); Poços de Caldas ETA V (900 L/s, 2019–23); CAJ Joinville ETE Jardim Paraíso (50,230 people) and ETE Espinheiros; SAMAE Brusque ETA Cristalina (400 L/s, 12,600 m³ reservoirs); Mafra sewer system (247 km, 216 L/s plant); Bacanga basin drainage plan (234,123 people); Arteris fauna monitoring along the whole concession (356.6 km, 23 municipalities, 2020–22) and Florianópolis Beltway environmental construction program (2016–20); Concórdia flood-control dam (2020–22); SC-108/SC-465 highway designs (2017–22); Três Barras water/sewer O&M (2024); Imaruí design-build-operate water system (2022–24); Balneário Camboriú water/sewer diagnosis for Instituto +BC (2023–24). Each row has links to the individual CAT, company certificate and full folder.
*   DCF feasibility studies for full municipal water and wastewater concessions (tariff, CAPEX/OPEX, tax, regulation, demand, efficiency), for public and private clients.
*   Municipal sanitation plans (water, sewage, urban drainage): diagnosis, prognosis, investment programs, service targets.
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

### Enterprise AI Accounts Payable (MPB, n8n + Microsoft 365 + Sienge)
*   **Situation:** Payables arrived through email, Teams and WhatsApp; finance typed every document into the ERP and picked the cost center by hand.
*   **Task:** Automate intake and classification without letting a model write unchecked data into the ERP.
*   **Action:** Centralized intake in one Microsoft 365 folder read via API; n8n flow with Docling conversion and multimodal fallback; LLM restricted to a closed list of active cost centers and accounts from the ERP; human review queue for 100% of entries; posting through the Sienge API; monthly feedback loop feeding confirmed examples back into the prompt.
*   **Result:** One intake channel instead of three; the team moved from typing to reviewing; no invalid cost center can reach the ERP by design. (No numeric gains were tracked — do not quote any.)

### Timesheet and Labor-Cost Allocation (MPB, Power Apps + SQL)
*   **Situation:** Labor, the firm's largest cost, was not allocated to projects, so contract margins were unknown.
*   **Task:** Create the process and the tool to cost labor by project.
*   **Action:** Power Apps canvas app inside Teams, SQL database, director approval flow, merge with payroll and allocation to redesigned Sienge cost centers.
*   **Result:** First real labor cost per project; feeds the annual budget and KPI dashboards.

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

> Each case below is tagged **Proves:** with the competencies it demonstrates, so interview prep can pick the right story for the question (evals, observability, failure recovery, deterministic guardrails, enterprise delivery, modeling, domain adaptability). Only the facts written here may be quoted.

### Evals That Gate Model Changes (CentralOps)
*   **Proves:** automated evaluation suites, observability, cost control, safe model switching.
*   **Situation:** The ERP's AI features (customer chat, copilot, classification, extraction, vision) ran on several providers, and changing a model risked silent regressions in what the agent promised customers.
*   **Task:** Make model choice a measured, reversible decision instead of a guess.
*   **Action:** Per-task model routes in a database table (`ai.model_routes`), each with backup models and a daily USD cap, switchable in the UI without a deploy; every call written to `ai.runs` with tokens, cost, latency and status; an eval suite that runs cases in a sandbox with rollback and scores approval, unfounded promises, correct handoff, latency and cost; the ranking gates any model change.
*   **Result:** Models are swapped by evidence, with full per-call cost and latency history; an exhausted budget or failing route hands off to a human instead of degrading silently.

### Post-Generation Validator and Autonomy Gate (CentralOps)
*   **Proves:** deterministic guardrails, brand/compliance safety, human-in-the-loop by policy.
*   **Situation:** Customer-facing replies could quote prices, installments and stock, offer discounts or make health claims — any of which can create liability.
*   **Task:** Guarantee that no reply goes out with a number or claim the system did not produce.
*   **Action:** Rules settle opt-outs, requests for a human, legal topics and formal complaints before any model call; a validator ships a reply only if every price, installment and stock figure came from that run's tool results, and blocks discounts, ID/card numbers and health claims; on failure one retry with the reason, then a draft or a human; auto-send only for allowed intents, minimum confidence, no flags, non-VIP customers, inside Meta's 24 h window and under hourly limits.
*   **Result:** Autonomy is a policy decided in code, not by the model. **Domain bridge:** the same pattern is what brand governance needs in a content pipeline — banned claims, approved values only, and a human gate for anything off-policy.

### Graceful Degradation Across the Agents (Mr Irrelevant, Lolo, CareerOps)
*   **Proves:** failure recovery, resilience, operating unattended in production.
*   **Situation:** Unattended agents depend on LLM providers, Google APIs and a changing LinkedIn UI; any of them fails at some point.
*   **Task:** Make each failure visible and recoverable, never a silent wrong action.
*   **Action:** Mr Irrelevant: primary and backup providers read from one config and tried in order, explicit max_tokens and timeouts per task, a JSON cache so a retry never re-calls the model, and if no model answers the original deterministic text is published. Lolo: when Google is disconnected, tasks queue locally instead of being lost. CareerOps: the browser extension acts first, what it cannot finish goes to a Claude Code routine, what is left reaches the user with the question or the screen; a miss raises an error_code with a screenshot.
*   **Result:** 41,000+ scheduled runs (Mr Irrelevant) and 22,000+ (Lolo) operating unattended; a provider outage degrades to deterministic text or a queue instead of an error, and CareerOps failures surface with a screenshot instead of a wrong click.

### Idempotent Financial Writes from a Chat Agent (Siê Joy Bot)
*   **Proves:** data integrity, deterministic guardrails, agent acting on an ERP.
*   **Situation:** In a partners' WhatsApp group, brainstorming, quotes and actual payments are mixed in the same chat, and message retries happen.
*   **Task:** Book reimbursements in the ERP from chat without duplicates or entries for things that were never paid.
*   **Action:** Ideas go to a pending list and become entries only on an unambiguous payment message; reimbursement items get deterministic ids (UUID v5) so retries never duplicate; writes go to CentralOps through RPC with edit and cancel; the bot answers only when mentioned or replied to.
*   **Result:** 11 reimbursements booked from 850 messages, with no duplicate possible by construction.

### Auditable Brokerage-Note Import (Trading Copilot)
*   **Proves:** reconciliation, financial controls, reversible operations.
*   **Situation:** Real trading costs, slippage and capital-gains tax depend on brokerage-note PDFs that must match the executions.
*   **Task:** Import notes without corrupting the position and tax history.
*   **Action:** Each import shows a preview reconciled against the executions, runs in one transaction per note, and has an undo that restores the previous state; risk, payoff and discipline are computed by rules and statistics, with no language model.
*   **Result:** 10 notes reconciled with fee allocation and monthly tax slips; any import can be reverted.

### Calibrated Election-Night Forecast (Election Bot)
*   **Proves:** statistical modeling, evaluation by backtest, honest uncertainty, live operation.
*   **Situation:** Early in a Brazilian count the raw share is biased by arrival order (South and Center-West count fast, Northeast slowly).
*   **Task:** Project the final runoff result during the count, with uncertainty people can trust.
*   **Action:** Per-municipality expectation from the 1st round plus vote transfer; hierarchical log-odds deviation (national → region → state) solved in closed form; residual per state so totals match the TSE exactly; uncertainty floor calibrated by replaying the 2014, 2018 and 2022 runoffs zone by zone in real arrival order; features that helped one year and hurt another were switched off; every TSE file's signature verified.
*   **Result:** Backtest: 0.28 pp mean error from 5% counted, 90% band held the result at 84% of points, never more than 95% for the eventual loser. 2026 real night: right favourite from 0.04% counted, ≥ 90% from 31% and ≥ 99.5% from 46% — while the raw count still showed the other candidate ahead.

### Signed Per-Job Links and Privacy-First Analytics (CareerOps + portfolio)
*   **Proves:** security by design, minimal attack surface, measuring outcomes.
*   **Situation:** Each application should carry its own portfolio link to see which companies actually open it, without exposing the CareerOps backend.
*   **Task:** Track views per job with no shared secret list and nothing inbound to the private platform.
*   **Action:** HMAC-signed tokens per job verified statelessly at the edge; events stored in private blob storage; CareerOps pulls and acknowledges them every 5 minutes (outbound only); the job-specific CV PDF is served only to that job's link; view counts surface on the job board and in the WhatsApp summary.
*   **Result:** Per-company engagement data on every application with zero exposed ports.

### Company-Wide ERP Rollout (MPB, Sienge)
*   **Proves:** enterprise delivery, change management, process before technology.
*   **Situation:** A 200+ employee consultancy ran on fragmented legacy systems.
*   **Task:** Lead the company's second ERP implementation (2023) as Finance Director.
*   **Action:** Started with finance, then extended it to every department with process mapping and staff training; redesigned cost centers.
*   **Result:** The ERP became the base for the budget, KPIs, timesheet costing and the AI accounts-payable pipeline.

### Coordinating a World Bank–Financed Urban Program (Lagoas do Norte, Teresina)
*   **Proves:** large-scale program delivery, multidisciplinary leadership, multilateral standards.
*   **Situation:** Teresina's (PI) Lagoas do Norte Program combined sewerage, drainage, water, roads, biogas and urban design over ~1,300 ha, financed by the World Bank.
*   **Task:** Win and then lead the engineering work for the municipality (SEMPLAN).
*   **Action:** Coordinated the proposal; served as general coordinator and technical lead (Feb 2014 – Jul 2019) for sewerage for 312,560 inhabitants, 28.2 km of drainage, water supply, roads, a 1,000 kW biogas plant, BIM-modeled urban design and the social-environmental-economic program.
*   **Result:** Led the engineering coordination of the whole contract for over five years, across all disciplines, as the single point of contact for the municipality.

### Keeping the Company's IT Running (MPB)
*   **Proves:** reliability engineering, operations, high availability.
*   **Situation:** A multi-office consultancy depended on file servers (30+ TB), the ERP and SharePoint every day.
*   **Task:** Keep systems available and data safe with a small in-house team.
*   **Action:** Redundant servers and UPS, failover internet links, backups, multi-office VPN, Active Directory and Microsoft 365 administration; SharePoint 2010 → Online migration with in-house staff only.
*   **Result:** The same operating discipline now applied to AI systems: backups with checksums and daily off-site copies, no exposed admin ports.

## 6. Education
*   **B.Eng., Sanitary & Environmental Engineering** | Federal University of Santa Catarina (UFSC) | Aug 2011
*   **MBA in Business Management** (executive postgraduate program) | Fundação Getulio Vargas (FGV) | Nov 2015
*   **MBA in Building Information Modeling** (postgraduate program) | Universidade Paulista (UNIP) | Dec 2021

## 7. Languages
Portuguese (native) · English (fluent, C1) · Spanish (intermediate, B1)
