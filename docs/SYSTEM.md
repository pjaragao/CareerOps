# CareerOps — System Architecture & Development Guide

> **Last Updated**: 2026-04-29
> **Maintainer**: @pjaragao
> **Rule**: This document MUST be updated whenever features are added, removed, or modified.

---

## 1. System Overview

CareerOps is an AI-powered career automation platform that helps users:
- Import LinkedIn job postings and profile data via a browser extension
- Generate ATS-optimized resumes and cover letters using AI
- Evaluate and score jobs against the user's career goals
- Prepare for interviews with STAR+R story generation
- Optimize their LinkedIn profile with AI-powered suggestions
- Track applications through a Kanban pipeline

### Architecture Diagram

```
┌─────────────────┐     ┌─────────────────────────┐     ┌──────────────────┐
│  Chrome Extension│────▶│  FastAPI Backend (:8005) │────▶│  PostgreSQL (DB) │
│  (content.js)   │     │  /backend/app/           │     │  (Supabase)      │
└─────────────────┘     └────────────┬────────────┘     └──────────────────┘
        │                            │
        │               ┌────────────▼────────────┐
        └───────────────▶  React Frontend (:5173) │
                        │  /frontend/src/          │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  Gotenberg (HTML→PDF)    │
                        │  (:3002)                 │
                        └─────────────────────────┘
```

### Technology Stack

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend | React 18 + TypeScript + Vite | 5173 |
| Backend | FastAPI (Python 3.12) | 8005 (mapped to 8000 internally) |
| Database | PostgreSQL 15 (Supabase) | 5432 |
| PDF Engine | Gotenberg 8 | 3002 |
| AI Provider | Multi-provider (Gemini, NVIDIA NIM, Alibaba, Ollama) | N/A |
| Extension | Chrome Manifest V3 | N/A |

---

## 2. Project Structure

```
linkedin_resume/
├── backend/                    # FastAPI (v2) — Primary backend
│   ├── app/
│   │   ├── api/                # Route handlers
│   │   ├── db/
│   │   │   └── session.py      # DB connection factory
│   │   ├── skills/             # [NEW] AI Skills (Modular .md Prompts)
│   │   │   ├── common/         # Shared constraints & rules
│   │   │   ├── profile/        # LinkedIn optimization skills
│   │   │   ├── jobs/           # Evaluation & ATS skills
│   │   │   └── interview/      # STAR+R & question generation
│   │   └── services/
│   │       ├── ai_service.py       # Multi-provider AI abstraction
│   │       ├── skill_service.py    # [NEW] Skill execution engine (Jinja2)
│   │       ├── interview_service.py # Migrated STAR+R logic
│   │       ├── job_evaluation_service.py # Migrated Scoring logic [NEW]
│   │       ├── job_service.py       # Job DB operations
│   │       ├── pdf_service.py       # Gotenberg PDF generation
│   │       └── profile_service.py   # Profile import/optimize/AI
│   ├── Dockerfile              # Playwright-free (Thin Backend)
│   └── requirements.txt
│
├── frontend/                   # React + Vite dashboard
│   └── src/
│       ├── pages/
│       │   ├── JobBoard.tsx         # Job listings table with AI actions
│       │   ├── Strategies.tsx       # Search strategies (Ext. Automation)
│       │   └── LinkedInOptimizer.tsx # Full LinkedIn audit suite
│
├── extension/                  # Chrome Extension (Manifest V3)
│   ├── content.js              # DOM scraping + Bulk Capture + Auto Search
│   ├── background.js           # Service worker (sync to backend)
│   ├── popup.html              # UI for Profile/Job/Bulk Import
│
├── linkedin-jobs/              # ⚠️ LEGACY Flask — Cleanup Mode
│   ├── web.py                  # Simplified Flask (No scrapers)
│   ├── job_evaluator.py        # [DEPRECATED] Ported to v2 service
│   ├── resume_generator.py     # [DEPRECATED] Ported to v2 service
│   ├── scraper.py              # [DELETED]
│   └── migration.sql           # DB schema source of truth
```

---

## 3. Data Flow

### 3.1 Job Import (via Extension)

**Individual**: LinkedIn Page → Extension extracts DOM → Background.js POSTs to `/api/jobs/import-extension`.
**Bulk**: LinkedIn Search → Extension iterates list → Clicks each job → Extracts description → Batch POSTs to Backend.

### 3.2 Strategy Automation

1. User clicks "Run Strategy" in Dashboard.
2. Frontend triggers Extension via Message/Backend Flag.
3. Extension navigates LinkedIn Search with keywords.
4. Extension triggers Bulk Capture automatically.

---

## 4. Feature Parity: v1 (Flask) vs v2 (FastAPI)

| Feature | v1 (Legacy) | v2 (Modern) | Status |
|---------|-------------|-------------|--------|
| Job Evaluation | `job_evaluator.py` | `job_evaluation_service.py` | ✅ Migrated |
| Interview Stories | `job_evaluator.py` | `interview_service.py` | ✅ Migrated |
| Customizable Prompts | `profile_prompts.py`| `app/skills/` (Jinja2) | 🏗️ Refactoring |
| Profile Storage | `profile.yml` (YAML) | PostgreSQL (JSONB) | ✅ Migrated |
| Resume HTML Template | `resume_template.py`| `pdf_service.py` | ✅ Migrated |
| PDF via Gotenberg | `resume_generator.py`| `pdf_service.py` | ✅ Migrated |
| Scrapers (Playwright) | Server-side | Browser-side (Extension) | ✅ Modernized |
| Auto-Apply | `auto_applier.py` | Extension + AI Chat | ✅ Modernized |

---

## 5. Development Workflow Rules

### 5.1 Documentation Update Rule

> [!IMPORTANT]
> **MANDATORY**: Whenever you add, remove, or significantly modify a feature, you MUST update:
> 1. This file (`docs/SYSTEM.md`)
> 2. `README.md`
> 3. Task status in `task.md`

### 5.2 Extension-First Data Policy

The backend should NEVER perform browser automation. All data ingestion must happen via the Extension or direct PDF/MD uploads. This keeps the backend thin, fast, and resilient to LinkedIn UI changes (as the user is always logged in).

---

## 6. Docker Deployment

### v2 Stack (Primary)
```bash
docker compose -f docker-compose.v2.yml up --build -d
```
Includes: FastAPI, React (Vite), Gotenberg, PostgreSQL.
