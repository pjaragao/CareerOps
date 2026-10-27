-- Migration V12: line of thought and networking plans
--   linkedin_voice = what you said in public (comments, replies, messages) and the positions behind it, so new texts
--                    stay consistent with them. Rows come from what you actually sent and from drafts you shaped with
--                    a request of your own; "position" rows are written by you in the app.
--   linkedin_networking_plans = companies, people, posts and messages suggested from the jobs in the system
-- Applied on startup too (main.py), so a fresh deploy never misses it.
CREATE TABLE IF NOT EXISTS public.linkedin_voice (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('comment', 'reply', 'message', 'post', 'position')),
    lang TEXT,
    topic TEXT,
    stance TEXT,
    text TEXT NOT NULL,
    context TEXT,           -- what it answered: the post, the reply, the person
    instruction TEXT,       -- your request when the AI drafted it
    post_url TEXT,
    ref TEXT,               -- source row ("engagement:12"), so a text is recorded once
    pinned BOOLEAN NOT NULL DEFAULT FALSE,   -- always in the prompt, whatever the topic
    used_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_linkedin_voice_ref ON public.linkedin_voice (ref) WHERE ref IS NOT NULL;

-- the AI's reading of a draft (topic + stance) and your request, kept until you send it
ALTER TABLE public.linkedin_engagement ADD COLUMN IF NOT EXISTS topic TEXT;
ALTER TABLE public.linkedin_engagement ADD COLUMN IF NOT EXISTS stance TEXT;
ALTER TABLE public.linkedin_engagement ADD COLUMN IF NOT EXISTS instruction TEXT;

-- direct message to a connection (drafted in the app, sent by you on LinkedIn)
ALTER TABLE public.linkedin_prospects ADD COLUMN IF NOT EXISTS message_draft TEXT;
ALTER TABLE public.linkedin_prospects ADD COLUMN IF NOT EXISTS message_sent_at TIMESTAMP WITH TIME ZONE;

CREATE TABLE IF NOT EXISTS public.linkedin_networking_plans (
    id SERIAL PRIMARY KEY,
    job_ids INTEGER[] NOT NULL DEFAULT '{}',
    plan JSONB NOT NULL,
    done TEXT[] NOT NULL DEFAULT '{}',   -- "companies:0", "people:3"… items you ticked off
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
