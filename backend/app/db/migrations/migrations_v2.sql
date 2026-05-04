
-- Migration V2: Add Companies Table and Link Job Listings

-- 1. Create company_type enum if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'company_type') THEN
        CREATE TYPE company_type AS ENUM ('DIRECT_EMPLOYER', 'RECRUITMENT_AGENCY', 'JOB_PLATFORM');
    END IF;
END $$;

-- 2. Create companies table
CREATE TABLE IF NOT EXISTS public.companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    career_site_url TEXT,
    description TEXT,
    logo_url TEXT,
    industry TEXT,
    tech_stack TEXT,
    remote_policy TEXT,
    domain TEXT,
    company_type company_type DEFAULT 'DIRECT_EMPLOYER',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Add company_id to job_listings
ALTER TABLE public.job_listings 
ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES public.companies(id);

-- 4. Index for performance
CREATE INDEX IF NOT EXISTS idx_job_listings_company_id ON public.job_listings(company_id);
CREATE INDEX IF NOT EXISTS idx_companies_name ON public.companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON public.companies(domain);
