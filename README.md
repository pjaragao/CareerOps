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

### 🤖 AI Resume & Cover Letter Engine
- **ATS-optimized resume generation** using Google's XYZ formula
- **Clean cover letters** (no markdown, ready to paste)
- **Chat assistant** for answering employer form questions
- **Outreach generator** for LinkedIn DMs and emails
- Multi-provider support: **Gemini**, **NVIDIA NIM**, **Alibaba Cloud**, **Ollama**
- Per-feature model selection (different models for resume, cover letter, chat, etc.)

### 📊 LinkedIn Profile Optimizer
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
Chrome Extension ──▶ FastAPI Backend ──▶ PostgreSQL (Supabase)
                          │
                    React Dashboard
                          │
                    Gotenberg (PDF)
```

| Component | Tech | Port |
|-----------|------|------|
| Frontend | React 18 + Vite + TypeScript | 5173 |
| Backend | FastAPI + Python 3.11 | 8005 |
| Database | PostgreSQL 15 (Supabase) | 5432 |
| PDF Engine | Gotenberg 8 | 3002 |
| Extension | Chrome Manifest V3 | — |

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
# Start the v2 stack (FastAPI + React + Gotenberg)
docker compose -f docker-compose.v2.yml up --build -d
```

### 3. Install Extension

1. Open `chrome://extensions/`
2. Enable **Developer Mode**
3. Click **Load unpacked** → select the `extension/` folder
4. Navigate to LinkedIn and click the extension icon

### 4. Access Dashboard

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🔧 Configuration

### AI Providers

Set your preferred AI provider in `.env`:

```bash
AI_PROVIDER=gemini              # gemini | nvidia | alibaba | ollama
GEMINI_API_KEY=your-key-here    # For Gemini
AI_API_KEY=your-key-here        # For other providers
AI_BASE_URL=                    # Required for nvidia/alibaba/ollama
```

### Per-Feature Models

Configure different AI models for each feature in the Settings page:

| Feature | Setting Key | Recommended |
|---------|------------|-------------|
| Resume Generation | `ai_model_resume` | gemini-2.5-pro |
| Cover Letter | `ai_model_cover` | gemini-2.0-flash |
| Chat Assistant | `ai_model_chat` | gemini-2.0-flash |
| Profile Optimization | `ai_model_optimizer` | gemini-2.5-pro |
| Job Evaluation | `ai_model_evaluator` | gemini-2.0-flash |
| Profile Import | `ai_model_import` | gemini-2.0-flash |

---

## 📁 Project Structure

```
├── backend/          # FastAPI backend (API + AI services)
├── frontend/         # React dashboard (Vite + TypeScript)
├── extension/        # Chrome extension (Manifest V3)
├── linkedin-jobs/    # Legacy Flask system (reference only)
├── docs/             # Documentation
│   └── SYSTEM.md     # Full system architecture & dev guide
├── config/           # Shared configuration files
└── docker-compose.v2.yml  # Production Docker stack
```

> 📖 See [docs/SYSTEM.md](docs/SYSTEM.md) for the complete system architecture, feature parity tables, and development guidelines.

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
2. When adding/removing features, update `docs/SYSTEM.md` (Section 9 — Feature Parity)
3. Follow the AI prompt guidelines in the system docs
4. Test extension changes on both profile and job pages

---

## 📄 License

Private project — All rights reserved.

---

<div align="center">
  <sub>Built with ❤️ by Paulo Aragão — Powered by AI</sub>
</div>
