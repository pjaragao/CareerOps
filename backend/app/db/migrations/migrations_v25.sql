-- Migration V25 (2026-11-22): jobs from more places than LinkedIn, and approving jobs from the phone with a link.
-- Applied by AutomationService.ensure_schema on every start (idempotent).

-- Where a job came from: 'linkedin' (the searches, the saved jobs, the extension) or a source of discovery_service
-- (greenhouse, lever, ashby, remotive...). A job of a company site carries the form's address: approved, it goes
-- straight to the company-site queue, never through the LinkedIn page.
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'linkedin';
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS source_job_id TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS apply_url TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS ux_job_listings_source_job ON public.job_listings (source, source_job_id) WHERE source_job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_job_listings_apply_url ON public.job_listings (apply_url) WHERE apply_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_job_listings_source_created ON public.job_listings (source, created_at);

-- The places read every day: one row per company board (kind = the ATS, slug = the company there) and one per job board
-- (kind = remotive, remoteok..., slug = the feed). status: ok | failing | gone (the company left that ATS) | off.
CREATE TABLE IF NOT EXISTS public.job_sources (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    slug TEXT NOT NULL,
    company TEXT,
    origin TEXT NOT NULL DEFAULT 'manual',      -- applied | probe | board | catalog | manual
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'ok',
    failures INTEGER NOT NULL DEFAULT 0,
    last_run_at TIMESTAMPTZ,
    last_ok_at TIMESTAMPTZ,
    last_error_code TEXT,
    last_error TEXT,
    jobs_seen INTEGER NOT NULL DEFAULT 0,
    jobs_added INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (kind, slug)
);

-- A company name already tried on the ATS (found or not), so it is not tried again every day.
CREATE TABLE IF NOT EXISTS public.job_source_probes (
    company_key TEXT PRIMARY KEY,
    company TEXT,
    found_kind TEXT,
    found_slug TEXT,
    probed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per reading of one kind of source: what came, what the cheap filter cut, what was new. The measure of each source.
CREATE TABLE IF NOT EXISTS public.discovery_runs (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    sources INTEGER NOT NULL DEFAULT 0,
    fetched INTEGER NOT NULL DEFAULT 0,
    filtered INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    known INTEGER NOT NULL DEFAULT 0,
    added INTEGER NOT NULL DEFAULT 0,
    deferred INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_discovery_runs_kind ON public.discovery_runs (kind, started_at);

-- The approval link (the phone, any browser): a token that only lists the proposed jobs and approves or discards them.
-- Only its hash is kept; it lasts a few days and can be revoked.
CREATE TABLE IF NOT EXISTS public.approval_links (
    id SERIAL PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL DEFAULT 'jobs',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    uses INTEGER NOT NULL DEFAULT 0
);

-- Limits: new jobs from the other sources read by the AI per day, and new jobs put on the approval list per day (all sources)
INSERT INTO public.automation_limits (kind, period, step0, step1, step2) VALUES
    ('source_read', 'day', 300, 300, 300),
    ('job_propose', 'day', 60, 60, 60)
ON CONFLICT (kind) DO NOTHING;

-- Kinds of source you switched off in Pesquisar vagas → Fontes (greenhouse, remotive...)
ALTER TABLE public.automation_state ADD COLUMN IF NOT EXISTS discovery_off TEXT[] NOT NULL DEFAULT '{}';
