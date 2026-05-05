-- Migration V5: Add User Documents and Knowledge Base tracking

CREATE TABLE IF NOT EXISTS public.user_documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    content_type TEXT,
    raw_text TEXT,                    -- Markdown version of the document
    processing_status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'awaiting_validation', 'validated', 'failed'
    extracted_data JSONB,             -- Raw AI extraction results
    validated_data JSONB,             -- User-approved facts
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_processed_at TIMESTAMP WITH TIME ZONE
);

-- Add column to interview_stories to trace back to source documents
ALTER TABLE public.interview_stories 
ADD COLUMN IF NOT EXISTS is_raw BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS source_doc_id INTEGER REFERENCES public.user_documents(id) ON DELETE CASCADE;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_user_documents_status ON public.user_documents(processing_status);
