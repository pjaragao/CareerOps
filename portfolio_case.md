# 🚀 Case de Estudo: CareerOps — AI-Powered Career Automation

## 📌 Visão Executiva
O **CareerOps** é uma plataforma avançada de automação de carreiras orientada a Inteligência Artificial, desenvolvida para redefinir a forma como profissionais gerenciam sua presença no mercado e seu pipeline de oportunidades. Atuando como um verdadeiro *copiloto de carreira*, a aplicação unifica a extração de dados do LinkedIn, a otimização algorítmica de perfis e a engenharia de currículos ATS-friendly. Com um ecossistema modular e distribuído, o sistema transforma o processo historicamente caótico e manual de *job hunting* em uma esteira de dados inteligente, preditiva e altamente escalável.

## 🎯 Público-Alvo e Modelo de Negócio
- **Público-Alvo**: Profissionais de tecnologia, executivos e talentos que buscam otimizar seu posicionamento no mercado, além de necessitarem de uma gestão estruturada de múltiplas aplicações simultâneas (via Kanban).
- **Proposta de Valor**: Redução exponencial do tempo gasto com preenchimento de formulários, adaptação de currículos por vaga e preparação de entrevistas, entregando uma vantagem competitiva técnica através de insights gerados por IA.
- **Modelo de Atuação**: Ferramenta de produtividade pessoal de altíssima performance (*B2C premium*), desenhada com arquitetura *self-hosted* em infraestrutura Docker, possuindo flexibilidade nativa para expansão em modelos SaaS (Software as a Service) no futuro.

## 🛑 O Problema Resolvido (The Challenge)
O processo moderno de recrutamento é assimétrico: enquanto as empresas utilizam ATS (*Applicant Tracking Systems*) e IAs corporativas para filtrar milhares de candidatos em segundos, o profissional ainda adapta currículos, audita seu perfil e rastreia vagas em planilhas estáticas e manuais. 

As **principais dores** resolvidas pelo CareerOps foram:
- **Ineficiência Operacional e Fadiga**: O trabalho repetitivo de ler descrições longas de vagas (JDs) e cruzá-las manualmente com as experiências do candidato.
- **Falta de Estrutura de Dados**: O histórico do profissional frequentemente fica fragmentado em PDFs, arquivos DOCX e perfis online desatualizados.
- **Subjetividade na Preparação**: A dificuldade analítica em construir casos no formato **STAR** (Situação, Tarefa, Ação, Resultado) que estejam perfeitamente alinhados ao que uma vaga específica exige.

## 🏗️ Arquitetura e Tech Stack
O sistema foi desenhado sob uma ótica de Arquitetura Orientada a Serviços (SOA), garantindo total desacoplamento entre a ingestão de dados (edge), o processamento heurístico (backend) e a experiência de usuário.

- **Frontend**: **React 18 + TypeScript + Vite**. Escolhidos pela reatividade imediata e tipagem estática robusta. A interface é focada em usabilidade e produtividade (Drag-and-drop Kanban, Dashboards e interações assíncronas).
- **Backend (Core API)**: **FastAPI (Python 3.12)**. Adotado por sua altíssima performance e natureza assíncrona nativa, característica fundamental para orquestrar requisições pesadas de IA e I/O de rede sem gargalos.
- **Banco de Dados**: **PostgreSQL 15 (Supabase)** utilizando extensivamente o tipo de dado **JSONB**. Essa decisão arquitetural garantiu flexibilidade de schema para persistir respostas imprevisíveis de LLMs e metadados dinâmicos de vagas.
- **Infraestrutura e PDF Engine**: Containerização completa via **Docker e Docker Compose**. Integrado com o **Gotenberg 8** atuando como um motor *headless* para conversão precisa de HTML em PDF on-the-fly.
- **Ingestão de Dados (Edge)**: **Chrome Extension (Manifest V3)**. O web scraper roda client-side, dentro do browser do usuário.

## 🧠 Integrações, APIs e IA
A "joia da coroa" do projeto é o seu **Modular AI Skills Engine**, uma pipeline de processamento de Inteligência Artificial agnóstica de provedor e desenhada para evitar acoplamento rígido.

- **Orquestração de Prompts com Jinja2**: Em vez de manipular strings *hardcoded* ou frameworks pesados como LangChain, o sistema utiliza templates Markdown (`.md`) enriquecidos com a sintaxe Jinja2. Isso permite a injeção dinâmica de contexto (ex: `{% include 'user_context.md' %}`) diretamente nas chamadas de inferência.
- **Multi-Provider AI**: Arquitetura resiliente que roteia requisições de acordo com a complexidade do domínio — utilizando **Gemini (1.5 Pro/Flash)** para processamento rápido ou raciocínio denso, mantendo suporte plug-and-play para **NVIDIA NIM, Alibaba Cloud e modelos locais via Ollama**.
- **Parsing de Alta Fidelidade**: Integração com a engine **MarkItDown** para ingestão de documentos (PDFs e DOCXs), convertendo-os em um Markdown semanticamente limpo antes de alimentar os embeddings e prompts.
- **Human-in-the-Loop (HITL)**: Implementação de um *Validation Wizard*. A IA não realiza escritas diretas no banco de dados de conhecimento. Ela processa o dado cru, gera uma estrutura "candidata", e submete a aprovação do usuário, garantindo integridade absoluta da "Fonte da Verdade".

## ⚙️ Soluções e Funcionalidades Core
- **Knowledge Base Unificada**: Consolidação de todo o histórico profissional, educacional e de portfólio em um único repositório (*user_data.md*), alimentado de forma orgânica pela extensão e por uploads manuais.
- **LinkedIn Profile Optimizer**: Uma suíte investigativa que realiza uma auditoria profunda do LinkedIn. Ela gera um Score (0-100), simulador de SSI (*Social Selling Index*), criador iterativo de *Headlines* e um otimizador de *Experience bullets* que foca exclusivamente em verbos de ação e impacto quantificável.
- **One-Click Job Capture & Pipeline Tracker**: A extensão de browser captura a árvore do DOM de uma vaga no LinkedIn em um clique e injeta os metadados via REST API. O dashboard React processa essas vagas e as expõe em um quadro Kanban gerencial (Applied → Screening → Interview → Offer).
- **ATS Match & Skills Gap Analysis**: Cruzamento vetorial e semântico entre o repositório de dados do candidato e a *Job Description*, identificando com precisão cirúrgica quais palavras-chave faltam para o candidato avançar nos filtros automatizados.
- **Entrevistas Preditivas (STAR+R)**: Agente proativo que avalia a cultura da empresa e o descritivo da vaga para sugerir perguntas comportamentais de alta probabilidade, elaborando rotetizações de respostas baseadas estritamente no passado validado do usuário.

## 🧗 Desafios Técnicos Superados

### 1. Evasão de Bloqueios e Web Scraping Escalável
**O Desafio**: Plataformas como o LinkedIn possuem mecanismos militares de anti-scraping. Tentativas de automatizar autenticações ou varreduras utilizando *headless browsers* (Playwright/Puppeteer) no backend resultavam em bloqueios severos (*shadowbans*) e quebra constante de contratos de página.
**A Solução de Engenharia**: Implementação de uma arquitetura estrita **"Extension-First"**. O backend foi totalmente destituído da responsabilidade de navegação. Toda a ingestão de dados foi movida para uma Extensão Chrome (Manifest V3). Assim, a extração do DOM ocorre no contexto do cliente (*client-side*), reaproveitando os *cookies* nativos e a sessão já autenticada do usuário. A extensão realiza o trabalho pesado e despacha apenas um *payload* JSON sanitizado para o FastAPI. Isso zerou o custo operacional com proxies rotativos e garantiu estabilidade de 100%.

### 2. Contenção de Alucinações de LLM e Context Isolation
**O Desafio**: Transmitir todo o histórico de um candidato juntamente com uma descrição extensa de vaga para um modelo fundacional resultava em perda de atenção (*lost in the middle*), alucinações graves (a IA inventava vivências) e estouro do limite de tokens de contexto.
**A Solução de Engenharia**: O desenvolvimento de um ecossistema de **Domain-Driven Prompts**. A monolítica chamada de IA foi refatorada em dezenas de *skills* isoladas (`profile/`, `jobs/`, `interview/`). A pipeline quebra o processamento: primeiro extrai apenas os requisitos core da vaga, e em seguida cruza exclusivamente com as "habilidades" mapeadas do candidato. A injeção injetada via Jinja2 garante que o LLM processe apenas o fragmento exato necessário. Além disso, o sistema ganhou *Dynamic Model Routing*, delegando tarefas de otimização criativa para modelos densos (`gemini-1.5-pro`) e tarefas de extração estruturada para modelos ágeis e determinísticos (`gemini-1.5-flash`), barateando custos e eliminando completamente as alucinações.
