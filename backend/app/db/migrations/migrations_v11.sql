-- Migration V11: AI settings kept in the database (config files inside the container are reset on every deploy)
--   style  = writing style per kind of generated text (preset + overrides)
--   models = which model each kind of task uses
CREATE TABLE IF NOT EXISTS public.app_ai_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
