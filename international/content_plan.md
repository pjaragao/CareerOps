# Plano de conteúdo — LinkedIn (dois mercados)

Objetivo: ser encontrado em **dois mercados**, cada um com seu foco:

| Mercado | Idioma | Foco (nesta ordem) | Público |
|---|---|---|---|
| **Brasil** | Português | Engenharia e saneamento → modelagem técnico-financeira → finanças → dados e IA | companhias de saneamento e autarquias, concessionárias, consultorias, construtoras, fundos de infraestrutura, bancos de fomento |
| **Exterior** (EUA e Europa) | Inglês | Dados → finanças → modelagem; IA como forma de construir; engenharia só como domínio | financial modeling, data science/analytics, FP&A, IA para finanças, fintech, finanças de infraestrutura e energia |

Os rascunhos são gerados no **LinkedIn Copilot** do CareerOps, escolhendo o mercado. Este plano está em português.

---

## 0. O papel de cada canal

| Canal | Papel |
|---|---|
| **LinkedIn** | O canal de publicação: posts de texto, carrosséis em PDF e vídeos curtos nativos, no idioma de cada mercado |
| **GitHub** | A prova técnica (exterior). Posts de dados e modelagem apontam para um repositório ou demo |
| **Artigo longo** (LinkedIn Articles) | 1 por mês, alternando os mercados. Vira link no Featured |

---

## 1. Mensagem central

- **Brasil:** "Engenharia de saneamento com rigor de quem já foi diretor financeiro — e com dados e IA para projetar, orçar e operar melhor."
- **Exterior:** "I build the models people make decisions with — and the data and AI systems around them — after 15 years modeling infrastructure and running finance."

## 2. Pilares

**Brasil (PT)**

| Pilar | O que mostra | Fonte |
|---|---|---|
| **E. Engenharia e saneamento** | Lições de projeto: o que funciona e o que dá errado | Lagoas do Norte, sistemas da CASAN e Sanepar, Mearim, aterro, rodovias |
| **C. Concessões e modelagem técnico-financeira** | Viabilidade, tarifa, CAPEX/OPEX, análise de concessões, preço de proposta | Concessões de Penha, Camboriú, Bombinhas e Pomerode; ~90 licitações/ano |
| **O. IA e dados em projeto, orçamento e obra** | Onde a IA ajuda (e onde não) em quantitativos, orçamento, edital, BIM, licenciamento, medição, aditivos, perdas | Experiência de projeto + ferramentas próprias |
| **G. Gestão financeira de engenharia** | Orçamento, KPIs, custo por projeto, BI | Período como diretor financeiro |
| **T. Tecnologia na infraestrutura** | Sistemas próprios aplicados ao setor | CentralOps, modelos estatísticos, automações |

**Exterior (EN)**

| Pilar | O que mostra | Fonte |
|---|---|---|
| **M. Financial modeling & valuation** | DCF, tarifa, concessões, pricing, orçamento | MPB, consultoria atual |
| **S. Forecasting & statistics** | Estatística de verdade, calibrada com backtest | Modelo de projeção eleitoral, TimesFM |
| **D. Data & financial systems** | Razão contábil, conciliação, DRE e caixa em código, testes de lógica financeira | CentralOps, Copiloto de Trades |
| **A. AI for finance** | Agentes que mexem com dinheiro com segurança | CentralOps (ADR-0005) |
| **I. Infrastructure & project finance** | Investimentos de US$ 20–150M vistos por quem modelou; engenharia como domínio | Lagoas do Norte (Banco Mundial), concessões |

## 3. Perfil

Os textos do perfil (EN e PT) ficam em `international/build_linkedin_profile.py` e aparecem no painel **CareerOps · Perfil** da extensão. Na seção "Contact info", coloque o GitHub.

## 4. Cadência e horário

- **3 posts por semana:** 2 do exterior (EN, terça e quinta) e 1 do Brasil (PT, quarta), **10h no horário de Brasília** (8–9h na costa leste dos EUA, 14–15h na Europa Central).
- **Na primeira hora depois de postar:** responda os comentários e comente em 5 posts da área-alvo do mercado daquele post.

---

## 5. Calendário das 4 primeiras semanas

| Sem. | Terça (EN · exterior) | Quarta (PT · Brasil) | Quinta (EN · exterior) |
|---|---|---|---|
| 1 | **Post 1 — Quem sou eu** (abaixo; ajuste o fim para dados, finanças e modelagem) | Apresentação: engenheiro sanitarista, Lagoas do Norte, 46 ARTs, modelagem de concessões | Pilar S: o modelo de projeção eleitoral e o backtest em três eleições |
| 2 | Pilar M: o que um modelo de viabilidade de concessão precisa ter para alguém decidir com ele | Pilar C: o que a modelagem tarifária ensina sobre viabilidade de concessão | **Post 2 — números que vêm do banco** (abaixo), como pilar A |
| 3 | Pilar D: razão contábil e conciliação em código com 2.000 testes | Pilar O: IA em quantitativos e orçamento — onde ajuda e onde não confiar | Pilar I: infraestrutura vista de quem modelou US$ 20–150M |
| 4 | **Artigo longo** (EN) + post curto com o link | Pilar G: orçamento e KPIs numa consultoria de engenharia | Pilar M ou S, a partir do que repercutiu |

Os posts 1 a 3 abaixo foram escritos para o posicionamento anterior, centrado em IA. Eles servem como pilar A (IA para finanças) e D (dados e sistemas financeiros) do exterior; para o resto, gere rascunhos no Copilot.

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
- **20 convites**, divididos entre os mercados: no Brasil, gestores e recrutadores de saneamento, concessões, consultorias e fundos de infraestrutura; no exterior, hiring managers e recrutadores de financial modeling, dados, FP&A e IA para finanças (Portugal, Espanha, Irlanda, Holanda, Alemanha, Reino Unido; EUA remoto).
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
