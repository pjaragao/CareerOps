# Interview Prep — Truelogic · Forward Deployed Engineer (AI & Business Transformation)

Interview: today, Nov 2, 2:00 PM (UTC−3) · Job #711 in CareerOps

**Part 1 — English** · **Part 2 — Português** (mesmo conteúdo, traduzido)

---

# PART 1 — ENGLISH

## 1. About the company

**Truelogic** (headquartered in New York) is a *nearshore staff augmentation* company: it places Latin American professionals on projects for U.S. companies. 20+ years in business, 600+ professionals in 25+ countries, clients from startups to Fortune 500.

- **Model:** you are hired by Truelogic and work embedded in the client's team. Remote, paid in USD, flexible hours, focus on results.
- **Culture they sell:** well-being, senior teams, a multicultural Latin American network.
- **End client (not named):** a global technology + creative network that drives business transformation for large enterprise brands, working directly with executive leadership across the whole customer journey. Think of a large digital agency/consultancy.

**What this means for the interview:** the first conversation is usually with a Truelogic recruiter (fit, English, salary, availability). Then comes the client (technical + consultative). Show that you adapt to the client and communicate well with Americans.

**Questions to ask them:**
1. Who is the client and what does a typical FDE engagement look like — length, team, who I'd report to?
2. What's the first problem you'd want this person to solve in the first 90 days?
3. Which AI stack does the client standardize on (OpenAI/Anthropic, Copilot Studio, n8n, etc.)?
4. How is success measured for an FDE — adoption, ROI, number of prototypes?
5. What are the next steps in the process, and is the client interview separate?

## 2. About the role

**In one sentence:** half management consultant, half AI engineer. You embed with the client, diagnose the process, redesign the operation and **prove the value by building an AI prototype that works** — without a dedicated engineering team.

| What they ask for | Your proof |
|---|---|
| 5–10 years in consulting / transformation | 15+ years at MPB: Senior Engineer → CFO; independent consultant |
| 2+ areas: org design, operating model, change mgmt, process engineering, tech enablement | All of them: SIENGE ERP, BIM, budgeting/KPIs, SharePoint migration, cost allocation |
| Structured arguments for executives | ~90 proposals/year, DCF models for municipalities, executive dashboards |
| Building real AI workflows/prototypes | n8n + LLM for accounts payable, CentralOps (MCP, 16 tools, guardrails), trading copilot |
| Working alone, knowing when to ask for help | CentralOps ~95k lines solo, 2,000+ tests; hired BIM consultants when needed |
| Diagnosis before solution | Process mapping before the ERP; found the root cause of misallocated labor cost |
| Bias toward prototypes over roadmaps | Power Apps allocation app in Teams; AP pipeline with a feedback loop |

**60-second pitch (memorize the structure, not the words):**

> I'm an engineer who became a CFO, and then an applied AI engineer. For 15 years at MPB Engineering I ran large advisory programs — including a World Bank–financed urban program — and as Finance Director I led the company's operating model and digital transformation: budgeting and KPIs, a new ERP, timesheet-based cost allocation, and AI automations with n8n and LLM APIs. Since 2026 I build AI systems hands-on: an AI-native ERP with MCP agents and deterministic guardrails, workflow bots, forecasting tools. So what I bring to an FDE role is both halves: I can sit with executives and diagnose where the process breaks, and then build the working prototype myself in days to prove the value.

**Why this role?**
> It's the exact intersection of what I've done: I've been the business owner who needed transformation, and I've been the person building the solution. Most roles ask for one side. This one asks for both, and that's where I add the most value.

## 3. STAR cases (use 4–5; pick by question)

> Tip: ~2 minutes each. Situation and task short (20%), action with "I" (60%), result with a number (20%). Close with what you learned.

### STAR 1 — AI accounts payable automation *(AI prototype, adoption, ROI)*
- **S:** AP documents arrived through email, Teams and WhatsApp; the finance team extracted data and mapped cost centers by hand.
- **T:** Centralize intake and automate extraction and classification against our chart of accounts.
- **A:** I built an n8n pipeline: employees drop files in one folder, Docling converts them to Markdown (or the image goes straight to the model), the LLM gets our active cost centers and chart of accounts and fills a spreadsheet for human review. A monthly workflow feeds confirmed classifications back into the prompt as examples. Then I started the direct ERP API integration.
- **R:** Manual data entry dropped drastically; accuracy improved month after month thanks to the feedback loop; the team reviewed instead of typing.
- **Use for:** "Tell me about an AI prototype you built", "How do you keep humans in the loop?"

### STAR 2 — Labor cost allocation *(root cause diagnosis, operating model)*
- **S:** Labor was our biggest cost, but it wasn't allocated to projects — leadership had no real project margin.
- **T:** Create a reliable way to allocate labor cost per project and cost center.
- **A:** I diagnosed that the gap was a missing process, not a missing report. I built a Power Apps canvas app inside Teams where people logged % of time per project, with an approval flow for directors (approve / request revision), then merged it with payroll data and redesigned the ERP cost accounting around it.
- **R:** First accurate project-level labor cost; it fed the budgeting cycle and KPI dashboards I introduced as CFO.
- **Use for:** "How do you diagnose root causes?", "Operating model change".

### STAR 3 — SIENGE ERP rollout *(change management, adoption)*
- **S:** Company-wide move to a new ERP, starting from finance.
- **T:** Lead the rollout and bring every department onto it.
- **A:** I mapped processes across departments first, fixed bottlenecks before configuring, aligned the ERP to the new workflows, and ran training per sector.
- **R:** Deployed and adopted company-wide; part of the transformation that saved 120+ manual hours/month in financial reporting and improved revenue forecast accuracy by ~30%.
- **Use for:** "Technology deployed but not adopted", "Resistance to change".

### STAR 4 — Pricing methodology *(evidence-based argument)*
- **S:** ~90 proposals per year, inconsistent pricing, uneven win rate.
- **T:** Make pricing objective and faster.
- **A:** I built a pricing model from historical data: project type, size, historical labor, risk; later automated parts with n8n. I presented it to the partners with the data behind each factor.
- **R:** Win rate up 18%, bid preparation time down ~30%.
- **Use for:** "Influencing senior stakeholders", "Data-driven decision".

### STAR 5 — CentralOps / agents with guardrails *(building alone, reliable AI)*
- **S:** I wanted to prove an AI-native ERP for retail could be safe enough for real operations.
- **T:** Build it alone, with agents that can't do damage.
- **A:** ~95k lines, 8 ADRs, 133 migrations, 2,000+ pgTAP tests. Agents act only through an MCP server with 16 tools mapped to scoped database functions and signed JWT context; a deterministic validator checks every LLM tool output against the database before it executes; human approval for sensitive actions.
- **R:** A working platform with agents for customers and staff, built solo with AI-assisted engineering.
- **Use for:** "When is AI a distraction?", "How do you handle hallucinations?", "Working without an engineering team".

### STAR 6 — Lagoas do Norte (World Bank) *(stakeholders, scale)*
- **S:** A World Bank–financed urban program with many disciplines and public/private stakeholders.
- **T:** General coordinator and technical lead.
- **A:** I directed the integrated design (sewerage for 312k+ people, drainage, water, 1 MW biogas, BIM urban models) and ran stakeholder coordination and delivery baselines.
- **R:** Delivered the integrated design; it became my reference for managing complex, multi-party programs.
- **Use for:** "Largest project you led", "Conflicting stakeholders".

### Failure / lesson question (prepare it!)
Suggestion: in the AP pipeline, the first version misclassified rare items. **Lesson:** I started with a human reviewing 100% plus the example loop; never trust the model before measuring. It became a principle: *baseline first, measure, then automate*.

## 4. How to answer hard skills questions

**Rule:** each skill = 1 sentence on what it is + 1 concrete example of yours + when **not** to use it. That shows seniority and is exactly the role's "AI vs. distraction" point.

| Likely question | Answer line |
|---|---|
| Which LLMs/APIs have you used? | Multi-provider routing (OpenAI, Anthropic, Gemini) via API; choose by cost/latency/quality per task; structured outputs and tool calling. |
| What's MCP / tool calling? | The model calls defined tools instead of free text; I expose only scoped DB functions so the agent can't go beyond its role. |
| How do you avoid hallucinations? | Ground in source data, deterministic validation before execution, human-in-the-loop for high-impact actions, measure accuracy against a baseline. |
| How fast can you build a POC? | Days, not weeks: n8n/low-code for workflow, Python/FastAPI when logic is complex. The goal is to run on the client's real data in their real process. |
| Low-code vs. code? | Low-code (n8n, Power Platform, Copilot) for fast adoption and handover to the client; code when it needs tests, scale or security. |
| How do you measure ROI? | Baseline before (hours, errors, cycle time, cost), same metric after, attribute carefully; adoption rate is a leading indicator. |
| Process / operating model? | Map current state end-to-end, find handoffs/decision rights/tooling gaps, design target state with RACI, governance and KPIs, then pilot. |
| Stack | Python (FastAPI), TypeScript/Next.js, PostgreSQL, Docker, GitHub Actions, n8n, Power Apps/Automate, SharePoint. |

**If you don't know something** (e.g., a client-specific tool):
> I haven't used X in production, but I've used Y, which solves the same problem. Here's how I'd get productive in the first week…

## 5. How to answer soft skills questions

**Rule:** never say just the adjective ("I'm a good communicator"). Always: behavior → example → effect.

- **Executive communication:** "As CFO I presented to partners monthly. I lead with the decision they need to make, then the evidence, then the detail if they ask."
- **Influencing skeptics:** "I don't argue with slides, I show a working demo on their own data. A skeptical director changes their mind faster with a prototype than with a roadmap." *(bridge to STAR 1/4)*
- **Autonomy:** "I built CentralOps alone, but I know when to pull people in — in the BIM rollout I hired external trainers instead of trying to do everything myself."
- **Diagnosis before solution:** "In the labor cost case, the easy answer was a new report. The real problem was a missing process, so I fixed the process first."
- **Accountability:** "I care about the number after, not the deliverable. That's why I measure a baseline before I start."
- **Change / resistance:** "Adoption is a process design problem, not a training problem: I map who loses and who gains, involve them early, and train per role." *(STAR 3)*
- **Remote / cultural fit:** lived and worked in the US, C1 English; used to async work and written documentation (ADRs).

## 6. Likely tough questions

- **"You were a CFO, why go back to hands-on?"** → "Because I saw transformation fail when strategy and building are separated. I want to be the person who closes that gap — that's what an FDE is."
- **"Your AI experience is recent."** → "Recent as a full-time focus, but I was already shipping LLM automations in production as CFO, and since then I've built systems end-to-end with tests and guardrails."
- **"Salary expectation?"** → Use the figure from your search plan, in USD, as a range: "Based on the scope, I'm looking at a range of X to Y USD, flexible for the right engagement."
- **"Availability?"** → Be direct about start date and time zone (UTC−3, good overlap with New York hours).

## 7. 10-minute checklist before
- [ ] Open this page, the tailored CV and the LinkedIn job post.
- [ ] Rehearse the 60-second pitch out loud twice.
- [ ] Pick 3 main STARs: **1 (AI AP), 2 (labor allocation), 5 (guardrails)**.
- [ ] Have a prototype ready to screen-share if asked (CentralOps or an n8n workflow).
- [ ] Camera, audio, water, quiet room.

---

# PARTE 2 — PORTUGUÊS

## 1. Sobre a empresa

**Truelogic** (sede em Nova York) é uma empresa de *nearshore staff augmentation*: aloca profissionais da América Latina em projetos de empresas dos EUA. Mais de 20 anos no mercado, 600+ profissionais em 25+ países, clientes de startups a Fortune 500.

- **Modelo:** você é contratado pela Truelogic e trabalha embutido no time do cliente. Remoto, pagamento em USD, autonomia de horário, foco em resultado.
- **Cultura que eles vendem:** bem-estar, times sêniores, rede multicultural latino-americana.
- **Cliente final (não nomeado):** uma rede global de tecnologia + design criativo que faz transformação de negócio para grandes marcas, falando direto com a liderança executiva e cobrindo toda a jornada do cliente. Pense em uma grande agência/consultoria digital.

**O que isso significa para a entrevista:** a primeira conversa costuma ser com recrutador(a) da Truelogic (fit, inglês, salário, disponibilidade). Depois vem o cliente (técnico + consultivo). Mostre que você se adapta ao cliente e se comunica bem com americanos.

**Perguntas para fazer a eles:**
1. Quem é o cliente e como é um projeto típico de FDE — duração, time, para quem eu reportaria?
2. Qual é o primeiro problema que vocês querem que essa pessoa resolva nos primeiros 90 dias?
3. Qual stack de IA o cliente usa como padrão (OpenAI/Anthropic, Copilot Studio, n8n etc.)?
4. Como o sucesso de um FDE é medido — adoção, ROI, número de protótipos?
5. Quais são os próximos passos do processo, e a entrevista com o cliente é separada?

## 2. Sobre a vaga

**Em uma frase:** metade consultor de gestão, metade engenheiro de IA. Você entra no cliente, diagnostica o processo, redesenha a operação e **prova o valor construindo um protótipo de IA que funciona** — sem time de engenharia dedicado.

| O que pedem | Sua prova |
|---|---|
| 5–10 anos em consultoria / transformação | 15+ anos na MPB: Engenheiro Sênior → CFO; consultor independente |
| 2+ áreas: desenho organizacional, modelo operacional, gestão da mudança, engenharia de processos, habilitação tecnológica | Todas: ERP SIENGE, BIM, orçamento/KPIs, migração SharePoint, rateio de custos |
| Argumentos estruturados para executivos | ~90 propostas/ano, modelos de fluxo de caixa descontado para prefeituras, dashboards para diretoria |
| Construir workflows/protótipos de IA de verdade | n8n + LLM no contas a pagar, CentralOps (MCP, 16 ferramentas, guardrails), trading copilot |
| Trabalhar sozinho, sabendo quando pedir ajuda | CentralOps ~95 mil linhas sozinho, 2.000+ testes; contratou consultores de BIM quando precisou |
| Diagnóstico antes da solução | Mapeamento de processos antes do ERP; achou a causa do custo de mão de obra mal rateado |
| Preferência por protótipo em vez de roadmap | App de rateio em Power Apps no Teams; pipeline de contas a pagar com ciclo de feedback |

**Pitch de 60 segundos (decore a estrutura, não as palavras):**

> Sou um engenheiro que virou CFO e depois engenheiro de IA aplicada. Por 15 anos na MPB Engenharia conduzi grandes programas de consultoria — incluindo um programa urbano financiado pelo Banco Mundial — e como Diretor Financeiro liderei a transformação do modelo operacional e digital da empresa: orçamento e KPIs, um novo ERP, rateio de custo por timesheet e automações de IA com n8n e APIs de LLM. Desde 2026 construo sistemas de IA com a mão na massa: um ERP nativo em IA com agentes MCP e guardrails determinísticos, bots de workflow, ferramentas de previsão. Então o que trago para a função de FDE são as duas metades: consigo sentar com executivos e diagnosticar onde o processo quebra, e depois construir eu mesmo o protótipo funcionando, em dias, para provar o valor.

**Por que essa vaga?**
> É exatamente a interseção do que eu já fiz: já fui o dono do negócio que precisava de transformação e já fui quem construiu a solução. A maioria das vagas pede um lado só. Esta pede os dois, e é aí que eu agrego mais valor.

## 3. Casos STAR (use 4–5; escolha conforme a pergunta)

> Dica: ~2 minutos cada. Situação e tarefa curtas (20%), ação com "eu" (60%), resultado com número (20%). Feche com o que aprendeu.

### STAR 1 — Automação de contas a pagar com IA *(protótipo de IA, adoção, ROI)*
- **S:** Os documentos de contas a pagar chegavam por e-mail, Teams e WhatsApp; o financeiro extraía os dados e mapeava os centros de custo à mão.
- **T:** Centralizar o recebimento e automatizar a extração e a classificação pelo plano de contas.
- **A:** Construí um pipeline no n8n: os funcionários colocam os arquivos numa pasta, o Docling converte em Markdown (ou a imagem vai direto para o modelo), o LLM recebe os centros de custo ativos e o plano de contas e preenche uma planilha para revisão humana. Um workflow mensal devolve as classificações confirmadas ao prompt como exemplos. Depois comecei a integração direta via API com o ERP.
- **R:** A digitação manual caiu drasticamente; a precisão melhorou mês a mês graças ao ciclo de feedback; a equipe passou a revisar em vez de digitar.
- **Use para:** "Fale de um protótipo de IA que você construiu", "Como você mantém o humano no processo?"

### STAR 2 — Rateio do custo de mão de obra *(diagnóstico de causa raiz, modelo operacional)*
- **S:** A mão de obra era o maior custo, mas não era rateada entre os projetos — a diretoria não tinha a margem real por projeto.
- **T:** Criar uma forma confiável de ratear o custo de mão de obra por projeto e centro de custo.
- **A:** Diagnostiquei que faltava um processo, não um relatório. Construí um app Power Apps (canvas) dentro do Teams onde as pessoas registravam o % de tempo por projeto, com fluxo de aprovação dos diretores (aprovar / pedir revisão), cruzei com os dados da folha e redesenhei a contabilidade de custos do ERP em torno disso.
- **R:** Primeiro custo de mão de obra preciso por projeto; alimentou o ciclo orçamentário e os dashboards de KPIs que implantei como CFO.
- **Use para:** "Como você diagnostica causas raiz?", "Mudança de modelo operacional".

### STAR 3 — Implantação do ERP SIENGE *(gestão da mudança, adoção)*
- **S:** Migração da empresa inteira para um novo ERP, começando pelo financeiro.
- **T:** Liderar a implantação e trazer todos os setores para o sistema.
- **A:** Mapeei os processos de todos os setores primeiro, resolvi os gargalos antes de configurar, alinhei o ERP aos novos fluxos e fiz treinamentos por setor.
- **R:** Implantado e adotado na empresa toda; parte da transformação que economizou 120+ horas manuais/mês em relatórios financeiros e melhorou a precisão da previsão de receita em ~30%.
- **Use para:** "Tecnologia implantada mas não adotada", "Resistência à mudança".

### STAR 4 — Metodologia de precificação *(argumento baseado em evidências)*
- **S:** ~90 propostas por ano, preços inconsistentes, taxa de vitória irregular.
- **T:** Tornar a precificação objetiva e mais rápida.
- **A:** Construí um modelo de preço com dados históricos: tipo de projeto, porte, mão de obra histórica, risco; depois automatizei partes com n8n. Apresentei aos sócios com os dados por trás de cada fator.
- **R:** Taxa de vitória +18%, tempo de preparação de propostas −30%.
- **Use para:** "Influenciar stakeholders sêniores", "Decisão baseada em dados".

### STAR 5 — CentralOps / agentes com guardrails *(construir sozinho, IA confiável)*
- **S:** Eu queria provar que um ERP nativo em IA para o varejo podia ser seguro o suficiente para a operação real.
- **T:** Construí-lo sozinho, com agentes que não conseguem causar estrago.
- **A:** ~95 mil linhas, 8 ADRs, 133 migrations, 2.000+ testes pgTAP. Os agentes só agem por um servidor MCP com 16 ferramentas ligadas a funções de banco com escopo restrito e contexto JWT assinado; um validador determinístico confere cada saída do LLM contra o banco antes de executar; aprovação humana para ações sensíveis.
- **R:** Plataforma funcionando, com agentes para clientes e funcionários, construída sozinho com engenharia assistida por IA.
- **Use para:** "Quando a IA é distração?", "Como lida com alucinações?", "Trabalhar sem time de engenharia".

### STAR 6 — Lagoas do Norte (Banco Mundial) *(stakeholders, escala)*
- **S:** Programa urbano financiado pelo Banco Mundial, com muitas disciplinas e stakeholders públicos e privados.
- **T:** Coordenador geral e líder técnico.
- **A:** Dirigi o projeto integrado (esgoto para 312 mil+ pessoas, drenagem, água, biogás de 1 MW, modelos urbanos em BIM) e conduzi a coordenação dos stakeholders e as linhas de base de entrega.
- **R:** Projeto integrado entregue; virou minha referência para gerir programas complexos com muitas partes.
- **Use para:** "Maior projeto que liderou", "Stakeholders em conflito".

### Pergunta de fracasso / aprendizado (prepare!)
Sugestão: no pipeline de contas a pagar, a primeira versão classificava errado itens raros. **Aprendizado:** comecei com humano revisando 100% e o ciclo de exemplos; não confie no modelo antes de medir. Virou princípio: *primeiro a linha de base, depois medir, depois automatizar*.

## 4. Como responder sobre hard skills

**Regra:** cada skill = 1 frase do que é + 1 exemplo concreto seu + quando **não** usar. Isso mostra senioridade e é exatamente o ponto "IA vs. distração" da vaga.

| Pergunta provável | Linha de resposta |
|---|---|
| Quais LLMs/APIs você usou? | Roteamento entre provedores (OpenAI, Anthropic, Gemini) via API; escolho por custo/latência/qualidade por tarefa; saídas estruturadas e tool calling. |
| O que é MCP / tool calling? | O modelo chama ferramentas definidas em vez de texto livre; exponho só funções de banco com escopo, para o agente não ir além do papel dele. |
| Como evita alucinações? | Base nos dados de origem, validação determinística antes de executar, humano no processo para ações de alto impacto, medir a precisão contra uma linha de base. |
| Em quanto tempo faz uma POC? | Dias, não semanas: n8n/low-code para o fluxo, Python/FastAPI quando a lógica é complexa. O objetivo é rodar com os dados reais do cliente, no processo real dele. |
| Low-code ou código? | Low-code (n8n, Power Platform, Copilot) para adoção rápida e entrega ao cliente; código quando precisa de testes, escala ou segurança. |
| Como mede ROI? | Linha de base antes (horas, erros, tempo de ciclo, custo), mesma métrica depois, atribuição cuidadosa; a taxa de adoção é o indicador antecedente. |
| Processo / modelo operacional? | Mapear o estado atual de ponta a ponta, achar falhas de passagem/direitos de decisão/ferramentas, desenhar o estado futuro com RACI, governança e KPIs, e pilotar. |
| Stack | Python (FastAPI), TypeScript/Next.js, PostgreSQL, Docker, GitHub Actions, n8n, Power Apps/Automate, SharePoint. |

**Se não souber algo** (ex.: uma ferramenta específica do cliente):
> Não usei X em produção, mas usei Y, que resolve o mesmo problema. Veja como eu ficaria produtivo na primeira semana…

## 5. Como responder sobre soft skills

**Regra:** nunca diga só o adjetivo ("sou bom comunicador"). Sempre: comportamento → exemplo → efeito.

- **Comunicação com executivos:** "Como CFO eu apresentava aos sócios todo mês. Começo pela decisão que eles precisam tomar, depois a evidência, depois o detalhe se pedirem."
- **Influenciar céticos:** "Não discuto com slides, mostro uma demo funcionando nos dados deles. Um diretor cético muda de ideia mais rápido com um protótipo do que com um roadmap." *(ponte com STAR 1/4)*
- **Autonomia:** "Construí o CentralOps sozinho, mas sei quando chamar gente — na implantação do BIM contratei instrutores externos em vez de tentar fazer tudo."
- **Diagnóstico antes da solução:** "No caso do custo de mão de obra, a resposta fácil era um relatório novo. O problema real era a falta de um processo, então corrigi o processo primeiro."
- **Responsabilidade pelo resultado:** "Me importo com o número depois, não com o entregável. Por isso meço a linha de base antes de começar."
- **Mudança / resistência:** "Adoção é um problema de desenho de processo, não de treinamento: mapeio quem perde e quem ganha, envolvo cedo e treino por função." *(STAR 3)*
- **Remoto / cultura:** morou e trabalhou nos EUA, inglês C1; acostumado a trabalho assíncrono e documentação escrita (ADRs).

## 6. Perguntas difíceis prováveis

- **"Você foi CFO, por que voltar ao operacional?"** → "Porque vi transformações falharem quando estratégia e construção ficam separadas. Quero ser quem fecha essa lacuna — é isso que um FDE é."
- **"Sua experiência com IA é recente."** → "Recente como foco integral, mas eu já colocava automações com LLM em produção como CFO, e desde então construí sistemas de ponta a ponta com testes e guardrails."
- **"Pretensão salarial?"** → Use o valor do seu plano de busca, em USD, como faixa: "Pelo escopo, busco uma faixa de X a Y USD, flexível para o projeto certo."
- **"Disponibilidade?"** → Seja direto sobre data de início e fuso (UTC−3, boa sobreposição com o horário de Nova York).

## 7. Checklist de 10 minutos antes
- [ ] Abrir esta página, o CV da vaga e a vaga no LinkedIn.
- [ ] Ensaiar o pitch de 60s em voz alta 2x.
- [ ] Escolher 3 STARs principais: **1 (contas a pagar com IA), 2 (rateio), 5 (guardrails)**.
- [ ] Ter um protótipo pronto para compartilhar a tela, se pedirem (CentralOps ou um workflow n8n).
- [ ] Câmera, áudio, água, ambiente silencioso.
