
-- Migration V3: Add Optimizer Analyses Table for Persistent Results

CREATE TABLE IF NOT EXISTS public.optimizer_analyses (
    id SERIAL PRIMARY KEY,
    analysis_type TEXT NOT NULL,              -- 'full_audit', 'experience', 'skills', 'ats_match'
    lang TEXT DEFAULT 'pt',
    strategy_context JSONB,                   -- { "type": "strategy"|"job"|"custom", "id": N, "label": "...", "keywords": [...] }
    results JSONB NOT NULL,                   -- Full AI response payload
    profile_snapshot JSONB,                   -- Profile state at time of analysis
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for quick lookups
CREATE INDEX IF NOT EXISTS idx_optimizer_analyses_type ON public.optimizer_analyses(analysis_type);
CREATE INDEX IF NOT EXISTS idx_optimizer_analyses_created ON public.optimizer_analyses(created_at DESC);
