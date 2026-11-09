# PAULO JOSÉ ARAGÃO JR.

**Data, Financial Modeling & AI Engineer | Former CFO | 15+ years in Infrastructure Finance**

Florianópolis, Brazil (UTC−3) | Remote-first; open to relocation (visa sponsorship required)
pjaragaojr@gmail.com | +55 00 00000-0000 | linkedin.com/in/paulojrarj | github.com/pjaragao

---

## PROFESSIONAL SUMMARY

Engineer and former CFO who turns operational and financial data into models people decide with, and into the software and AI systems that run on top of them. Fifteen years in infrastructure consulting, from intern to Finance Director: DCF and tariff models for utility concessions, pricing for ~90 tenders a year, budgets, KPIs and BI, and coordination of a World Bank–financed program. Today I build data and AI products end to end: Bayesian forecasting, a financial ERP with 2,000+ automated tests, and LLM agents with guardrails. Used to async work across time zones (full overlap with US Eastern hours) and to explaining numbers to non-technical decision-makers.

---

## CORE SKILLS

- **Data & software:** Python, SQL, PostgreSQL (PL/pgSQL, pgTAP, RLS), Supabase, data pipelines/ETL, REST APIs, FastAPI, TypeScript/Next.js, Docker, CI/CD, Power BI, Excel
- **Modeling & analytics:** financial modeling, DCF and feasibility, concession and tariff modeling, valuation, forecasting (Bayesian hierarchical, TimesFM), backtesting, budgeting and variance analysis, KPIs, cost accounting, pricing
- **AI:** LLM applications and agents, tool calling and MCP, guardrails and human-in-the-loop, testing and evaluation, multi-provider routing (Claude, Gemini, OpenAI), AI-assisted development
- **Leadership & domain:** finance team leadership, project and contract management, stakeholder reporting, ERP and digital transformation; infrastructure and utilities (water, wastewater, drainage), project finance, public procurement

---

## PROFESSIONAL EXPERIENCE

### Data & AI Engineer — Self-employed (remote)
**Florianópolis, Brazil** | Feb 2026 – Present

Independent product work, team of one: platform builds, product launches, forecasting models and LLM agents, with AI-assisted development (Claude Code) and automated tests and CI as the quality gate.

- **CentralOps — AI-native retail ERP.** ~95k lines (Next.js/TypeScript, Python workers, PostgreSQL/Supabase): POS, inventory, double-entry accounting, cash flow and P&L, payroll, Brazilian tax and e-invoicing; 133 migrations, 2,000+ pgTAP tests, CI/CD.
- **Customer-facing LLM agent** behind an MCP server (16 tools): acts only through database functions under signed context tokens and row-level security; a guardrail checks every price and stock figure against the database; human handoff when unsure.
- **Election-night projection model (Brazil 2026):** Bayesian hierarchical model on official electoral data (national → regional → state shrinkage); uncertainty calibrated by replaying the 2014, 2018 and 2022 runoffs in real vote-arrival order; 56 tests.
- **Trading Copilot (B3):** broker-statement reconciliation of real costs and slippage, capital-gains tax, TimesFM backtests; 100+ tests.
- Also: a multi-tenant WhatsApp AI agent (300+ tests), a career-automation platform and a sports-pool SaaS; all in production on Docker/Coolify.

The agents work in series, never as one agent doing everything: narrow steps (scorer → writer → reviewer) with each output checked before the next runs and a reviewer that can send work back. Guardrails are in code — figures verified against the database, MCP tools under least-privilege roles, a content guard for forbidden topics — and governance sits on top: human approval for every irreversible action, logs of every agent run and tool call, daily limits, and failures that stop with a clear error and screenshot and go to a fallback model or a person.

### Independent Consultant — Infrastructure Project Finance & Modeling
**Florianópolis, Brazil** | Feb 2026 – Present (freelance, concurrent with the role above)

- Advise large Brazilian corporate groups (under NDA) on major infrastructure projects: engineering-financial models (CAPEX/OPEX, cash flow, feasibility) for infrastructure projects and coordination of sanitation engineering projects.

### MPB Engineering — Florianópolis, Brazil
**Infrastructure engineering consultancy** | May 2008 – Jan 2026

200+ employees; serves municipalities, state utilities and federal agencies. Promoted from intern to Finance Director.

**Finance Director (CFO)** | Feb 2023 – Jan 2026
- Led a 5-person finance team; introduced the annual budget with monthly variance tracking and the KPIs used to monitor operational goals.
- Led the company's second ERP implementation (2023), from finance to every department.
- Built BI reporting on department, project and major-expense performance; built a Power Apps canvas timesheet app in Teams (SQL database, director approval) that merged approved hours with payroll and allocated labor to redesigned ERP cost centers, giving the first real labor cost per project.
- Built an AI accounts-payable pipeline: one Microsoft 365 intake instead of email, Teams and WhatsApp; n8n with Docling and a multimodal fallback; an LLM that may only pick from the ERP's active cost centers and accounts; human review of every entry; posting through the Sienge ERP API; monthly feedback of confirmed examples into the prompt.

**Senior Engineer — Feasibility Modeling, Proposals & Projects** | Aug 2011 – Jan 2023
Project types: feasibility and tariff models, tender pricing, World Bank–financed program, ERP and BIM rollouts.
- Built DCF feasibility and tariff models for municipal water and wastewater concessions.
- Prepared financial proposals for the firm's ~90 tenders a year (QCBS/LCS) and designed a metrics-based pricing method (type, size, risk) that significantly cut bid-preparation time.
- Managed 5–7 concurrent contracts (~US$4M a year) supporting infrastructure investments of US$20–150M; owned scope, schedule, budget, risk and client reporting.
- General coordinator and engineer of record for the **World Bank–financed Lagoas do Norte Program** in Teresina (Feb 2014 – Jul 2019): integrated design of sewerage for 312,000 residents, 28 km of drainage, water, roads, a 1 MW biogas plant and BIM urban design across ~1,300 ha.
- Engineer of record on 46 registered engagements, including a river-basin plan (99,000 km², 2.1M people), water systems for state utilities (up to 1,250 L/s) and environmental management of highway programs (BR-470 for DNIT; Arteris concession, 357 km).
- Led the firm's first ERP implementation (2017), ISO 9001 and the BIM rollout with in-house staff.
- IT lead: deployed on-premises SharePoint in 2012, migrated it to SharePoint Online in 2018, and managed Microsoft 365 for the whole 200+ employee company.

**Engineering Intern** | May 2008 – Aug 2011

---

## EDUCATION & CREDENTIALS

- **B.Eng., Sanitary and Environmental Engineering** — UFSC, Brazil, 2011; CREA-SC 108928-7
- **MBA, Business Management** — Fundação Getulio Vargas (FGV), 2015
- **MBA, Building Information Modeling** — Universidade Paulista (UNIP), 2021

**Languages:** Portuguese (native) | English (fluent, C1; lived and worked in the US) | Spanish (B1)
