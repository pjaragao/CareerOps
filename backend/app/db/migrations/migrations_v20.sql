-- Migration V20: token plan for the autoapply engine (2026-11-16).
-- Applied by AutomationService.ensure_schema (startup). Idempotent.

-- One row per company site (host): how its forms are navigated (recipes learned from successful runs, phase 2) and what
-- blocked it before (site memory, phase 0: a host that showed a CAPTCHA goes straight to you, with no tokens spent).
CREATE TABLE IF NOT EXISTS public.automation_sites (
    host TEXT PRIMARY KEY,
    adapter TEXT NOT NULL DEFAULT 'generic',
    next_labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    submit_labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    successes INTEGER NOT NULL DEFAULT 0,
    failures INTEGER NOT NULL DEFAULT 0,
    blocks JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_block TEXT,
    last_block_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Per-run measurement (phase 0): which model ran and how many tokens it used, on which host, with what result.
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS input_tokens INTEGER;
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS output_tokens INTEGER;
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER;
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS cache_write_tokens INTEGER;
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS host TEXT;
ALTER TABLE public.automation_runs ADD COLUMN IF NOT EXISTS result_class TEXT;

-- Per-action budget and retry gate (phase 0): tokens spent across all runs, and the state the last run saw (a run is
-- tried again only when something changed since).
ALTER TABLE public.automation_actions ADD COLUMN IF NOT EXISTS tokens_spent BIGINT NOT NULL DEFAULT 0;
ALTER TABLE public.automation_actions ADD COLUMN IF NOT EXISTS last_run_fingerprint TEXT;

-- Texts written once and reused (phase 3): motivation answers per company and question, cover letters per company.
CREATE TABLE IF NOT EXISTS public.automation_text_cache (
    cache_key TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Circuit breaker (phase 0): a usage limit, a 5xx or an exhausted quota pauses every Claude run until this time, instead of
-- spending one attempt per action every 5 minutes.
ALTER TABLE public.automation_state ADD COLUMN IF NOT EXISTS claude_paused_until TIMESTAMP WITH TIME ZONE;
