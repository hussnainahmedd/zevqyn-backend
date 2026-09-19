-- ==========================================================================================
-- Migration: Create contact_messages table for marketing website contact form
-- ==========================================================================================

CREATE TABLE IF NOT EXISTS public.contact_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT contact_messages_status_check CHECK (status IN ('new', 'read', 'replied', 'archived')),
    CONSTRAINT contact_messages_subject_check CHECK (subject IN ('Support', 'Feedback', 'Partnership', 'Bug', 'Other'))
);

CREATE INDEX IF NOT EXISTS idx_contact_messages_status ON public.contact_messages(status);
CREATE INDEX IF NOT EXISTS idx_contact_messages_created_at ON public.contact_messages(created_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE public.contact_messages ENABLE ROW LEVEL SECURITY;

-- Notice on Security:
-- No public policies are created for anon/authenticated roles.
-- Direct browser access through Supabase client/REST is strictly forbidden.
-- Inserts and administrative reads are performed exclusively by the FastAPI backend
-- using the privileged service-role key (which bypasses RLS).
