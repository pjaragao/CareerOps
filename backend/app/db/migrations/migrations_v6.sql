-- Migration V6: Add updated_at column to job_listings
ALTER TABLE public.job_listings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;
