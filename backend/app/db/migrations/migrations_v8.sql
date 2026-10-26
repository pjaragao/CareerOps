-- Migration V8: companies.company_type was never created on databases where `companies` already existed
-- before V2 (CREATE TABLE IF NOT EXISTS skipped it); the job list joins on it.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'company_type') THEN
        CREATE TYPE company_type AS ENUM ('DIRECT_EMPLOYER', 'RECRUITMENT_AGENCY', 'JOB_PLATFORM');
    END IF;
END$$;
ALTER TABLE public.companies ADD COLUMN IF NOT EXISTS company_type company_type DEFAULT 'DIRECT_EMPLOYER';
