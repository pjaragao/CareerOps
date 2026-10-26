-- Migration V7: LinkedIn Copilot (post drafts, engagement queue, prospects, OAuth, weekly metrics)
-- Nothing here interacts with LinkedIn on its own: posts are published only after explicit approval,
-- engagement and connection requests are always done by the user.

CREATE TABLE IF NOT EXISTS public.linkedin_posts (
    id SERIAL PRIMARY KEY,
    pillar TEXT,
    topic TEXT,
    source_notes TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'published', 'failed', 'discarded')),
    scheduled_for TIMESTAMP WITH TIME ZONE,
    approved_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE,
    linkedin_urn TEXT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_linkedin_posts_due ON public.linkedin_posts (status, scheduled_for);

CREATE TABLE IF NOT EXISTS public.linkedin_engagement (
    id SERIAL PRIMARY KEY,
    post_url TEXT,
    author_name TEXT,
    author_headline TEXT,
    post_text TEXT NOT NULL,
    relevance INTEGER,
    reason TEXT,
    comment_draft TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'done', 'skipped')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    done_at TIMESTAMP WITH TIME ZONE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_linkedin_engagement_url ON public.linkedin_engagement (post_url) WHERE post_url IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.linkedin_prospects (
    id SERIAL PRIMARY KEY,
    profile_url TEXT,
    name TEXT,
    headline TEXT,
    company TEXT,
    profile_text TEXT,
    segment TEXT,
    fit INTEGER,
    reason TEXT,
    note_draft TEXT,
    status TEXT NOT NULL DEFAULT 'to_contact'
        CHECK (status IN ('to_contact', 'invited', 'accepted', 'replied', 'skipped')),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_linkedin_prospects_url ON public.linkedin_prospects (profile_url) WHERE profile_url IS NOT NULL;

-- Single-row OAuth store (id = 1). Token lifetime is ~60 days; re-connect from the UI when it expires.
CREATE TABLE IF NOT EXISTS public.linkedin_auth (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    access_token TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    member_urn TEXT NOT NULL,
    member_name TEXT,
    scope TEXT,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.linkedin_oauth_states (
    state TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.linkedin_metrics_weekly (
    week_start DATE PRIMARY KEY,
    profile_views INTEGER,
    search_appearances INTEGER,
    post_impressions INTEGER,
    recruiter_messages INTEGER,
    interviews INTEGER,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
