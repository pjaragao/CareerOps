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

### 🧠 AI Onboarding & Knowledge Base
- **Document Repository**: Upload resumes, cover letters, and project descriptions.
- **MarkItDown Integration**: High-fidelity conversion of PDF, DOCX, and XLSX to Markdown for AI processing.
- **Validation Wizard**: Review and approve AI-extracted facts before they join the Knowledge Base.
- **Prompt Injection**: Automatically enriches LinkedIn optimization, interview prep, and resume tailoring with validated knowledge.
- **Base Resume Optimization**: AI-suggested improvements to your `resume_base.md` based on new achievements.

### 📊 LinkedIn Profile Optimizer
- **PostgreSQL JSONB storage** — definitive source of truth for all profile data
- **Profile Sync Alerts** — detect when your LinkedIn data has changed and needs a fresh AI audit
- **One-click Full Audit** — comprehensive AI analysis of Score, SSI, Headlines, Bio, Experiences, and Skills in one step
- **Profile audit** with strength score (0-100)
- **SSI Score simulator** across 4 LinkedIn pillars
- **Headline builder** with LinkedIn preview mockup
- **Bio/Summary optimizer** — side-by-side original vs AI-enhanced
- **Experience bullet rewriter** — action verbs + quantified impact
- **Skills gap analysis** — keep/add/remove recommendations
- **ATS match checker** — paste a job description and compare

### 📋 Application Tracking
- **Kanban board** with drag-and-drop (Applied → Screening → Interview → Offer)
- **Job evaluation** — multi-dimensional scoring (match, north star, compensation, culture)
- **Interview prep** — STAR+R story bank with auto-generation
- **Pipeline queue** — URL-based job import queue

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
