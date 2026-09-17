-- ==========================================================================================
-- MANUAL SUPABASE SQL ACTION REQUIRED
-- ==========================================================================================
-- This file updates the existing `match_document_chunks` RPC to return the new
-- citation fields added in Phase 5: page_number, source_label, and metadata.
--
-- Please execute this exact SQL block in the Supabase SQL Editor.
-- ==========================================================================================

DROP FUNCTION IF EXISTS match_document_chunks;

CREATE OR REPLACE FUNCTION match_document_chunks(
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  filter_user_id uuid,
  filter_workspace_id uuid DEFAULT NULL,
  filter_document_id uuid DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  document_id uuid,
  content text,
  page_number int,
  source_label text,
  metadata jsonb,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.page_number,
    dc.source_label,
    dc.metadata,
    1 - (dc.embedding <=> query_embedding) AS similarity
  FROM document_chunks dc
  -- If we filter by workspace, we join documents.
  LEFT JOIN documents d ON d.id = dc.document_id
  WHERE dc.user_id = filter_user_id
    AND (filter_document_id IS NULL OR dc.document_id = filter_document_id)
    AND (filter_workspace_id IS NULL OR d.workspace_id = filter_workspace_id)
    AND 1 - (dc.embedding <=> query_embedding) > match_threshold
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
