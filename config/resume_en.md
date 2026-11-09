# PAULO JOSÉ ARAGÃO JR.

**Data, Financial Modeling & AI | Forecasting, Valuation & Analytics | Engineer & former CFO**

Florianópolis, Brazil (UTC−3) | Open to relocation to the EU or US (visa sponsorship required) and to remote roles
pjaragaojr@gmail.com | +55 00 00000-0000 | linkedin.com/in/paulojrarj | github.com/pjaragao

---

## PROFESSIONAL SUMMARY

Former CFO and engineer with 15+ years in infrastructure finance, now building data, modeling and AI systems end to end. I build the models people decide with — DCF feasibility and tariff models for utility concessions, pricing for ~90 tenders a year, budgets, KPIs and BI — and the software around them: statistical forecasting (a Bayesian election-night projection model calibrated on three past elections), financial systems with double-entry ledgers and 2,000+ automated tests, and LLM agents where every number comes from the database. Python, SQL and PostgreSQL every day, and 11 AI and data systems of my own running in production on a Docker/Coolify production platform (48 containers, 88,000+ agent and scheduled runs). A background as a sanitary and environmental engineer — including general coordination of a World Bank–financed urban program — gives me real domain depth in infrastructure, utilities and project finance. I also led the company's IT infrastructure — redundant servers, failover internet links, backups and multi-office VPN — so I know how to keep systems, and the AI automations on top of them, running reliably and continuously in production.

---

## SKILLS

- **Modeling & analytics:** financial modeling, DCF and feasibility studies, concession and tariff modeling, valuation, forecasting (Bayesian hierarchical models, TimesFM), backtesting, budgeting and variance analysis, KPI design, cost accounting, pricing
- **Data & software:** Python, SQL, PostgreSQL (PL/pgSQL, pgTAP, Supabase, PGMQ queues), SQLite, Redis, FastAPI, async workers, data pipelines, Playwright browser automation, Power BI, Excel, REST APIs and webhooks, TypeScript/Next.js/React/Tailwind, Expo/React Native, Turborepo, Flask, Pandas/NumPy, Typst and LaTeX documents, Google Workspace APIs, GitHub Actions CI/CD
- **AI:** LLM applications and autonomous agents, tool calling, MCP servers, multi-agent systems and inter-agent calls, RAG, agent memory, guardrails and human-in-the-loop, prompt engineering and prompt chaining, multi-provider model routing (Claude, GPT-4o, Gemini, open models), LangChain, Pydantic AI, Hermes Agent, n8n AI workflows, AI-assisted development with Claude Code
- **DevOps & platform:** Docker and Docker Compose, Coolify (PaaS, GitOps deploys), Tailscale zero-trust networking, Nginx (TLS 1.3 reverse proxy), Linux/WSL2, scheduled jobs and monitoring
- **IT infrastructure:** Active Directory, Microsoft 365 tenant administration, SharePoint (on-premises and Online), Power Apps (canvas and model-driven), file server (30+ TB), backup, VPN, multi-office networking, high availability (redundant servers, UPS, failover internet links)
- **Domain:** infrastructure and utilities (water, wastewater, drainage), project finance, public procurement (QCBS/LCS), ERP, BIM

---

## PROFESSIONAL EXPERIENCE

### Data & AI Engineer — Self-employed
**Florianópolis, Brazil (remote)** | Feb 2026 – Present

Independent product work, team of one. Project types: platform builds, product launches, forecasting models, LLM agents.

Build and operate data, modeling and AI products end to end as sole engineer: 14 systems, 11 in production. Method: prototype integrations, prompt chains and agent tool calls in n8n to prove the flow and its edge cases, then harden them with Claude Code into production services (FastAPI, Next.js, Python workers, PL/pgSQL), with automated tests and CI as the quality gate.

How the agents are built: no single agent does the whole job. Each workflow is a chain of narrow agents working in series — for example scorer → writer → reviewer — and each step's output is checked before the next one runs; the reviewer can send work back or fix it, and its notes go to the human who approves. Guardrails live in code, not only in prompts: numbers and prices are verified against the database before a reply goes out, agents act only through MCP tools under least-privilege database roles, and a content guard blocks topics that must never appear. Governance on top: every irreversible action (an application, a message, a payment-related answer) waits for human approval, often from WhatsApp; every agent run and tool call is logged; actions have daily limits; and when a step fails — a page changed, a check did not pass — it stops with a clear error code and a screenshot and goes to a fallback model or to me, never a silent guess.

- **Election-night projection model (Brazil 2026):** Bayesian hierarchical model of municipal deviations from a first-round + vote-transfer baseline on official electoral data (national → regional → state shrinkage); uncertainty calibrated by replaying the 2014, 2018 and 2022 runoffs in real vote-arrival order; 56 tests.
- **CentralOps — retail ERP with an AI agent.** ~95k-line system (PostgreSQL/Supabase, Python workers, Next.js/TypeScript): double-entry ledger, cash flow and P&L, inventory, payroll, Brazilian tax and e-invoicing; 133 migrations, 2,000+ pgTAP tests, CI/CD. Point of sale, e-commerce, Stone payments and NFC-e e-invoicing; 10 PostgreSQL schemas with PGMQ queues. Omnichannel scope: touch POS, e-commerce, TEF/Stone payments, NFC-e straight to SEFAZ with offline contingency, customer CRM scoring and multi-warehouse inventory with atomic reservations; Next.js 16/React 19 front end. The customer-facing LLM agent acts only through database functions exposed by an MCP server, and a guardrail checks every price and stock level against the database before a reply goes out; an operations agent (Hermes) uses the same MCP server to audit stock divergences, watch SEFAZ transmissions and PGMQ queues and answer sales and cash-flow questions, and a store-operations agent keeps the catalog and product photos in sync with Google Drive.
- **Trading Copilot (B3):** tracks analyst signals, reconciles broker statements for real costs and slippage, computes capital-gains tax and backtests strategies with TimesFM forecasts; risk cockpit on MetaTrader 5 history (payoff, hit rate, intraday max drawdown, discipline rules) with an LLM trade-journal reviewer; Flask, Pandas, SQLite WAL; 100+ tests.
- **CareerOps — career automation platform:** FastAPI, React/Vite, PostgreSQL and a Playwright/Chromium worker (watchable over noVNC) that finds and scores jobs with LLMs against this CV, tailors CVs (PDF via Gotenberg, Typst and LaTeX; prototyped as n8n agent workflows of 18 and 26 nodes), and applies, connects and comments on LinkedIn only after human approval, with layered fallbacks when the site changes.
- **WhatsApp AI agents:** multi-tenant agent platform (300+ tests) running an executive assistant (94 tool commands, 58 skills, 35 Python modules; Google Calendar, Tasks and Gmail, live flight tracking, a contract-drafting engine for 7 contract types with company-registry checks; approves CareerOps actions from chat; 22,000+ scheduled runs) and a customer-service agent with a human persona, persistent memory and hand-over to staff; Evolution API, SQLite and Redis.
- **Sports analytics:** Bayesian (MCMC) and TimesFM forecasting on NFL data for a fantasy league, with an automated editorial bot on a 13-slot weekly schedule (41,000+ runs, charts with Matplotlib/Seaborn); open-source Sleeper API engine (TypeScript/Python) with an event-driven game watcher and RAG over a 99-document knowledge base it generates.
- **Public-tender intelligence:** search, scoring and executive summaries of Brazilian public tenders from the national PNCP API — downloads terms of reference and extracts technical requirements with Gemini 1.5 Pro on Firebase Genkit; Flask and Node.js/TypeScript.
- **Earlier products:** a sports-pool SaaS (Turborepo monorepo, Next.js 15 web and Expo/React Native app, Mercado Pago payments, two redundant football data APIs, Supabase) and a live World Cup 2026 iCalendar feed (Next.js, RFC 5545).
- **Platform:** everything runs in production on my own Docker/Coolify platform — 48 containers in 21 stacks behind Tailscale zero-trust networking (no public ports; Nginx TLS 1.3 on 16 services), GitOps deploys, an n8n hub as the prototyping bench, password vault, daily backups mirrored to Google Drive, 88,000+ agent and scheduled runs.

### Independent Consultant — Infrastructure Project Finance & Modeling
**Florianópolis, Brazil** | Feb 2026 – Present

Independent practice serving large Brazilian corporate groups. Freelance, held concurrently with the data and AI work above.

- Advise large Brazilian corporate groups (under NDA) on major infrastructure projects: engineering-financial models (CAPEX/OPEX, cash flow, feasibility) for infrastructure projects and coordination of sanitation engineering projects.

### MPB Engineering — Florianópolis, Brazil
**Consultancy for water, wastewater, urban and highway-environmental infrastructure** | May 2008 – Jan 2026

Consultancy of 200+ employees serving municipalities, state utilities and federal agencies, bidding ~90 tenders a year. Internal promotions from intern to Finance Director over nearly 18 years.

**Finance Director (CFO)** | Feb 2023 – Jan 2026
Project types: budgeting and KPI rollout, ERP migration, BI reporting, finance automation.
- Led a 5-person finance team; introduced the annual budget with monthly variance tracking and the KPIs used to monitor operational goals.
- Led the company's second ERP implementation (2023), starting from finance and rolled out to every department with process mapping and staff training.
- Built BI reporting on department and project performance and major expenses; built a Power Apps canvas timesheet app in Teams (SQL database, director approval) that merged approved hours with payroll and allocated labor to redesigned ERP cost centers, giving the first real labor cost per project.
- Built an AI accounts-payable pipeline: one Microsoft 365 intake instead of email, Teams and WhatsApp; n8n with Docling and a multimodal fallback; an LLM that may only pick from the ERP's active cost centers and accounts; human review of every entry; posting through the Sienge ERP API; monthly feedback of confirmed examples into the prompt.

**Senior Engineer — Feasibility Modeling, Proposals & Projects** | Aug 2011 – Jan 2023
Project types: feasibility and tariff modeling, concession analysis, tender pricing, World Bank–financed program delivery, ERP and BIM rollouts.
- Built DCF feasibility and tariff models for municipal water and wastewater concessions and analyzed concession processes for four municipalities.
- Prepared financial proposals for the firm's ~90 tenders a year (QCBS/LCS) and designed a metrics-based pricing method that significantly cut bid-preparation time.
- Managed 5–7 concurrent contracts (~US$4M a year) of US$0.2–0.4M each, supporting infrastructure investments of US$20–150M; owned scope, schedule, budget, risk and client reporting.
- General coordinator and engineer of record for the **World Bank–financed Lagoas do Norte Program** in Teresina (Feb 2014 – Jul 2019): proposal and integrated design of sewerage for 312,000 residents, 28 km of drainage, water, roads, a 1 MW biogas plant and BIM-modeled urban design across ~1,300 ha.
- Engineer of record on 46 registered engagements, including the Mearim river-basin plan (99,000 km², 2.1M people), water systems for state utilities (up to 1,250 L/s) and environmental management of highway programs (BR-470 for DNIT; Arteris concession, 357 km).
- Led the firm's first ERP implementation (2017) and the BIM rollout with in-house staff.

**IT Infrastructure Lead**
Project types: multi-office on-premises infrastructure, high availability, cloud migration.
- Owned the IT infrastructure of the 200+ employee firm, with several offices joined to the local network over VPN: Active Directory, the on-premises file server (30+ TB) and management of Microsoft 365 for the whole company.
- Built for high availability and continuous operation: 2 redundant servers running in parallel, on-site UPS installed and maintained, local-server backup routines and 3 internet links, 1 of them dedicated with failover.
- Deployed on-premises SharePoint in 2012 for document control and internal records, then migrated it to SharePoint Online in 2018.
- Built Power Apps, both canvas and model-driven.

**Engineering Intern** | May 2008 – Aug 2011

---

## EDUCATION

- **B.Eng., Sanitary and Environmental Engineering** — Federal University of Santa Catarina (UFSC), Brazil | 2011
- **MBA in Business Management** (executive postgraduate program) — Fundação Getulio Vargas (FGV) | 2015
- **MBA in Building Information Modeling** (postgraduate program) — Universidade Paulista (UNIP) | 2021

## LANGUAGES

Portuguese (native) | English (fluent, C1 — lived and worked in the US) | Spanish (intermediate, B1)
