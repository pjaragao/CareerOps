-- Tables the Autopilot works with, as they were before migrations_v15 (schema only, for the tests).
CREATE TYPE public.company_type AS ENUM ('DIRECT_EMPLOYER', 'RECRUITMENT_AGENCY', 'JOB_PLATFORM');
--
--

--
--

CREATE TABLE public.companies (
    id integer NOT NULL,
    name text NOT NULL,
    career_site_url text,
    description text,
    logo_url text,
    industry text,
    tech_stack text,
    remote_policy text,
    domain text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    company_type public.company_type DEFAULT 'DIRECT_EMPLOYER'::public.company_type
);

--
--

CREATE SEQUENCE public.companies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
--

ALTER SEQUENCE public.companies_id_seq OWNED BY public.companies.id;

--
--

CREATE TABLE public.job_listings (
    id integer NOT NULL,
    linkedin_job_id character varying(50),
    url text NOT NULL,
    status character varying(20) DEFAULT 'new'::character varying,
    job_title text,
    company text,
    location text,
    description text,
    language character varying(5),
    file_name text,
    scraped_at timestamp with time zone,
    generated_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    easy_apply boolean DEFAULT false,
    company_description text,
    company_profile_url text,
    hiring_team_json text,
    cover_letter text,
    custom_prompt text,
    archetype character varying(50),
    evaluation_score numeric(3,2),
    email_draft text,
    linkedin_dm_draft text,
    recruiter_email character varying(255),
    recruiter_linkedin_url text,
    applied_via_bot boolean DEFAULT false,
    application_cost_tokens integer DEFAULT 0,
    resume_markdown text,
    company_id integer,
    eligibility_status text,
    eligibility_issues jsonb DEFAULT '[]'::jsonb NOT NULL,
    eligibility_checked_at timestamp with time zone,
    auto_docs_at timestamp with time zone
);

--
--

CREATE SEQUENCE public.job_listings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
--

ALTER SEQUENCE public.job_listings_id_seq OWNED BY public.job_listings.id;

--
--

CREATE TABLE public.linkedin_engagement (
    id integer NOT NULL,
    post_url text,
    author_name text,
    author_headline text,
    post_text text NOT NULL,
    relevance integer,
    reason text,
    comment_draft text,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    done_at timestamp with time zone,
    topic text,
    stance text,
    instruction text,
    CONSTRAINT linkedin_engagement_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'done'::text, 'skipped'::text])))
);

--
--

CREATE SEQUENCE public.linkedin_engagement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
--

ALTER SEQUENCE public.linkedin_engagement_id_seq OWNED BY public.linkedin_engagement.id;

--
--

CREATE TABLE public.linkedin_networking_plans (
    id integer NOT NULL,
    job_ids integer[] DEFAULT '{}'::integer[] NOT NULL,
    plan jsonb NOT NULL,
    done text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

--
--

CREATE SEQUENCE public.linkedin_networking_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
--

ALTER SEQUENCE public.linkedin_networking_plans_id_seq OWNED BY public.linkedin_networking_plans.id;

--
--

CREATE TABLE public.linkedin_prospects (
    id integer NOT NULL,
    profile_url text,
    name text,
    headline text,
    company text,
    profile_text text,
    segment text,
    fit integer,
    reason text,
    note_draft text,
    status text DEFAULT 'to_contact'::text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    market text,
    message_draft text,
    message_sent_at timestamp with time zone,
    CONSTRAINT linkedin_prospects_market_check CHECK (((market IS NULL) OR (market = ANY (ARRAY['br'::text, 'intl'::text])))),
    CONSTRAINT linkedin_prospects_status_check CHECK ((status = ANY (ARRAY['to_contact'::text, 'invited'::text, 'accepted'::text, 'replied'::text, 'skipped'::text])))
);

--
--

CREATE SEQUENCE public.linkedin_prospects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
--

ALTER SEQUENCE public.linkedin_prospects_id_seq OWNED BY public.linkedin_prospects.id;

--
--

CREATE TABLE public.linkedin_voice (
    id integer NOT NULL,
    kind text NOT NULL,
    lang text,
    topic text,
    stance text,
    text text NOT NULL,
    context text,
    instruction text,
    post_url text,
    ref text,
    pinned boolean DEFAULT false NOT NULL,
    used_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT linkedin_voice_kind_check CHECK ((kind = ANY (ARRAY['comment'::text, 'reply'::text, 'message'::text, 'post'::text, 'position'::text])))
);

--
--

CREATE SEQUENCE public.linkedin_voice_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
--

ALTER SEQUENCE public.linkedin_voice_id_seq OWNED BY public.linkedin_voice.id;

--
--

ALTER TABLE ONLY public.companies ALTER COLUMN id SET DEFAULT nextval('public.companies_id_seq'::regclass);

--
--

ALTER TABLE ONLY public.job_listings ALTER COLUMN id SET DEFAULT nextval('public.job_listings_id_seq'::regclass);

--
--

ALTER TABLE ONLY public.linkedin_engagement ALTER COLUMN id SET DEFAULT nextval('public.linkedin_engagement_id_seq'::regclass);

--
--

ALTER TABLE ONLY public.linkedin_networking_plans ALTER COLUMN id SET DEFAULT nextval('public.linkedin_networking_plans_id_seq'::regclass);

--
--

ALTER TABLE ONLY public.linkedin_prospects ALTER COLUMN id SET DEFAULT nextval('public.linkedin_prospects_id_seq'::regclass);

--
--

ALTER TABLE ONLY public.linkedin_voice ALTER COLUMN id SET DEFAULT nextval('public.linkedin_voice_id_seq'::regclass);

--
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_name_key UNIQUE (name);

--
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_pkey PRIMARY KEY (id);

--
--

ALTER TABLE ONLY public.job_listings
    ADD CONSTRAINT job_listings_linkedin_job_id_key UNIQUE (linkedin_job_id);

--
--

ALTER TABLE ONLY public.job_listings
    ADD CONSTRAINT job_listings_pkey PRIMARY KEY (id);

--
--

ALTER TABLE ONLY public.job_listings
    ADD CONSTRAINT job_listings_url_key UNIQUE (url);

--
--

ALTER TABLE ONLY public.linkedin_engagement
    ADD CONSTRAINT linkedin_engagement_pkey PRIMARY KEY (id);

--
--

ALTER TABLE ONLY public.linkedin_networking_plans
    ADD CONSTRAINT linkedin_networking_plans_pkey PRIMARY KEY (id);

--
--

ALTER TABLE ONLY public.linkedin_prospects
    ADD CONSTRAINT linkedin_prospects_pkey PRIMARY KEY (id);

--
--

ALTER TABLE ONLY public.linkedin_voice
    ADD CONSTRAINT linkedin_voice_pkey PRIMARY KEY (id);

--
--

CREATE INDEX idx_companies_domain ON public.companies USING btree (domain);

--
--

CREATE INDEX idx_companies_name ON public.companies USING btree (name);

--
--

CREATE INDEX idx_job_listings_company_id ON public.job_listings USING btree (company_id);

--
--

CREATE INDEX idx_job_listings_linkedin_job_id ON public.job_listings USING btree (linkedin_job_id);

--
--

CREATE INDEX idx_job_listings_status ON public.job_listings USING btree (status);

--
--

CREATE UNIQUE INDEX uq_linkedin_engagement_url ON public.linkedin_engagement USING btree (post_url) WHERE (post_url IS NOT NULL);

--
--

CREATE UNIQUE INDEX uq_linkedin_prospects_url ON public.linkedin_prospects USING btree (profile_url) WHERE (profile_url IS NOT NULL);

--
--

CREATE UNIQUE INDEX uq_linkedin_voice_ref ON public.linkedin_voice USING btree (ref) WHERE (ref IS NOT NULL);

--
--

ALTER TABLE ONLY public.job_listings
    ADD CONSTRAINT job_listings_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id);

--
--

