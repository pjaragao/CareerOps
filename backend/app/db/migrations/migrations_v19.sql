-- Migration V19: ATS candidate portal accounts and email verification ingestion for autonomous external applies.
-- Applied by AutomationService.ensure_schema (startup). Idempotent.

CREATE TABLE IF NOT EXISTS public.automation_site_accounts (
    id SERIAL PRIMARY KEY,
    site_key TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT NOT NULL DEFAULT '',
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.automation_email_verifications (
    id SERIAL PRIMARY KEY,
    message_id TEXT UNIQUE,
    sender TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    links JSONB NOT NULL DEFAULT '[]'::jsonb,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS automation_email_verifications_received_idx
    ON public.automation_email_verifications (received_at DESC);
