-- Migration V23: which engine does each kind of AI work (2026-11-17). Applied by AutomationService.ensure_schema. Idempotent.
-- {"agent": "hermes|auto|claude", "documents": "claude|hermes", "forms": "claude|hermes", "texts": "agy|hermes"}
ALTER TABLE public.automation_state ADD COLUMN IF NOT EXISTS ai_engine JSONB NOT NULL DEFAULT '{}'::jsonb;
