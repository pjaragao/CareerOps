-- Migration V17: replies to your comments, and the LinkedIn inbox (invitations and conversations).
-- Applied with migrations_v15 by AutomationService.ensure_schema (startup). Idempotent.
--
-- reply_scan (read)  : the notifications page → "X replied to your comment" → one thread_read per new notice
-- thread_read (read) : opens the post, reads post + your comment + the reply → the AI decides: like only, or reply
-- reply (write)      : answers the reply (waits for your OK) — likes it too
-- like (write)       : only likes the reply (goes on its own)
-- inbox_scan (read)  : received invitations + unread conversations → translation, origin, suggestion
-- message (write)    : sends a chat message (a polite no to a service offer goes on its own; anything else waits for your OK)

ALTER TABLE public.automation_actions DROP CONSTRAINT IF EXISTS automation_actions_kind_check;
ALTER TABLE public.automation_actions ADD CONSTRAINT automation_actions_kind_check
    CHECK (kind IN ('apply', 'comment', 'follow', 'connect', 'search', 'check', 'feed_scan', 'follow_scan', 'saved_import',
                    'reply_scan', 'thread_read', 'reply', 'like', 'inbox_scan', 'message'));

INSERT INTO public.automation_limits (kind, period, step0, step1, step2) VALUES
    ('reply', 'day', 5, 8, 12),
    ('like', 'day', 10, 15, 25),
    ('message', 'day', 5, 8, 12),
    ('reply_scan', 'day', 3, 3, 3),
    ('thread_read', 'day', 20, 20, 20),
    ('inbox_scan', 'day', 4, 4, 4)
ON CONFLICT (kind) DO NOTHING;

-- A reply someone left to one of your comments. notice_key is what the notification points at (the comment's URL with
-- its commentUrn, or the notice text): seen twice, handled once.
CREATE TABLE IF NOT EXISTS public.linkedin_comment_replies (
    id SERIAL PRIMARY KEY,
    notice_key TEXT NOT NULL UNIQUE,
    post_url TEXT NOT NULL,
    notice_text TEXT,
    post_text TEXT,
    post_author TEXT,
    my_comment TEXT,
    reply_text TEXT,
    reply_author TEXT,
    decision TEXT CHECK (decision IS NULL OR decision IN ('like', 'reply', 'ignore')),
    reason TEXT,
    draft TEXT,
    lang TEXT,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'read', 'proposed', 'done', 'skipped', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- One row per person/conversation in the inbox: an invitation (kind invite) or a chat (kind chat). last_key is the
-- last message already handled, so a new message from them is news and an old one is not.
CREATE TABLE IF NOT EXISTS public.linkedin_conversations (
    id SERIAL PRIMARY KEY,
    conv_key TEXT NOT NULL UNIQUE,              -- invite:<profile slug> or chat:<thread id>
    kind TEXT NOT NULL CHECK (kind IN ('invite', 'chat')),
    thread_url TEXT,
    profile_url TEXT,
    name TEXT,
    headline TEXT,
    category TEXT,                              -- recruiter, service_offer, networking, job_seeker, other
    confidence REAL,
    lang TEXT,                                  -- ISO code of their language (pt, en, es, de…)
    last_key TEXT,
    last_message TEXT,
    translation TEXT,                           -- of their last message, into Portuguese (empty when already PT)
    origin TEXT,                                -- how they likely found you (a comment of yours, an invite of yours…)
    suggestion TEXT,
    es_notice_given BOOLEAN NOT NULL DEFAULT FALSE,
    translator_notice_given BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'notified', 'proposed', 'declined', 'done', 'ignored')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS linkedin_conversations_profile_idx ON public.linkedin_conversations (profile_url);
