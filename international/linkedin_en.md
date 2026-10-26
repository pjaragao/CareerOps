# LinkedIn — English profile (copy to paste)

Target: recruiters in the US and Europe. Positioning: **Applied AI Engineer with deep finance and infrastructure-engineering domain.**
Target roles: Applied AI Engineer · AI Solutions Engineer · Forward Deployed Engineer · AI Engineer (fintech / ERP / finance automation / infrastructure & climate tech).

Field-by-field texts in **English and Portuguese** for the extension's profile filler live in `international/build_linkedin_profile.py` → `config/linkedin_profile.json` (edit there and re-run the script). Items marked ⟦CONFIRM⟧ need your input before publishing. Master CV (also used by the app for tailoring): [resume_base.md](../resume_base.md).

---

## Headline (max 220 chars)

**Recommended**
> Applied AI Engineer | LLM Agents, MCP & Financial Systems | Python · TypeScript · PostgreSQL | 15+ yrs Infrastructure Engineering & Finance (ex-CFO) | Open to relocation EU/US · Remote

Alternatives
> AI Engineer building LLM agents for finance & operations | Ex-CFO & Civil Infrastructure Engineer | Python · Next.js · PostgreSQL | Open to EU/US relocation

> Forward Deployed / AI Solutions Engineer | I turn finance and operations workflows into production AI systems | Ex-CFO · 15+ yrs engineering | Remote or EU/US relocation

---

## About (max 2,600 chars)

I build AI systems that run real operations — and I know those operations from the inside, because I ran them for 15 years.

I'm an engineer and former CFO who now works as an Applied AI Engineer. Recent work:
• CentralOps — an AI-native retail ERP (~95k hand-written lines, 2,000+ automated database tests) with an LLM agent exposed through an MCP server, where every price, stock level and coupon the agent quotes is checked against the database before it reaches a customer.
• Trading Copilot — a trading and tax assistant that sends orders to MetaTrader 5, reconciles broker statements, computes capital-gains tax and backtests strategies with time-series forecasting.
• A multi-tenant WhatsApp AI agent running fantasy-football leagues, with per-league isolation, an LLM fallback chain and 300+ tests.

Before that, I spent nearly 18 years at an engineering consultancy for water, wastewater, urban and solid-waste infrastructure in Brazil, from intern to Finance Director (CFO). I prepared the financial proposals for the firm's ~90 tenders a year, coordinated a World Bank–financed urban infrastructure program, managed consulting contracts for infrastructure investments of US$20–150M, built DCF feasibility and tariff models for municipal concessions, led a 5-person finance team, and drove the firm's ERP, SharePoint and BIM transformations. Today I also advise large Brazilian corporate groups on major infrastructure projects, including engineering-financial modeling for solid waste.

What I bring:
• LLM agents that are safe to put in front of customers and money — tool calling, MCP, guardrails, prompt-injection defenses, human-in-the-loop.
• Production engineering — Python, TypeScript/Next.js, PostgreSQL (RLS, PL/pgSQL, pgTAP), Docker, CI/CD, architecture decision records.
• Finance and domain depth — financial modeling, accounting and tax workflows, pricing, CAPEX/OPEX. I can talk to the CFO and to the codebase.

I'm looking for Applied AI, AI Solutions and Forward Deployed Engineer roles, especially in fintech, finance/ERP automation and infrastructure or climate tech.

Based in Florianópolis, Brazil (UTC−3: full overlap with US Eastern hours, ~5 hours with Central Europe). Open to remote work and to relocation to Europe or the US with visa sponsorship.

Portuguese (native) · English (fluent, C1 — lived and worked in the US) · Spanish (intermediate)

---

## Experience

### Applied AI Engineer — Self-employed
Feb 2026 – Present · Florianópolis, Brazil · Remote

I design, build and operate AI products end to end as the sole engineer, using an AI-assisted workflow (Claude Code) with automated tests and CI as the quality gate.

• CentralOps — AI-native retail ERP and omnichannel platform: Next.js 16/TypeScript, async Python workers, PostgreSQL/Supabase. POS, inventory ledger, double-entry accounting with cost allocation, cash flow and P&L, payroll, Brazilian tax and e-invoicing. 133 SQL migrations, 2,000+ pgTAP tests, CI/CD with manually approved production migrations, 8 architecture decision records.
• Customer-facing LLM agent behind an MCP server (16 tools): it can only act through database RPCs scoped by signed, short-lived context tokens and row-level security; a guardrail validator checks every number in a reply against that run's tool results; autopilot only for whitelisted intents above a confidence threshold, otherwise a human takes over.
• Staff AI assistant that runs tools under the user's own identity, reads documents, barcodes and payment slips (voice, camera, PDF) and only writes after the user confirms.
• Trading Copilot (B3): signal tracking, MetaTrader 5 execution with confirmation, broker-statement parsing to reconcile real costs and slippage, monthly capital-gains tax, strategy backtests with TimesFM forecasts.
• Multi-tenant WhatsApp agent (Hermes Agent + Evolution API) for fantasy-football leagues: isolated persona, data and schedule per league; LLM fallback chain; 300+ unit and end-to-end tests.
• Everything self-hosted on a Docker / Coolify / Traefik homelab.

Skills: AI Agents · Model Context Protocol (MCP) · Python · TypeScript · PostgreSQL

### Independent Consultant — Infrastructure Engineering & Project Finance
Feb 2026 – Present · Florianópolis, Brazil

• Advise large Brazilian corporate groups (names under NDA) on major infrastructure projects.
• General coordination of sanitation engineering projects: scope, schedule, multidisciplinary team and client deliverables.
• Engineering-financial models for solid-waste infrastructure projects: CAPEX/OPEX, cash flow and economic feasibility.

Skills: Financial Modeling · Project Management · Solid Waste Management

### MPB Engineering (group the three positions under the company)

**Finance Director (CFO)** · Feb 2023 – Jan 2026
• Led a 5-person finance team.
• Introduced the firm's annual budget with monthly variance tracking, and defined the KPIs used to monitor operational goals.
• Built BI management reporting on department performance, project margins and major expense lines, focused on cost reduction.
• Redesigned cost accounting in the new ERP: cost centers and labor-cost allocation from employee timesheets.
• Automated reporting and document workflows with n8n and LLM APIs (Gemini, Claude, ChatGPT), plus Power Apps / Power Automate integrated with the ERP and SharePoint, eliminating manual data entry.

**Senior Engineer — Projects, Proposals & Digital Transformation** · Aug 2011 – Jan 2023
• Managed 5–7 concurrent consulting contracts (~R$20M / ~US$4M a year): engineering and advisory contracts of R$1–2M each for infrastructure investments of R$100–800M (~US$20–150M) in environmental, water, wastewater and hydraulics — scope, schedule, budget, risk and reporting with clients and sub-consultants.
• General coordinator and engineer of record for the World Bank–financed Lagoas do Norte Program in Teresina, Brazil (2014–2019): led the proposal and the integrated design of sewerage for 312,000 residents, 28 km of drainage, water supply, roads, a 1 MW biogas plant, BIM-modeled urban design and the social-environmental program across ~1,300 ha.
• Engineer of record on 46 registered engagements (CREA-SC technical record, 40 client certificates), including the Mearim river-basin drainage plan (99,000 km², 2.1M people, Maranhão State), water systems for state utilities (a 1,250 L/s regional system for four cities; Criciúma, 311,000 people; 148 km of network for the Paraná coast) and a sanitary-landfill design and licensing for Proactiva Meio Ambiente.
• Ran the technical-economic analysis of water and wastewater concession processes for four municipalities (Penha, Camboriú, Bombinhas, Pomerode; 30,000–134,000 residents at end of plan).
• Coordinated environmental management on highway programs: BR-470 duplication for DNIT (73 km, 2013–2023), SC-477 for the state agency (73 km) and the Arteris Autopista Litoral Sul concession (Florianópolis Beltway; fauna monitoring along 357 km and 23 municipalities).
• Prepared and reviewed the financial proposals for the firm's ~90 tenders a year (QCBS and LCS); designed a metrics-based pricing method (project type, size, risk factors) that significantly cut bid-preparation time and effort.
• DCF feasibility studies and tariff structures for full municipal water and wastewater concessions, for public and private clients.
• Authored and updated municipal sanitation plans (water, sewage, drainage, solid waste) and CAPEX/OPEX analyses of engineering alternatives.
• Led the firm's SharePoint 2010 → Online migration with in-house staff only, Power Apps / Power Automate tools integrated with the ERP, ISO 9001 procedures and BIM adoption.

**Engineering Intern** · May 2008 – Aug 2011
• Financial proposals, sewage and treatment-plant design, technical reports.

### Remove or fix
• "International Business Operations (J-1 Program)": use the real employer and role — "Back Waiter, P.F. Chang's, Fort Lauderdale, FL (J-1 Work & Travel)" · Dec 2007 – Mar 2008 — or remove the entry; background checks verify employer names.
• "CTI — Engenheiro (Jun 2008 – Jan 2026)" on the Portuguese profile: delete it. You don't recognize it, and its description (IT, proposals, feasibility studies) is MPB work already covered there; a duplicate employer looks inconsistent to recruiters.
• Remove "Managing Partner" from the current About (EN and PT) — you were not a partner, and it would not survive a reference check.
• Remove the current EN bullets with unverified numbers (45%, 30% forecasting accuracy, 120+ hours/month, 18%, 25%).

---

## Projects section (add each one; link the GitHub repo once public)

**CentralOps — AI-native retail ERP & omnichannel platform** · Sep 2026 – Present
ERP + customer-service platform for fashion retail, built solo: POS, inventory, double-entry finance, tax, HR, and an omnichannel inbox (WhatsApp, Instagram, Telegram) with an LLM agent that is safe to touch money — MCP tools, signed context tokens, row-level security, numeric guardrails and human handoff. ~95k hand-written lines, 2,000+ database tests, CI/CD.
Skills: AI Agents · MCP · Next.js · PostgreSQL · Python

**Trading Copilot** · Oct 2026 – Present
Personal trading assistant for the Brazilian market (B3): analyst-signal monitoring, MetaTrader 5 execution, broker-statement reconciliation, capital-gains tax, backtesting and TimesFM forecasting.
Skills: Python · Quantitative Finance · Time-Series Forecasting

**Mr Irrelevant — multi-tenant WhatsApp AI agent** · Sep 2026 – Present
Fantasy-football league agent on WhatsApp: tool with 40 queries, per-league isolation, LLM fallback chain, cron-driven reports, charts and live alerts, 300+ tests.
Skills: AI Agents · Python · LLM Ops

**Election-Night Projection Model (Brazil 2026)** · Sep 2026 – Oct 2026
Real-time projection of Brazil's 2026 presidential runoff from official electoral-court (TSE) data: Bayesian hierarchical model of municipal deviations from a first-round + vote-transfer baseline (national → regional → state shrinkage, log-odds), analytic uncertainty calibrated by replaying the 2014, 2018 and 2022 runoffs in their real vote-arrival order; verifies the TSE's Ed25519-signed feeds and posts live updates to WhatsApp. No LLM — pure statistics; 56 tests.
Skills: Bayesian Statistics · Python · Backtesting · Data Engineering

**CareerOps — AI career-automation platform** · Feb 2026 – Jun 2026
FastAPI + React + Chrome extension. Modular Jinja2 prompt skills across Gemini, NVIDIA NIM and Ollama, human-validated knowledge base, ATS matching and PDF generation.
Skills: FastAPI · React · Prompt Engineering

**Public Tender Radar** · Feb 2026 – Mar 2026
Searches the Brazilian national procurement API (PNCP) across states and classifies tenders against a company profile with Gemini.
Skills: Python · Generative AI · Public Procurement

**JãoBolão — sports-pool SaaS** · 2026
Web and mobile app (Next.js, React Native/Expo, Supabase, Stripe, RevenueCat) with real-time rankings and subscriptions.
Skills: Next.js · React Native · Supabase

---

## Featured (pin in this order)
1. CentralOps — GitHub showcase repo + 2-minute demo video (agent answering a customer, guardrail blocking a wrong price, human handoff).
2. A post: "How I made an LLM agent safe to touch money" (MCP + RLS + numeric guardrails). Technical posts are how international recruiters find you.
3. Trading Copilot — GitHub repo.
4. JãoBolão — link to the live app or its GitHub repo (github.com/pjaragao/J-oBol-o) with a 3-screen image (pool, live ranking, subscription plans). Description: "Web + mobile sports-pool SaaS: Next.js, React Native/Expo, Supabase (Postgres, Auth, Realtime, Edge Functions), Stripe and RevenueCat subscriptions, live rankings and a WhatsApp AI bot." Shows full product delivery: payments, mobile and real time.
5. Election-night projection model — GitHub link + the live chart image. Description: "Real-time projection of Brazil's 2026 presidential runoff from official electoral-court (TSE) data: Bayesian hierarchical model of municipal deviations from a first-round + vote-transfer baseline (national → regional → state shrinkage, log-odds), analytic uncertainty calibrated by replaying the 2014, 2018 and 2022 runoffs in their real vote-arrival order; verifies the TSE's Ed25519-signed feeds and posts live updates to WhatsApp. No LLM — pure statistics; 56 tests." Shows statistical modeling and calibration, not just LLMs.
6. Mr Irrelevant — GitHub link + a WhatsApp screenshot (league chart or trade verdict). Description: "Multi-tenant WhatsApp AI agent for fantasy-football leagues: one instance serves several leagues with isolated persona, data, secrets and schedule, built from nothing but the league ID; 40-query league tool, LLM fallback chain ending in deterministic text, cron-driven reports, charts and live injury alerts; 300+ unit and end-to-end tests." Shows an AI agent running in production for real users.
7. GitHub profile.

---

## Skills
Top 5 (shown on profile): AI Agents · Large Language Models (LLM) · Python · PostgreSQL · Financial Modeling

Full list: Model Context Protocol (MCP) · Prompt Engineering · Generative AI · LLMOps · Retrieval & knowledge bases · Human-in-the-loop · TypeScript · Next.js · React · FastAPI · Supabase · Docker · CI/CD · GitHub Actions · REST APIs · Webhooks · Linux · n8n · Time-Series Forecasting · Financial Analysis · Discounted Cash Flow (DCF) · CAPEX/OPEX · Feasibility Studies · Pricing Strategy · Budgeting · Accounting Systems · Power BI · SQL · Project Management · Public Procurement · Water & Wastewater · Solid Waste Management · ERP Implementation · Digital Transformation · BIM

---

## Settings checklist
- [ ] English profile version: LinkedIn shows a viewer the version in their language, so recruiters with an English interface see this one.
- [ ] Open to Work → **recruiters only**. Titles: Applied AI Engineer, AI Engineer, AI Solutions Engineer, Forward Deployed Engineer, Solutions Architect. Locations: Remote (worldwide / US / EU), Lisbon, Madrid, Amsterdam, Berlin, Dublin. Types: full-time, contract.
- [ ] Location: keep Florianópolis, Brazil (honest; relocation is stated in headline and About).
- [ ] Contact info: email + GitHub + portfolio link.
- [ ] Professional photo and a simple banner (expected on LinkedIn, unlike on the CV).
- [ ] 2–3 recommendations in English (former partner/director, a client, a project colleague).
- [ ] Custom URL: keep linkedin.com/in/paulojrarj or switch to /in/paulo-aragao-jr (easier to read).
