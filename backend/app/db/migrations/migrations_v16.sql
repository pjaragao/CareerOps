-- Migration V16: portfolio link per job and its views.
-- The portfolio (Vercel) records each visit as a small event; CareerOps pulls them every few minutes
-- (PortfolioService.pull) and keeps the numbers here. Applied on startup too (main.py). Idempotent.

ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS portfolio_token TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS portfolio_views INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS portfolio_last_view_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS portfolio_seconds INTEGER NOT NULL DEFAULT 0;
-- hash of the CV last uploaded to the portfolio (downloadable there only with this job's link)
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS portfolio_cv_hash TEXT;
-- The CV PDF lives in Google Drive (uploaded by Lolo); the portfolio only redirects to it and counts the downloads.
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS portfolio_cv_drive_id TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS portfolio_cv_downloads INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS portfolio_cv_last_download_at TIMESTAMP WITH TIME ZONE;

-- One row per event pulled from the portfolio (event_id is the portfolio's id: pulling twice never counts twice).
CREATE TABLE IF NOT EXISTS public.portfolio_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    token TEXT NOT NULL,
    job_id INTEGER REFERENCES public.job_listings(id) ON DELETE SET NULL,
    company TEXT,
    event TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    location TEXT,
    device TEXT,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    notified_at TIMESTAMP WITH TIME ZONE,          -- told to you in the Lolo summary
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS portfolio_events_job_idx ON public.portfolio_events (job_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS portfolio_events_unnotified_idx ON public.portfolio_events (occurred_at) WHERE notified_at IS NULL;

-- Settings when not given by the environment (PORTFOLIO_URL, PORTFOLIO_TOKEN_SECRET, PORTFOLIO_PULL_TOKEN).
CREATE TABLE IF NOT EXISTS public.portfolio_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
