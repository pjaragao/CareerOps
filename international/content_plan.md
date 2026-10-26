# Plano de conteúdo — LinkedIn

Objetivo: ser encontrado por recrutadores e hiring managers dos EUA e da Europa como **Applied AI Engineer com domínio de finanças e infraestrutura**.
Os posts vão em inglês, prontos para publicar. Este plano está em português.

---

## 0. O papel de cada canal

| Canal | Papel | Idioma |
|---|---|---|
| **LinkedIn** | O único canal de publicação: é onde recrutador procura. Posts de texto, carrosséis em PDF (documento) e vídeos curtos nativos. | Inglês |
| **GitHub** | A prova. Todo post aponta para um repositório ou uma demo. | Inglês |
| **Artigo longo** (LinkedIn Articles + dev.to ou Medium) | 1 por mês. É o que aparece no Google e vira link no Featured. | Inglês |

---

## 1. Mensagem central (a frase que todo post reforça)

> **"I build AI agents that are safe to touch money — because I spent 18 years in infrastructure and finance, I know which numbers must never be wrong."**

## 2. Pilares (alternar)

| Pilar | O que mostra | Fonte de material |
|---|---|---|
| **A. Agents that touch money** | Engenharia de agentes com segurança: MCP, RLS, guardrails, humano no circuito | CentralOps (ADR-0005, ADR-0008) |
| **B. Ex-CFO builds** | Finanças + IA: orçamento, KPIs, contabilidade, impostos, trading | CentralOps (financeiro), Trading Copilot |
| **C. Infrastructure × AI** | 18 anos em saneamento, resíduos e Banco Mundial; onde a IA entra em infraestrutura | MPB, consultoria atual (sem nomes), Radar de Licitações |
| **D. AI-assisted engineering** | Como usar agentes de código com rigor: testes, ADRs, CI | CentralOps, Mr Irrelevant |

## 3. Perfil

A headline e o About já estão em [linkedin_en.md](linkedin_en.md). Na seção "Contact info", coloque o GitHub e o link da demo do CentralOps.

## 4. Cadência e horário

- **LinkedIn:** 2 posts por semana (terça e quinta), **10h no horário de Brasília**. Equivale a 8–9h na costa leste dos EUA e 14–15h na Europa Central, então pega os dois públicos.
- **Na primeira hora depois de postar:** responda todos os comentários e comente em 5 posts de gente da sua área-alvo. Isso pesa mais no alcance do que a hora exata.

---

## 5. Calendário das 4 primeiras semanas

| Sem. | Terça | Quinta |
|---|---|---|
| 1 | **Post 1 — Quem sou eu** (pronto abaixo) | **Post 2 — Agente seguro para mexer em dinheiro** (pronto abaixo) |
| 2 | **Post 3 — 95k linhas com IA, 2.000 testes** (pronto abaixo) | Vídeo nativo de 45 s: o agente recusando um preço errado e passando para um humano |
| 3 | "What World Bank infrastructure projects taught me about shipping AI": termos de referência viram specs, contrato vira teste de aceitação, banca avaliadora vira avaliação do modelo | "My trading copilot reconciles broker statements — here's why the tax math was harder than the AI": nota de corretagem, custos reais, slippage, IR |
| 4 | "A CFO's checklist before letting AI near your ledger": partidas dobradas, rateio, fechamento, trilha de auditoria | **Artigo longo** (versão estendida do Post 2) + post curto com o link |

Depois disso: repetir os pilares A–D em rodízio, sempre com um projeto como prova.

---

## 6. Posts prontos

### Post 1 — Quem sou eu (Pilar C)

> I spent nearly 18 years in infrastructure engineering — the last 3 as a CFO.
>
> Now I build AI agents. It's not a career change. It's the same job with better tools.
>
> In infrastructure consulting, my work was turning messy reality into models people could trust: feasibility studies for water and wastewater concessions, financial proposals for ~90 tenders a year, a World Bank–financed urban program in Teresina, Brazil. As CFO: budgets, KPIs and cost allocation with a 5-person team.
>
> Every one of those jobs had the same bottleneck: people copying data between systems and re-checking numbers by hand.
>
> So in 2026 I started building the systems myself:
> → CentralOps, an AI-native ERP where the agent can sell, but can't invent a price
> → A trading copilot that reconciles broker statements and computes taxes
> → A WhatsApp agent that runs fantasy-football leagues for real groups
>
> What I learned: domain knowledge is the moat. Anyone can call an LLM API. Knowing which number must never be wrong is the hard part.
>
> I'm looking for Applied AI / Forward Deployed Engineer roles in fintech, finance automation and infrastructure tech — remote, or relocating to Europe or the US.
>
> If you're building AI for finance or infrastructure, I'd love to compare notes.
>
> #AIEngineering #AIAgents #FinTech #LLM #CareerChange

**Versão carrossel (PDF no LinkedIn, opcional):** 1) "18 years in infrastructure. 3 as CFO. Now I build AI agents." 2) Infrastructure: concessions, ~90 tenders a year, World Bank 3) CFO: budget, KPIs, 5-person team 4) The bottleneck: humans copying numbers 5–7) Os três projetos, um por slide, com print 8) "Domain knowledge is the moat" 9) "Open to EU/US roles — let's talk".

### Post 2 — Agente seguro para mexer em dinheiro (Pilar A)

> My AI agent can reserve stock, create orders and send payment links to customers on WhatsApp.
>
> Here's how I make sure it can't give away a discount — even when a customer tries prompt injection.
>
> 1. The model never touches tables. Every tool runs through one database function, under a role with no table access.
> 2. Identity comes from a signed token, not from the model. Store, customer and conversation travel in a 10-minute JWT and are revalidated in the database. IDs the model sends are discarded.
> 3. The database computes every number. Prices, stock and totals come from SQL, never from the LLM. Orders above a limit go to a human.
> 4. A guardrail checks the reply before it's sent. Every price, stock level and coupon in the message must match a tool result from that same run. Fail → one retry → draft for a human.
> 5. Autopilot only where it's safe: a closed list of intents with confidence ≥ 0.75. Everything else is copilot or human.
>
> Result: a malicious prompt can't reach another customer's data or a value the database didn't compute — and swapping the model provider doesn't change any of it.
>
> The rule I brought from finance: never trust a number you can't trace back to the ledger.
>
> How are you handling guardrails for agents that touch money?
>
> #AIAgents #LLMSecurity #PromptInjection #MCP #PostgreSQL

**Vídeo nativo (LinkedIn, 45 s, opcional):** tela do CentralOps com dados fictícios → cliente pede desconto → o agente recusa e aplica só o cupom válido → um pedido acima do limite vai para um humano. Legenda na tela: "The database computes every number."

### Post 3 — 95k linhas com IA, 2.000 testes (Pilar D)

> I wrote ~95k lines of production code in about five weeks with an AI coding agent.
>
> The number that matters isn't 95k. It's 2,000+ — the database tests that let me trust it.
>
> AI-assisted coding is fast. That's exactly why it needs harder controls than human coding:
>
> → The database is the system of record. Business rules live in transactional SQL functions, not scattered across the app.
> → Every rule has a test. pgTAP tests cover row-level security, the accounting ledger, inventory, payroll and tax.
> → Decisions are written down. 8 architecture decision records explain the why, so neither I nor the AI re-argues them every session.
> → Production is gated. CI runs everything on every pull request; production migrations need manual approval.
>
> My CFO years taught me: speed without controls isn't speed. It's future rework.
>
> AI didn't replace engineering discipline for me. It made discipline the main job.
>
> #AIAssistedDevelopment #ClaudeCode #SoftwareEngineering #PostgreSQL #Testing

**Versão carrossel (PDF no LinkedIn, opcional):** 1) "95k lines in 5 weeks. The number that matters: 2,000." 2–5) As quatro regras, uma por slide, com print do código ou do CI 6) "Speed without controls is future rework."

---

## 7. Regras para todo conteúdo

- **Nunca citar os clientes da consultoria** (NDA), nem por pista: setor + cidade + porte já identificam.
- **Demos só com dados fictícios** (o CentralOps tem seed de demonstração em `supabase/seed/90_dev_demo.sql`). Nada de cliente real da loja, CPF, valores reais.
- **Só números que você defende numa entrevista.** Os percentuais estimados da MPB ficam fora.
- **Um post, uma ideia, um projeto como prova.**

---

## 8. Prospecção ativa (o conteúdo sozinho não basta)

Toda semana:
- **20 convites** para hiring managers e recrutadores de AI engineering em fintech, ERP/finanças e infra/climate tech, nos países-alvo (Portugal, Espanha, Irlanda, Holanda, Alemanha; EUA remoto).
- **5 candidaturas** adaptadas pelo CareerOps.
- **Comentários de verdade** em posts dessas pessoas antes de mandar mensagem.

Nota do convite (máximo de 300 caracteres):
> Hi {name} — I'm an ex-CFO and infrastructure engineer now building LLM agents for finance (MCP, guardrails, PostgreSQL). I follow {company}'s work on {topic} and would love to connect. Open to remote or EU/US relocation.

Registro semanal: visualizações do perfil, aparições em busca, convites aceitos, InMails de recrutador, conversas, entrevistas.

---

## 9. Cursos, certificações, palestras

Em AI engineering, o portfólio pesa mais que certificado. Mesmo assim, alguns itens passam no filtro de RH e ajudam na imigração. **Confira se cada um ainda existe e quanto custa antes de pagar.**

| Prioridade | Item | Por quê |
|---|---|---|
| 1 — já (gratuitos, 1–2 semanas) | Cursos da Anthropic (Claude API, MCP), Hugging Face AI Agents Course e cursos curtos da DeepLearning.AI sobre agentes e avaliação | Formalizam o que você já faz e dão um certificado para a seção "Licenses & certifications" |
| 2 — 1 a 3 meses | **Uma** certificação de nuvem em IA: AWS (AI Practitioner → Machine Learning Engineer Associate) ou Azure AI Engineer Associate | Passa no filtro de ATS e de recrutador de empresa grande; escolha a nuvem que mais aparecer nas vagas-alvo |
| 3 — imigração | Certificado de inglês (IELTS Academic, TOEFL ou Cambridge C1) | Vários vistos e sistemas de pontos pedem comprovação formal; dá credibilidade ao "C1" do CV |
| 3 — imigração | Equivalência do diploma: Alemanha (ZAB/anabin, exigida pelo Blue Card) e EUA (avaliação de credenciais, como a WES) | Pré-requisito em vários processos de visto; é demorado, então comece cedo |
| Palestras | Começar por meetups de Florianópolis e eventos brasileiros (TDC, Python Brasil) com o tema do Post 2; depois mandar o mesmo tema, em inglês, para meetups online internacionais de AI engineering | Uma palestra gravada vira link no Featured e prova de comunicação em inglês |
| Artigos | 1 artigo longo por mês (o primeiro é o Post 2 expandido) | Aparece no Google, entra no Featured e no README do GitHub |
