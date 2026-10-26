-- Migration V9: two target markets in the LinkedIn Copilot
--   br   = Brazil (Portuguese): engineering & sanitation, technical-financial modeling, data/AI
--   intl = abroad, US/Europe (English): data, finance and modeling; engineering as background
ALTER TABLE public.linkedin_posts ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'intl';
ALTER TABLE public.linkedin_prospects ADD COLUMN IF NOT EXISTS market TEXT;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'linkedin_posts_market_check') THEN
        ALTER TABLE public.linkedin_posts ADD CONSTRAINT linkedin_posts_market_check CHECK (market IN ('br', 'intl'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'linkedin_prospects_market_check') THEN
        ALTER TABLE public.linkedin_prospects ADD CONSTRAINT linkedin_prospects_market_check CHECK (market IS NULL OR market IN ('br', 'intl'));
    END IF;
END$$;
