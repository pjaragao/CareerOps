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
    cover_letter    TEXT,
    language        VARCHAR(5),
    file_name       TEXT,
    easy_apply      BOOLEAN DEFAULT FALSE,
    company_description TEXT,
    company_profile_url TEXT,
    hiring_team_json    TEXT,
    scraped_at      TIMESTAMPTZ,
    generated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    -- New columns for V3
    archetype       VARCHAR(50),
    evaluation_score NUMERIC(3,2),
    email_draft     TEXT,
    linkedin_dm_draft TEXT,
    recruiter_email VARCHAR(255),
    recruiter_linkedin_url TEXT,
    applied_via_bot BOOLEAN DEFAULT FALSE,
    application_cost_tokens INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES public.job_listings(id) ON DELETE SET NULL,
    company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    apply_method VARCHAR(50), 
    status VARCHAR(50) DEFAULT 'Applied', 
    notes TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.profile_stats (
    id SERIAL PRIMARY KEY,
    scraped_at TIMESTAMPTZ,
    score INTEGER,
    analysis TEXT,
    last_optimized_at TIMESTAMPTZ,
    current_data JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User Profiles: Stores exhaustive information for auto-filling
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(50) DEFAULT 'default',
    full_data       JSONB NOT NULL,
    base_resume_md  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Search Strategies: Stores keywords and filters for autonomous searching
CREATE TABLE IF NOT EXISTS public.search_strategies (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(50) DEFAULT 'default',
    title           TEXT NOT NULL,
    keywords        TEXT[],
    locations       TEXT[],
    remote_only     BOOLEAN DEFAULT TRUE,
    is_active       BOOLEAN DEFAULT TRUE,
    ai_suggestions  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Skill Gaps: Tracks missing skills from job descriptions
CREATE TABLE IF NOT EXISTS public.skill_gaps (
    id              SERIAL PRIMARY KEY,
    skill_name      VARCHAR(100) UNIQUE,
    frequency       INTEGER DEFAULT 1,
    priority        VARCHAR(20) DEFAULT 'medium',
    last_seen_at    TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Status flow: new → scraped → generating → done → error
-- 'removed' status for jobs unsaved from LinkedIn

CREATE INDEX IF NOT EXISTS idx_job_listings_status ON public.job_listings(status);
CREATE INDEX IF NOT EXISTS idx_job_listings_linkedin_job_id ON public.job_listings(linkedin_job_id);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON public.applications(job_id);

-- Job Evaluations (scoring system based on career-ops)
CREATE TABLE IF NOT EXISTS public.job_evaluations (
    id              SERIAL PRIMARY KEY,
    job_id          INTEGER REFERENCES public.job_listings(id) ON DELETE CASCADE,
    overall_score   NUMERIC(3,2) DEFAULT 0,
    match_score     NUMERIC(3,2) DEFAULT 0,
    north_star_score NUMERIC(3,2) DEFAULT 0,
    comp_score      NUMERIC(3,2) DEFAULT 0,
    cultural_score  NUMERIC(3,2) DEFAULT 0,
    red_flags       TEXT,
    analysis        TEXT,
    archetype       VARCHAR(50),
    evaluated_at    TIMESTAMPTZ DEFAULT NOW(),
    ai_provider     VARCHAR(50),
    ai_model        VARCHAR(100)
);

-- Interview Stories (STAR+R framework)
CREATE TABLE IF NOT EXISTS public.interview_stories (
    id              SERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    situation       TEXT,
    task            TEXT,
    action          TEXT,
    result          TEXT,
    reflection      TEXT,
    tags            TEXT[],
    archetypes      TEXT[],
    usage_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- AI Provider Config (stored in DB for UI management)
CREATE TABLE IF NOT EXISTS public.ai_config (
    id              SERIAL PRIMARY KEY,
    provider        VARCHAR(50) DEFAULT 'gemini',
    model           VARCHAR(100),
    base_url        TEXT,
    api_key_hint    VARCHAR(10),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline URLs (for batch processing)
CREATE TABLE IF NOT EXISTS public.pipeline_urls (
    id              SERIAL PRIMARY KEY,
    url             TEXT NOT NULL UNIQUE,
    source          VARCHAR(50) DEFAULT 'manual',
    status          VARCHAR(20) DEFAULT 'pending',
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

-- New indexes
CREATE INDEX IF NOT EXISTS idx_job_evaluations_job_id ON public.job_evaluations(job_id);
CREATE INDEX IF NOT EXISTS idx_job_evaluations_archetype ON public.job_evaluations(archetype);
CREATE INDEX IF NOT EXISTS idx_job_evaluations_score ON public.job_evaluations(overall_score);
CREATE INDEX IF NOT EXISTS idx_interview_stories_tags ON public.interview_stories USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_interview_stories_archetypes ON public.interview_stories USING GIN(archetypes);
CREATE INDEX IF NOT EXISTS idx_pipeline_urls_status ON public.pipeline_urls(status);
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON public.user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_search_strategies_user_id ON public.search_strategies(user_id);

-- Alter table commands to safely add columns if they don't exist
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS archetype VARCHAR(50);
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS evaluation_score NUMERIC(3,2);
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS email_draft TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS linkedin_dm_draft TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS recruiter_email VARCHAR(255);
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS recruiter_linkedin_url TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS applied_via_bot BOOLEAN DEFAULT FALSE;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS application_cost_tokens INTEGER DEFAULT 0;
