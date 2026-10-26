-- Migration V10: posts saved from the feed as topics of interest, used as inspiration for new posts
CREATE TABLE IF NOT EXISTS public.linkedin_inspirations (
    id SERIAL PRIMARY KEY,
    post_url TEXT,
    author_name TEXT,
    author_headline TEXT,
    post_text TEXT NOT NULL,
    note TEXT,
    used_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_linkedin_inspirations_url ON public.linkedin_inspirations (post_url) WHERE post_url IS NOT NULL;
