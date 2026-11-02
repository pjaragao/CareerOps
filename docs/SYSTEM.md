# CareerOps — System Architecture & Development Guide

> **Last Updated**: 2026-10-31
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
│   ├── linkedin_assist.js      # AI comment on posts, connect-without-note on profiles (also opened from the app), scoring of listed people (user clicks send)
│   ├── background.js           # Sync to backend + "Enviar ao CareerOps Copilot" menu
│   ├── popup.html              # Import button
│   (download zip is built on the fly by GET /api/linkedin-copilot/extension/download)
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
4b. **Post links** (`linkedin_assist.js` `postUrn`, `urn_bridge.js`): a saved post's link comes from, in order, the HTML (data-urn/data-id, `/feed/update/` and `/posts/…-activity-…` links), React's props (first post id on the way up from the post's first buttons; an id already given to another post is refused — a deeper props walk was tried and returned other posts' ids), LinkedIn's own request right after you click Comment/Publicar on that post (fetch/XHR seen by the bridge; two different ids in the 4-s window are dropped), and the page address on a single-post page. Group posts use `urn:li:groupPost:<group>-<id>`. When all fail, `_save_inspiration` matches the post by its opening text (`_text_key`), so saving it again fills the link instead of duplicating it; `GET /inspirations/missing-links` + `PATCH /inspirations/{id}/link` let the extension fill it when the post shows up on any LinkedIn page, and `set_post_link` copies it to the same post's comment-queue item and line-of-thought records.
5. **Metrics**: weekly counts from the tables + manual LinkedIn analytics in `linkedin_metrics_weekly`; day/week boundaries use `APP_TIMEZONE`.
6. **Line of thought** (`migrations_v12.sql`, applied on startup by `linkedin_voice_service.ensure_schema`, which also backfills sent comments and published posts): `linkedin_voice` holds what you sent (comment, reply, message, post) or wrote (position), with topic, stance and your request to the AI; `ref` keeps one row per sent text (`comment:<hash of post>`, `message:<prospect id>`, `post:<id>`). Comments are recorded when a queue item goes to `done`, by `reconcile_engagement` and by the "Você comentou" theme; replies by the extension on LinkedIn's send (`POST /voice`). The consolidated profile lives in `app_ai_settings` (`voice_profile`, skill `linkedin/voice_profile.md`). Templates call `{{ line_of_thought(text) }}` (`SkillService`): profile + pinned rows + the 6 rows with the highest weighted word overlap (topic ×3, stance/request ×2, text).
7. **Networking** (`linkedin_networking_service.py`, `linkedin/networking_plan.md`, table `linkedin_networking_plans`): one AI call over up to 18 jobs (applied/interviewing/offer, then the last 45 days) → `contacts` (per pursued job: hiring-team members by name, else the likely hiring manager/recruiter as a people search; each with `note` ≤300 and `message`, in the ad's language), `companies`, `follow` and `posts` (per hiring company: the hiring team's `/recent-activity/all/` and a content search for the quoted company name, sorted by date, plus the angle). Named contacts are kept only when they match a hiring-team member or a prospect at that company. The extension sends `hiringTeam` (found by the "Meet the hiring team" heading) with `/jobs/import-extension`; `save_hiring_team` stores it in `job_listings.hiring_team_json` and adds the people as prospects (`segment = hiring_team`). `POST /prospects/{id}/message` (only for people at the company of one of your jobs, `job_ties`) drafts a connection note or, once connected, a DM (`linkedin/prospect_message.md`); `/message/sent` stores it (`message_draft`, `message_sent_at`) and in the line of thought.

### 3.5 Autopilot (you approve, the system executes)

Tables (`migrations_v15.sql`): `automation_state` (one row: mode, account kind, halted lanes, ramp), `automation_actions`, `automation_events`, `automation_runs`, `automation_limits`, `automation_answers`, `job_searches`, `job_email_events`. Code: `api/automation.py` → `services/automation_service.py`, `services/job_search_service.py`, `services/email_monitor_service.py`; worker in `automation/worker/`; extension in `linkedin_assist.js` section 8 (managed mode, only when the worker set `careeropsManaged` in `chrome.storage`); routine in `automation/claude_runner/run.py`; screen `pages/Automation.tsx`. Go-live steps: `automation/README.md`.

1. **Access** (`core/auth.py`): `X-CareerOps-Token`. The approver (you) decides; the worker only claims and reports, and can never approve. A role with no token configured refuses everything. Other sites' pages are refused by Origin on these routes and on post approve/publish.
2. **States**: `proposed → approved → (review_docs) → queued → running_ext → verifying → done`. Elsewhere: `escalated → running_claude`, `needs_user`, `awaiting_confirm`, `unknown_outcome`, `discarded`, `rejected`, `expired`, `cancelled`. Approving freezes the payload (`payload_hash`); a difference at claim time refuses it.
3. **Claim** (`AutomationService.claim`): the only way anything starts. Under a lock on the state row it checks mode, halted lanes, the window, the gap between writes, windows per lane, the limit of each kind at the current ramp step, the hash and the content guard. `unknown_outcome` comes first and only looks at the page.
4. **Never twice**: the extension reports `executed`, the worker opens the page and calls `verify`. Clicked but not seen: one more look, then `needs_user`, never a second click. Crash or lost lease: `unknown_outcome`.
5. **Final click** (`_allow_final`): an application needs mode `live` + main account + `allow_final_submit` + env `AUTOMATION_ALLOW_FINAL_SUBMIT`; anything else goes up to the last screen and reports a dry run. A test account only comments on or invites `test_account.allowed_targets`. An `executed` report with no permission halts everything. The first CVs wait for your reading (`review_cv_left`) and the first submissions for your click (`confirm_submit_left`).
6. **Failures** (`escalate`): `CLAUDE_CODES` go to the routine (one attempt, `claude.per_day`), `HALT_CODES` stop the LinkedIn lanes and lower the ramp, `DISCARD_CODES` end it, everything else comes to you. `safety.py` looks at every page first.
7. **Search**: `schedule_reads` queues the rounds; `managedSearch` reads the cards and `jobPosting` the ads; `add_discovered` stores them as `discovered`, which the document pipeline and the job board ignore, so a CV is only generated after approval (`prepare_documents`). `triage_pending` (`jobs/eligibility.md` + `jobs/triage.md`) decides propose / external_manual / discarded: score ≥ `jobs.min_score`, employer market in `jobs.markets`.
8. **Company sites** (`jobs.external_apply`, off by default): the popup's address moves the action to the `ats` lane, a browser with no LinkedIn session. `apply_copilot.js` fills and never submits; the routine finishes it with the form open.
9. **Claude routine**: cron on the host, so the credentials never enter a container. Browser tools only (`@playwright/mcp` inside the container, published on loopback), no shell or files, no tokens: the script reports. `audit` reads every tool call; going off target halts the lane. Saying "done" only leads to the worker looking at the page.
10. **Salary and years** (`LinkedInCopilotService._salary_answer`, `_facts`): salary questions never reach the AI, they come from the floors in `config/easy_apply.yml`; total years count from `career_start_year`.
11. **Content guard** (`services/content_guard.py`, `config/automation.yml`): `SkillService.OUTGOING_SKILLS` get the rule in the prompt, one rewrite if the answer breaks it, then refusal. Checked again at approval, at claim and when a job's PDF is served.
12. **Email monitor**: `EXAMINE` + `BODY.PEEK` only. Filter without AI, one AI reading with no tools per message, `job_email_events` keeps a summary and a quote. The first read only suggests; status changes need `email.auto_status`. `funnel` compares by age of the ad at application.

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

### 5.2 Extension-First Policy and Autopilot

The backend itself never drives a browser. Everything that happens on a page happens through the Extension, in your browser or in the worker's (`automation/`), so there is one implementation of each action. The rules live only in `automation_service.py`.

LinkedIn's rules forbid software that automates activity on the site. The Autopilot exists by the owner's decision, with that risk accepted (2026-10-31). Keep it honest: every action needs your approval; no stealth, fingerprint spoofing, proxies or captcha solving; any warning stops the lane until you turn it on again; a test account never submits an application.


---

## 6. Docker Deployment

### v2 Stack (Primary)
```bash
docker compose -f docker-compose.v2.yml up --build -d
```
Includes: FastAPI, React (Vite), Gotenberg, PostgreSQL.
