-- Migration V15: Autopilot (you approve, the server browser executes) and the daily email monitor.
-- Applied on startup too (main.py), so a fresh deploy never misses it. Everything starts switched off (mode = 'off').

-- One row. mode: off (nothing runs) | dry_run (reads and walks forms, never does the final click) | live.
-- account_kind = 'test' never submits an application, whatever else says so (automation_service._allow_final).
CREATE TABLE IF NOT EXISTS public.automation_state (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    mode TEXT NOT NULL DEFAULT 'off' CHECK (mode IN ('off', 'dry_run', 'live')),
    account_kind TEXT NOT NULL DEFAULT 'test' CHECK (account_kind IN ('test', 'main')),
    allow_final_submit BOOLEAN NOT NULL DEFAULT FALSE,
    halted_at TIMESTAMP WITH TIME ZONE,
    halted_reason TEXT,
    halted_lanes TEXT[] NOT NULL DEFAULT '{}',
    invites_paused_until TIMESTAMP WITH TIME ZONE,
    ramp_step INTEGER NOT NULL DEFAULT 0,
    ramp_step_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    confirm_submit_left INTEGER NOT NULL DEFAULT 3,
    review_cv_left INTEGER NOT NULL DEFAULT 20,
    next_write_at TIMESTAMP WITH TIME ZONE,
    session_status TEXT,
    worker_seen_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
INSERT INTO public.automation_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.automation_actions (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('apply', 'comment', 'follow', 'connect', 'search', 'check', 'feed_scan', 'follow_scan')),
    lane TEXT NOT NULL CHECK (lane IN ('linkedin_read', 'linkedin_write', 'ats')),
    status TEXT NOT NULL CHECK (status IN ('proposed', 'approved', 'review_docs', 'queued', 'running_ext', 'verifying', 'awaiting_confirm',
        'unknown_outcome', 'escalated', 'running_claude', 'needs_user', 'done', 'discarded', 'failed', 'rejected', 'expired', 'cancelled')),
    target_type TEXT,
    target_id INTEGER,
    target_url TEXT,
    title TEXT,
    rank INTEGER NOT NULL DEFAULT 50,
    sort_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL DEFAULT '{}',
    payload_hash TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    approved_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    executor TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    claude_attempts INTEGER NOT NULL DEFAULT 0,
    lease_owner TEXT,
    lease_until TIMESTAMP WITH TIME ZONE,
    nonce TEXT,
    error_code TEXT,
    error_text TEXT,
    questions JSONB NOT NULL DEFAULT '[]',
    result JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_automation_actions_claim ON public.automation_actions (lane, status, rank, sort_at DESC);
CREATE INDEX IF NOT EXISTS ix_automation_actions_kind_started ON public.automation_actions (kind, started_at);

CREATE TABLE IF NOT EXISTS public.automation_events (
    id BIGSERIAL PRIMARY KEY,
    action_id INTEGER REFERENCES public.automation_actions (id) ON DELETE CASCADE,
    at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    event TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    screenshot_path TEXT
);
CREATE INDEX IF NOT EXISTS ix_automation_events_action ON public.automation_events (action_id, at);

-- Executions of a routine: the Claude fallback (its daily cap is counted here), searches, the email check
CREATE TABLE IF NOT EXISTS public.automation_runs (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    action_id INTEGER REFERENCES public.automation_actions (id) ON DELETE SET NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    ok BOOLEAN,
    cost_usd NUMERIC(10, 4),
    summary JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_automation_runs_kind ON public.automation_runs (kind, started_at);

-- Per kind: how many at each step of the ramp, per day or per week. A LinkedIn warning goes back one step.
CREATE TABLE IF NOT EXISTS public.automation_limits (
    kind TEXT PRIMARY KEY,
    period TEXT NOT NULL CHECK (period IN ('day', 'week')),
    step0 INTEGER NOT NULL,
    step1 INTEGER NOT NULL,
    step2 INTEGER NOT NULL
);
INSERT INTO public.automation_limits (kind, period, step0, step1, step2) VALUES
    ('apply', 'day', 3, 5, 10),
    ('comment', 'day', 3, 5, 10),
    ('connect', 'week', 10, 15, 20),
    ('follow', 'day', 3, 5, 10),
    ('search', 'day', 12, 12, 12),
    ('job_read', 'day', 40, 40, 40),
    ('check', 'day', 2, 2, 2),
    ('feed_scan', 'day', 2, 2, 2),
    ('follow_scan', 'day', 2, 2, 2)
ON CONFLICT (kind) DO NOTHING;

-- Answers you gave to questions in application forms, reused on the next form that asks the same
CREATE TABLE IF NOT EXISTS public.automation_answers (
    id SERIAL PRIMARY KEY,
    question_norm TEXT NOT NULL,
    question TEXT NOT NULL,
    field_type TEXT NOT NULL DEFAULT 'text',
    answer TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (question_norm, field_type)
);

CREATE TABLE IF NOT EXISTS public.job_searches (
    id SERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    group_id TEXT NOT NULL,
    mode_id TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'intl',
    keywords TEXT NOT NULL,
    location TEXT NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}',
    schedule TEXT NOT NULL DEFAULT 'daily',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    jobs_found INTEGER NOT NULL DEFAULT 0
);

-- A job found by a search stays 'discovered' until you approve it: no CV or cover letter is generated before that.
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS triage_score INTEGER;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS triage_reason TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS triage_outcome TEXT;   -- propose | external_manual | discarded
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS posted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS employer_market TEXT;  -- intl | br | unknown
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS salary_flag TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS search_slug TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS applied_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS applied_via_bot BOOLEAN;
CREATE INDEX IF NOT EXISTS ix_job_listings_triage ON public.job_listings (status, triage_score);

-- Daily email monitor: a summary and the sentence behind the reading, never the whole message
CREATE TABLE IF NOT EXISTS public.job_email_events (
    id SERIAL PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    thread_id TEXT,
    job_id INTEGER REFERENCES public.job_listings (id) ON DELETE SET NULL,
    received_at TIMESTAMP WITH TIME ZONE,
    sender_domain TEXT,
    subject TEXT,
    classification TEXT NOT NULL,
    confidence NUMERIC(3, 2),
    summary TEXT,
    evidence_quote TEXT,
    status_applied TEXT,
    needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    baseline BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_job_email_events_job ON public.job_email_events (job_id, received_at);

-- Lolo (the WhatsApp bot): what to tell you, once each. The bot fetches what is not delivered and marks it delivered.
CREATE TABLE IF NOT EXISTS public.bot_notifications (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    urgent BOOLEAN NOT NULL DEFAULT FALSE,
    text TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_bot_notifications_pending ON public.bot_notifications (id) WHERE delivered_at IS NULL;
-- the last status of the action you were told about: a change into a status worth telling becomes a notification
ALTER TABLE public.automation_actions ADD COLUMN IF NOT EXISTS notified_status TEXT;

-- What the e-mails say about you beyond "no": grouped by theme, for you to decide later what to do with them
CREATE TABLE IF NOT EXISTS public.improvement_suggestions (
    id SERIAL PRIMARY KEY,
    email_event_id INTEGER REFERENCES public.job_email_events (id) ON DELETE CASCADE,
    job_id INTEGER REFERENCES public.job_listings (id) ON DELETE SET NULL,
    company TEXT,
    target TEXT NOT NULL,                   -- cv | me
    theme TEXT NOT NULL,
    suggestion TEXT NOT NULL,
    evidence_quote TEXT,
    status TEXT NOT NULL DEFAULT 'new',     -- new | accepted | dismissed
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMP WITH TIME ZONE
);
ALTER TABLE public.job_email_events ADD COLUMN IF NOT EXISTS alert_kind TEXT;
ALTER TABLE public.job_email_events ADD COLUMN IF NOT EXISTS source TEXT;
-- What to do with the message in the mailbox (Lolo does it): archive what needs nothing from you, keep the rest
ALTER TABLE public.job_email_events ADD COLUMN IF NOT EXISTS mail_action TEXT;          -- archive | keep
ALTER TABLE public.job_email_events ADD COLUMN IF NOT EXISTS mail_done_at TIMESTAMP WITH TIME ZONE;
