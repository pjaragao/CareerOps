-- Migration V14: general CVs (not tied to a job) for job-board sign-ups (We Work Remotely and the like)
--   target_title     = the role the CV is aimed at; the ATS review and the form suggestions are measured against it
--   review           = last ATS-style review: {"score", "categories": [...], "strengths": [...], "issues": [...], "keywords": {...}}
--   form_suggestions = what to answer in sign-up forms: target titles, experience level, job status, salary range, ...
-- Applied on startup too (main.py), so a fresh deploy never misses it.
CREATE TABLE IF NOT EXISTS public.general_resumes (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    lang TEXT NOT NULL DEFAULT 'en',
    target_title TEXT NOT NULL DEFAULT '',
    used_on TEXT NOT NULL DEFAULT '',
    content_md TEXT NOT NULL DEFAULT '',
    review JSONB,
    review_at TIMESTAMP WITH TIME ZONE,
    form_suggestions JSONB,
    form_suggestions_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
