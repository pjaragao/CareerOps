-- Migration V22: live questions (2026-11-16). Applied by AutomationService.ensure_schema (startup). Idempotent.
-- The apply agent (Lolo's Hermes) meets a required question nothing answers: Lolo asks you on WhatsApp, the agent waits
-- with the form open, and your answer goes back to it (and into the answer bank, for good).
CREATE TABLE IF NOT EXISTS public.automation_live_questions (
    id BIGSERIAL PRIMARY KEY,
    action_id BIGINT NOT NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]'::jsonb,
    field_type TEXT NOT NULL DEFAULT 'text',
    answer TEXT,
    asked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    answered_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS automation_live_questions_open ON public.automation_live_questions (action_id) WHERE answer IS NULL;
