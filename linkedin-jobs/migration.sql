-- LinkedIn Jobs Scraper - Database Migration
-- Execute this on Supabase local PostgreSQL (schema: public)

CREATE TABLE IF NOT EXISTS public.job_listings (
    id              SERIAL PRIMARY KEY,
    linkedin_job_id VARCHAR(50) UNIQUE,
    url             TEXT NOT NULL UNIQUE,
    status          VARCHAR(20) DEFAULT 'new',
    job_title       TEXT,
    company         TEXT,
    location        TEXT,
    description     TEXT,
    language        VARCHAR(5),
    file_name       TEXT,
    easy_apply      BOOLEAN DEFAULT FALSE,
    scraped_at      TIMESTAMPTZ,
    generated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Status flow: new → scraped → generating → done → error
-- 'removed' status for jobs unsaved from LinkedIn

CREATE INDEX IF NOT EXISTS idx_job_listings_status ON public.job_listings(status);
CREATE INDEX IF NOT EXISTS idx_job_listings_linkedin_job_id ON public.job_listings(linkedin_job_id);
