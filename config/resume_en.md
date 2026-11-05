# PAULO JOSÉ ARAGÃO JR.

**Data, Financial Modeling & AI | Forecasting, Valuation & Analytics | Engineer & former CFO**

Florianópolis, Brazil (UTC−3) | Open to relocation to the EU or US (visa sponsorship required) and to remote roles
pjaragaojr@gmail.com | +55 00 00000-0000 | linkedin.com/in/paulojrarj | github.com/pjaragao

---

## PROFESSIONAL SUMMARY

Former CFO and engineer with 15+ years in infrastructure finance, now building data, modeling and AI systems end to end. I build the models people decide with — DCF feasibility and tariff models for utility concessions, pricing for ~90 tenders a year, budgets, KPIs and BI — and the software around them: statistical forecasting (a Bayesian election-night projection model calibrated on three past elections), financial systems with double-entry ledgers and 2,000+ automated tests, and LLM agents where every number comes from the database. Python, SQL and PostgreSQL every day, and 11 AI and data systems of my own running in production on a self-hosted Docker platform (48 containers, 88,000+ agent and scheduled runs). A background as a sanitary and environmental engineer — including general coordination of a World Bank–financed urban program — gives me real domain depth in infrastructure, utilities and project finance. I also led the company's IT infrastructure — redundant servers, failover internet links, backups and multi-office VPN — so I know how to keep systems, and the AI automations on top of them, running reliably and continuously in production.

---

## SKILLS

- **Modeling & analytics:** financial modeling, DCF and feasibility studies, concession and tariff modeling, valuation, forecasting (Bayesian hierarchical models, TimesFM), backtesting, budgeting and variance analysis, KPI design, cost accounting, pricing
- **Data & software:** Python, SQL, PostgreSQL (PL/pgSQL, pgTAP, Supabase, PGMQ queues), SQLite, Redis, FastAPI, async workers, data pipelines, Playwright browser automation, Power BI, Excel, REST APIs and webhooks, TypeScript/Next.js/React, GitHub Actions CI/CD
- **AI:** LLM applications and autonomous agents, tool calling, MCP servers, multi-agent systems and inter-agent calls, RAG, agent memory, guardrails and human-in-the-loop, prompt engineering and prompt chaining, multi-provider model routing (Claude, GPT-4o, Gemini, open models), LangChain, Pydantic AI, Hermes Agent, n8n AI workflows, AI-assisted development with Claude Code
- **DevOps & platform:** Docker and Docker Compose, Coolify (self-hosted PaaS, GitOps deploys), Tailscale zero-trust networking, Linux, scheduled jobs and monitoring
- **IT infrastructure:** Active Directory, Microsoft 365 tenant administration, SharePoint (on-premises and Online), Power Apps (canvas and model-driven), file server (30+ TB), backup, VPN, multi-office networking, high availability (redundant servers, UPS, failover internet links)
- **Domain:** infrastructure and utilities (water, wastewater, drainage), project finance, public procurement (QCBS/LCS), ERP, BIM

---

## PROFESSIONAL EXPERIENCE

### Data & AI Engineer — Self-employed
**Florianópolis, Brazil (remote)** | Feb 2026 – Present

Independent product work, team of one. Project types: platform builds, product launches, forecasting models, LLM agents.

Build and operate data, modeling and AI products end to end as sole engineer: 14 systems, 11 in production. Method: prototype integrations, prompt chains and agent tool calls in n8n to prove the flow and its edge cases, then harden them with Claude Code into production services (FastAPI, Next.js, Python workers, PL/pgSQL), with automated tests and CI as the quality gate.

- **Election-night projection model (Brazil 2026):** Bayesian hierarchical model of municipal deviations from a first-round + vote-transfer baseline on official electoral data (national → regional → state shrinkage); uncertainty calibrated by replaying the 2014, 2018 and 2022 runoffs in real vote-arrival order; 56 tests.
- **CentralOps — retail ERP with an AI agent.** ~95k-line system (PostgreSQL/Supabase, Python workers, Next.js/TypeScript): double-entry ledger, cash flow and P&L, inventory, payroll, Brazilian tax and e-invoicing; 133 migrations, 2,000+ pgTAP tests, CI/CD. Point of sale, e-commerce, Stone payments and NFC-e e-invoicing; 10 PostgreSQL schemas with PGMQ queues. The customer-facing LLM agent acts only through database functions exposed by an MCP server, and a guardrail checks every price and stock level against the database before a reply goes out; a second operations agent works the ERP through the same MCP server.
- **Trading Copilot (B3):** tracks analyst signals, reconciles broker statements for real costs and slippage, computes capital-gains tax and backtests strategies with TimesFM forecasts; 100+ tests.
- **CareerOps — career automation platform:** FastAPI, PostgreSQL and a Playwright/Chromium worker that finds and scores jobs with LLMs against this CV, tailors CVs (PDF via Gotenberg), and applies, connects and comments on LinkedIn only after human approval, with layered fallbacks when the site changes.
- **WhatsApp AI agents:** multi-tenant agent platform (300+ tests) running an executive assistant (94 commands, 58 skills, long-term memory; approves CareerOps actions from chat), a customer-service agent with persistent memory and an operations agent for an online store; Evolution API, SQLite and Redis.
- **Sports analytics:** Bayesian (MCMC) and TimesFM forecasting on NFL data for a fantasy league, with an automated editorial bot; open-source Sleeper API engine with an event-driven game watcher and RAG over its own documentation.
- **Public-tender intelligence:** classifier of Brazilian public tenders (PNCP) with Gemini and Firebase Genkit.
- **Platform:** all of it self-hosted on my own Docker/Coolify platform — 48 containers in 21 stacks behind Tailscale zero-trust networking, GitOps deploys, 88,000+ agent and scheduled runs.

### Independent Consultant — Infrastructure Project Finance & Modeling
**Florianópolis, Brazil** | Feb 2026 – Present

Independent practice serving large Brazilian corporate groups. Freelance, held concurrently with the data and AI work above.

- Advise large Brazilian corporate groups (under NDA) on major infrastructure projects: engineering-financial models (CAPEX/OPEX, cash flow, feasibility) for infrastructure projects and coordination of sanitation engineering projects.

### MPB Engineering — Florianópolis, Brazil
**Consultancy for water, wastewater, urban and highway-environmental infrastructure** | May 2008 – Jan 2026

Consultancy serving municipalities, state utilities and federal agencies, bidding ~90 tenders a year. Internal promotions from intern to Finance Director over nearly 18 years.

**Finance Director (CFO)** | Feb 2023 – Jan 2026
Project types: budgeting and KPI rollout, ERP migration, BI reporting, finance automation.
- Led a 5-person finance team; introduced the annual budget with monthly variance tracking and the KPIs used to monitor operational goals.
- Built BI reporting on department and project performance and major expenses; redesigned ERP cost accounting with timesheet-based labor allocation.
- Automated reporting and document workflows with n8n, LLM APIs and Power Platform integrated with the ERP and SharePoint, eliminating manual data entry.

**Senior Engineer — Feasibility Modeling, Proposals & Projects** | Aug 2011 – Jan 2023
Project types: feasibility and tariff modeling, concession analysis, tender pricing, World Bank–financed program delivery, ERP and BIM rollouts.
- Built DCF feasibility and tariff models for municipal water and wastewater concessions and analyzed concession processes for four municipalities.
- Prepared financial proposals for the firm's ~90 tenders a year (QCBS/LCS) and designed a metrics-based pricing method that significantly cut bid-preparation time.
- Managed 5–7 concurrent contracts (~US$4M a year) of US$0.2–0.4M each, supporting infrastructure investments of US$20–150M; owned scope, schedule, budget, risk and client reporting.
- General coordinator and engineer of record for the **World Bank–financed Lagoas do Norte Program** in Teresina (Feb 2014 – Jul 2019): proposal and integrated design of sewerage for 312,000 residents, 28 km of drainage, water, roads, a 1 MW biogas plant and BIM-modeled urban design across ~1,300 ha.
- Engineer of record on 46 registered engagements, including the Mearim river-basin plan (99,000 km², 2.1M people), water systems for state utilities (up to 1,250 L/s) and environmental management of highway programs (BR-470 for DNIT; Arteris concession, 357 km).
- Led the firm's ERP, SharePoint Online and BIM transformations with in-house staff.

**IT Infrastructure Lead**
Project types: multi-office on-premises infrastructure, high availability, cloud migration.
- Owned the firm's IT infrastructure, with several offices joined to the local network over VPN: Active Directory, Microsoft 365 tenant administration and the on-premises file server (30+ TB).
- Built for high availability and continuous operation: 2 redundant servers running in parallel, on-site UPS installed and maintained, local-server backup routines and 3 internet links, 1 of them dedicated with failover.
- Deployed on-premises SharePoint in 2012, then migrated it to SharePoint Online (cloud).
- Built Power Apps, both canvas and model-driven.

**Engineering Intern** | May 2008 – Aug 2011

---

## EDUCATION

- **B.Eng., Sanitary and Environmental Engineering** — Federal University of Santa Catarina (UFSC), Brazil | 2011
- **MBA in Business Management** (executive postgraduate program) — Fundação Getulio Vargas (FGV) | 2015
- **MBA in Building Information Modeling** (postgraduate program) — Universidade Paulista (UNIP) | 2021

## LANGUAGES

Portuguese (native) | English (fluent, C1 — lived and worked in the US) | Spanish (intermediate, B1)
