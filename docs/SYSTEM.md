# CareerOps — System Architecture & Development Guide

> **Last Updated**: 2026-05-05
> **Maintainer**: @pjaragao
> **Rule**: This document MUST be updated whenever features are added, removed, or modified.

---

## 1. System Overview

CareerOps is an AI-powered career automation platform that helps users:
- Import LinkedIn job postings and profile data via a browser extension
- Generate ATS-optimized resumes and cover letters using a **Modular AI Skills Engine**
- Evaluate and score jobs against the user's career goals
- Prepare for interviews with STAR+R story generation
- **Build a Knowledge Base** from uploaded documents (PDF, DOCX) via **MarkItDown**
- **Deep Context Engine**: Injects validated results/STAR cases into all AI flows ([docs/AI_CONTEXT_ENGINE.md](AI_CONTEXT_ENGINE.md))
- Optimize their LinkedIn profile with AI-powered suggestions
- Track applications through a Kanban board

### Architecture Diagram

```
┌─────────────────┐     ┌──────────────────────────────────┐     ┌──────────────────┐
│  Chrome Extension│────▶│  FastAPI Backend (:8005)         │────▶│  PostgreSQL (DB) │
│  (content.js)   │     │  SkillService (Jinja2 Templates) │     │  (JSONB Storage) │
└─────────────────┘     └────────────────┬─────────────────┘     └──────────────────┘
        │                                │
        │                   ┌────────────▼────────────┐
        └───────────────────▶  React Frontend (:5173) │
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
| Backend | FastAPI (Python 3.12) | 8005 |
| Database | PostgreSQL 15 (Supabase/Local) | 5432 |
| AI Engine | **SkillService** (Jinja2 + Modular Prompts) | N/A |
| PDF Engine | Gotenberg 8 | 3002 |
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
│   │   ├── skills/             # AI Skills (Modular .md Prompts)
│   │   │   ├── common/         # Shared constraints & rules
│   │   │   ├── profile/        # LinkedIn optimization skills
│   │   │   ├── onboarding/     # Document parsing & resume optimization
│   │   │   ├── knowledge/      # Aggregated context generation
│   │   │   ├── jobs/           # Evaluation & ATS skills
│   │   │   ├── interview/      # STAR+R & question generation
│   │   │   └── analytics/      # Skill gaps & career insights
│   │   ├── services/
│   │   │   ├── ai_service.py       # Multi-provider AI abstraction
│   │   │   ├── skill_service.py    # Skill execution engine (Jinja2)
│   │   │   ├── interview_service.py # Refactored Interview skills
│   │   │   ├── job_service.py       # Job DB operations
│   │   │   ├── pdf_service.py       # Gotenberg PDF generation
│   │   │   ├── profile_service.py   # DB-only profile operations
│   │   │   └── document_service.py  # MarkItDown + Knowledge Base management
│   ├── scripts/                # Utility scripts (e.g. migration)
│   └── main.py
│
├── frontend/                   # React + Vite app — five screens (App.tsx)
│   └── src/
│       ├── pages/Home.tsx           # Início: today's actions
│       ├── pages/Profile.tsx · DocumentRepository.tsx · LinkedInTexts.tsx   # Meu Perfil tabs
│       ├── pages/JobBoard.tsx · Interview.tsx   # Vagas tabs
│       ├── pages/LinkedInCopilot.tsx
│       └── pages/Settings.tsx · InstallExtension.tsx   # Configurações tabs
│
├── extension/                  # Chrome Extension (Manifest V3)
│   ├── content.js              # Job and profile import (one page at a time)
│   ├── profile_filler.js       # "CareerOps · Perfil" panel on linkedin.com
│   ├── background.js           # Sync to backend + "Enviar ao CareerOps Copilot" menu
│   ├── popup.html              # Import button
│   └── package.py              # Builds the download zip
│
├── linkedin-jobs/.env(.example) # Environment file used by docker-compose (the legacy Flask app was removed)
```

---

## 3. Data Flow

### 3.1 Job Import (via Extension)

**Individual**: LinkedIn Page → Extension extracts DOM → Background.js POSTs to `/api/jobs/import-extension`.
Bulk capture and search-strategy automation were removed: the extension only reads the page the user is on.

### 3.3 AI Onboarding & Knowledge Injection

1. **Upload**: User uploads PDF/DOCX → `DocumentService` converts to Markdown via **MarkItDown**.
2. **Extract**: `onboarding/process_document.md` skill extracts structured facts.
3. **Validate**: User reviews and approves findings in the UI.
4. **Aggregate**: `knowledge/compile_knowledge.md` builds `user_data.md` (Knowledge Base).
5. **Inject**: Other skills (`interview`, `jobs`, `profile`) include `common/user_context.md` which pulls from the Knowledge Base via the **Deep Context Engine**.

### 3.3.1 Two markets and two master CVs

The profile targets **Brazil** (Portuguese: engineering and sanitation first, then technical-financial modeling, finance, data/AI) and **abroad** (English: data, finance and modeling; engineering as background). Master CVs live in `config/` (mounted into the container): `resume_en.md` (abroad) and `resume_pt.md` (Brazil). `ProfileService.get_resume_base(lang)` reads them; `/api/profile/resume?lang=en|pt` edits them (Profile → Base Resume toggle); resume generation for a job uses the CV in the job's language. The knowledge base (`skills/knowledge/user_data.md`, section 1) states both positionings for every AI skill.

### 3.4 LinkedIn Copilot

Tables (`migrations_v7.sql`): `linkedin_posts`, `linkedin_engagement`, `linkedin_prospects`, `linkedin_auth`, `linkedin_oauth_states`, `linkedin_metrics_weekly`.
Code: `api/linkedin_copilot.py` → `services/linkedin_copilot_service.py` (+ `services/linkedin_api_service.py` for OAuth and posting); skills in `skills/linkedin/` (posts use `ai_model_optimizer`, comments/notes `ai_model_outreach`); UI `pages/LinkedInCopilot.tsx`.

1. **Posts**: generate for a market (`br` in Portuguese or `intl` in English, each with its own audience and pillars; `migrations_v9.sql` adds `market`) (`linkedin/post_drafts.md`) → `draft` → user approves (optionally with a time) → `approved` → published by the API (button, or the 60-s scheduler started in `main.py`) → `published`. Editing an approved post sends it back to `draft`; publishing claims the row first (`approved → published`) so a post never goes out twice; failures go to `failed` with the error; `LINKEDIN_MAX_POSTS_PER_DAY` caps the rate.
2. **OAuth**: `/api/linkedin-copilot/oauth/start` → LinkedIn consent (`openid profile w_member_social`) → `/oauth/callback` validates the one-time `state`, stores the 60-day token and the member URN, redirects to the UI.
3. **Engagement / prospects**: the extension's context menu POSTs the selected text or the profile page to `/capture` (profile URL → prospect; post permalink or selection → engagement). The AI scores 0–100 (below 40 is auto-skipped) and drafts a comment or a ≤300-char note. The user acts on LinkedIn and updates the status.
4. **Profile filler**: `GET /api/linkedin-copilot/profile-copy` serves `config/linkedin_profile.json` (EN + PT, generated by `international/build_linkedin_profile.py`, which enforces LinkedIn's field limits). `extension/profile_filler.js` shows a shadow-DOM panel on linkedin.com; *Inserir* writes into the last focused field (native value setter + input/change events); the user saves on LinkedIn.
5. **Metrics**: weekly counts from the tables + manual LinkedIn analytics in `linkedin_metrics_weekly`; day/week boundaries use `APP_TIMEZONE`.

---

## 4. Feature Parity: v1 (Flask) vs v2 (FastAPI)

| Feature | v1 (Legacy) | v2 (Modern) | Status |
|---------|-------------|-------------|--------|
| Job Evaluation | `job_evaluator.py` | `job_evaluation_service.py` | ✅ Migrated |
| Interview Stories | `job_evaluator.py` | `interview_service.py` | ✅ Migrated |
| Customizable Prompts | `profile_prompts.py`| `app/skills/` (Jinja2) | ✅ Migrated |
| Profile Storage | `profile.yml` (YAML) | PostgreSQL (JSONB) | ✅ Migrated |
| Resume HTML Template | `resume_template.py`| `pdf_service.py` | ✅ Migrated |
| PDF via Gotenberg | `resume_generator.py`| `pdf_service.py` | ✅ Migrated |
| Scrapers (Playwright) | Server-side | Browser-side (Extension) | ✅ Modernized |
| Auto-Apply | `auto_applier.py` | Extension + AI Chat | ✅ Modernized |

---

## 5. Development Workflow Rules

### 5.1 Documentation & Workflow Rule

> [!IMPORTANT]
> **MANDATORY**: Whenever you add, remove, or significantly modify a feature, you MUST follow the [docs/WORKFLOW.md](WORKFLOW.md) steps and update:
> 1. This file (`docs/SYSTEM.md`)
> 2. `README.md`
> 3. Task status in `task.md`
> 4. **Extensive Investigation**: Always use the methodology in [docs/DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) for troubleshooting.

### 5.2 Profile Sync & Extension-First Policy

The backend should NEVER perform browser automation. All data ingestion must happen via the Extension. 


---

## 6. Docker Deployment

### v2 Stack (Primary)
```bash
docker compose -f docker-compose.v2.yml up --build -d
```
Includes: FastAPI, React (Vite), Gotenberg, PostgreSQL.
