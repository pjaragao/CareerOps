# 🚀 CareerOps — AI-Powered Career Automation

<div align="center">

**Automate your job search. Optimize your LinkedIn. Land interviews faster.**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Chrome](https://img.shields.io/badge/Chrome_Extension-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)](https://developer.chrome.com/docs/extensions/)

</div>

---

## ✨ Features

### 🔌 Browser Extension
- **One-click job capture** from any LinkedIn job page
- **Smart profile import** with multi-page navigation (experience, education, skills)
- **AI-powered extraction** — sends raw page text to backend for structured parsing
- Auto-syncs with backend via REST API

### 🤖 Modular AI Skills Engine
- **Template-driven architecture** using Jinja2 for all AI prompts
- **Isolated Skill folders** (`profile`, `jobs`, `interview`, `analytics`) for easy prompt maintenance
- **Dynamic AI model mapping** — assign specific models to each skill domain via Settings
- **Common rule inheritance** — centralized anti-hallucination and output format rules
- Multi-provider support: **Gemini**, **NVIDIA NIM**, **Alibaba Cloud**, **Ollama**

### 🧠 Knowledge Base Stack & Workflow
- **High-Fidelity Parsing**: Uses **MarkItDown** to convert PDF, DOCX, and XLSX into clean Markdown, preserving document structure for better AI comprehension.
- **AI-Powered Extraction**: Modular skills analyze raw text to extract professional facts, skills, and structured **STAR Cases** (Situation, Task, Action, Result).
- **Human-in-the-Loop Validation**: A dedicated Validation Wizard allows users to review, edit, and approve AI-extracted data before it enters the knowledge base.
- **Intelligent Consolidation**: Automatically merges and de-duplicates information from multiple sources into a single, persistent `user_data.md` "source of truth".
- **Dynamic Context Injection**: Grounded AI responses via Jinja2 `{% include %}` — your validated history is automatically injected into interview prep, job matching, and LinkedIn optimization prompts.

### 🧭 Five screens
- **Início** — what to do today: drafts to review, comments and invites against targets, applications in progress
- **Meu Perfil** — profile data and the two master CVs (Brazil PT / abroad EN), the knowledge base, and the LinkedIn texts in both languages
- **Vagas** — job list and Kanban (Applied → Interview → Offer); per job: tailored CV, cover letter, DM, chat and PDF; interview prep (STAR stories)
- **LinkedIn Copilot** — posts, engagement, prospecting and metrics (below)
- **Configurações** — AI keys/models and the extension install guide

### 📣 LinkedIn Copilot (human-in-the-loop)
- **Two markets** — Brazil (Portuguese: engineering, sanitation, technical-financial modeling) and abroad (English: data, finance, modeling), with a master CV for each in `config/`
- **Post drafts** — AI writes posts per market from your knowledge base and fresh notes, rotating each market's content pillars
- **Approve → publish** — only posts you approve go out, through the official LinkedIn API (`w_member_social`), now or at a scheduled time; max posts per day is capped
- **Engagement queue** — capture posts while browsing (extension: right-click → *Enviar ao CareerOps Copilot*); AI scores relevance and drafts a specific comment; you comment on LinkedIn and tick it off
- **Prospecting** — capture profiles; AI scores fit and drafts a ≤300-char connection note; track invited → accepted → replied against a weekly target
- **Weekly metrics** — posts, comments and invites counted automatically, plus profile views / impressions / recruiter messages entered from LinkedIn analytics
- **Profile filler (EN + PT)** — extension panel *CareerOps · Perfil* on linkedin.com with the approved headline, About, positions and projects in both languages (`config/linkedin_profile.json`, built by `international/build_linkedin_profile.py`); click a LinkedIn field, press *Inserir*, review and Save
- **LinkedIn assist (extension)** — `✨ Comentário IA` on every post (drafts and fills the comment box; clicking Publicar marks it done), `🤝 Convite IA` on profiles (scores fit and fills the invite note; clicking Enviar marks it invited), `⭐ Avaliar pessoas da página` on search and My Network (scores everyone visible in one AI call and saves good fits with a ready note)
- **Easy Apply assistant (extension)** — `✨ Preencher com IA` inside LinkedIn's Easy Apply: fills each step from `config/easy_apply.yml` (contact, work authorization, years of experience, salary) and the CV in the job's language; demographic questions and anything unknown are left for you (orange). You review, click Next and Submit; the job is marked applied on submit
- **Line of thought** — every comment and thread reply you send (extension), every published post and every message marked as sent is recorded with its topic, the stance it takes and the request you gave the AI; Copilot → *Linha de pensamento* consolidates them into a list of positions you edit. Every comment, reply, post and DM prompt gets those positions plus the records closest to the subject (and the ones you pin), so everything reads as the same person
- **Networking from the jobs** — Copilot → *Networking*: from the jobs in the system (applied first, then the last 45 days) the AI suggests companies to follow, people to connect with or follow (as LinkedIn search links: score them with `⭐ Avaliar pessoas da página`), recent posts to join with the angle to bring, and a first message for connections who accepted; accepted prospects also get a *Mensagem* button
- **Saved topics** — `📌 Salvar tema` on any post stores it as a topic of interest; the Copilot's Posts tab turns it into a post of yours on the same theme (never copying it)
- **AI writing style and models** — Configurações → Estilo e modelos: per kind of text (posts, comments, invites, Easy Apply, CV/cover letter, messages) a preset plus tone, formality, length, emojis, hashtags and extra instructions, or "Ajustar com IA" from a plain-language request; the language always follows the content; comments avoid repeating the post's other comments and your own recent ones. With AGY: posts on Argon High, style adjust on Argon Medium, writing on Flash Medium, routine tasks on Flash Low, with automatic fallback when a model's quota runs out
- **Job pages** — `📥 CareerOps` next to LinkedIn's Save (and Save imports automatically); `📥 Importar vagas salvas` on the Job tracker
- **No bots**: nothing likes, comments, follows or connects on your behalf — that violates LinkedIn's User Agreement and gets accounts restricted

---

## 🏗️ Architecture

```
Chrome Extension ──▶ FastAPI Backend (Skills + Jinja2) ──▶ PostgreSQL (JSONB)
                          │                   ▲
                    React Dashboard ──────────┘
                          │
                    Gotenberg (PDF)
```

| Component | Tech | Port |
|-----------|------|------|
| Frontend | React 18 + Vite + TypeScript | 5173 |
| Backend | FastAPI + Python 3.12 + Jinja2 | 8005 |
| Database | PostgreSQL 15 (Supabase/Local) | 5432 |
| AI Engine | SkillService (Modular Templates) | — |
| Parsing Engine | MarkItDown (Markdown) | — |
| PDF Engine | Gotenberg 8 | 3002 |

---

## 🚀 Quick Start

### Prerequisites
- Docker + Docker Compose
- Supabase (self-hosted or cloud)
- Gemini API key (or another AI provider)
- Chrome browser (for the extension)

### 1. Clone & Configure

```bash
git clone https://github.com/pjaragao/linkedin_resume.git
cd linkedin_resume

# Copy and fill environment variables
cp .env.example .env
# Edit .env with your Supabase credentials and AI API keys
```

### 2. Start Services

```bash
# Start the full stack
docker compose up --build -d
```

---

## 🔧 AI Skills Configuration

### Per-Domain Model Mapping

Configure different AI models for each domain in the Settings page. The `SkillService` automatically routes requests based on the prompt folder:

| Domain (Folder) | Setting Key | Recommended |
|-----------------|-------------|-------------|
| `profile/` | `ai_model_profile` | gemini-1.5-pro |
| `jobs/` | `ai_model_jobs` | gemini-1.5-pro |
| `interview/` | `ai_model_interview` | gemini-1.5-flash |
| `onboarding/` | `ai_model_onboarding` | gemini-1.5-pro |
| `analytics/` | `ai_model_analytics` | gemini-1.5-flash |
| `common/` | `ai_model_chat` | gemini-1.5-flash |

---

## 📁 Project Structure

```
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── services/ # Business logic (SkillService, ProfileService...)
│   │   ├── skills/   # 🤖 AI Prompt Templates (.md)
│   │   └── api/      # REST Endpoints
├── frontend/         # React dashboard
├── extension/        # Chrome extension
├── docs/             # Documentation
│   └── SYSTEM.md     # Full technical specification
└── docker-compose.yml
```

> 📖 See [docs/SYSTEM.md](docs/SYSTEM.md) for the complete system architecture and development guidelines.

---

## 🔄 Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Extension
Load the `extension/` folder as an unpacked extension in Chrome.

---

## 📝 Contributing

1. Read `docs/SYSTEM.md` before making changes
2. When adding/removing features, update `docs/SYSTEM.md`
3. Follow the AI prompt guidelines in the system docs
4. Test extension changes on both profile and job pages

---

## 📄 License

Private project — All rights reserved.

---

<div align="center">
  <sub>Built with ❤️ by Paulo Aragão — Powered by AI</sub>
</div>
