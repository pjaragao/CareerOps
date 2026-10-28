-- Migration V13: eligibility check of each job (residency / work visa the candidate does not have)
--   eligibility_status = 'ok' (nothing found), 'warning' (soft: "preferred", unclear region), 'blocked' (hard requirement)
--   eligibility_issues = [{"type": "residency"|"work_authorization", "quote": "...", "reason": "..."}]
--   eligibility_checked_at = NULL means "check again" (new job, or the description changed on re-import)
--   auto_docs_at = when CV and cover letter were generated automatically after the check (attempted once per job)
-- Applied on startup too (main.py), so a fresh deploy never misses it.
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS eligibility_status TEXT;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS eligibility_issues JSONB NOT NULL DEFAULT '[]';
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS eligibility_checked_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS auto_docs_at TIMESTAMP WITH TIME ZONE;
