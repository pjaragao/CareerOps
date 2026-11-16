-- Migration V21: live CAPTCHA session (2026-11-16). Applied by AutomationService.ensure_schema (startup). Idempotent.
-- While it lasts, only the actions stuck on a CAPTCHA run, one at a time, with the browser waiting for you to solve it.
ALTER TABLE public.automation_state ADD COLUMN IF NOT EXISTS captcha_session_until TIMESTAMP WITH TIME ZONE;
