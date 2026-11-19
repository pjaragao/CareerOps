-- Migration V24: the CAPTCHA solver (2026-11-19). Applied by AutomationService.ensure_schema on every start; the one-shot part
-- runs once, guarded by automation_state.captcha_solver_since.
-- Sites that were marked "only a person passes this" (2+ CAPTCHAs, automation_sites.blocks.captcha) were never tried by a
-- solver: their CAPTCHA count starts again, so they get the solver; 2 more misses by the solver send them to you again.
ALTER TABLE public.automation_state ADD COLUMN IF NOT EXISTS captcha_solver_since TIMESTAMPTZ;
UPDATE public.automation_sites SET blocks = blocks - 'captcha', updated_at = NOW()
 WHERE blocks ? 'captcha' AND EXISTS (SELECT 1 FROM public.automation_state WHERE captcha_solver_since IS NULL);
UPDATE public.automation_state SET captcha_solver_since = NOW() WHERE captcha_solver_since IS NULL;
