"""Document indexing pipeline."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase import get_admin_client
from app.models.chunking import IndexingResponse
from app.services.chunking import chunk_document
from app.services.documents import get_document
from app.services.embeddings import embed_document
from app.services.extraction import process_document


def index_document(user_id: UUID, workspace_id: UUID, document_id: UUID) -> IndexingResponse:
    """Run the complete document indexing pipeline."""
    # 1. Verification handled by extraction service
    
    client = get_admin_client()
    
    # 2. Extract text
    # This also sets document status to processing/processed
    try:
        extracted_doc = process_document(user_id, workspace_id, document_id)
    except Exception as e:
        # extraction service already sets status to failed, just re-raise
        raise e
        
    # 3. Chunk text
    try:
        chunks = chunk_document(extracted_doc)
    except Exception:
        # If chunking fails, mark failed
        client.table("documents").update({"status": "failed"}).eq("id", str(document_id)).execute()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to chunk document"
        )
        
    if not chunks:
        # Empty doc? We consider it processed but with 0 chunks.
        client.table("documents").update({"status": "processed"}).eq("id", str(document_id)).execute()
        return IndexingResponse(
            document_id=document_id,
            status="processed",
            chunk_count=0,
            embedding_dimension=768
        )
        
    # 4. Generate embeddings
    texts = [c.content for c in chunks]
    try:
        embeddings = embed_document(texts)
    except Exception as e:
        # If embeddings fail, mark failed, BUT do NOT delete old chunks yet.
        client.table("documents").update({"status": "failed"}).eq("id", str(document_id)).execute()
        raise e
        
    # 5. Prepare rows for Supabase insertion
    rows = []
    for chunk, emb in zip(chunks, embeddings):
        rows.append({
            "document_id": str(document_id),
            "user_id": str(user_id),
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "embedding": emb,
            "page_number": chunk.page_number,
            "source_label": chunk.source_label,
            "metadata": chunk.metadata
        })
        
    # 6. Database Replacement Strategy (Idempotent)
    # Since Supabase JS/REST doesn't support transactional insert + delete easily from Python,
    # and we don't want to leave orphaned chunks if insert fails halfway, we delete old chunks
    # FIRST, then insert. This is safe because we only reached this point if the NEW pipeline 
    # fully succeeded in memory (extraction, chunking, Gemini API).
    try:
        # Delete old chunks scoped by document AND user
        client.table("document_chunks").delete().eq("document_id", str(document_id)).eq("user_id", str(user_id)).execute()
        
        # Insert new chunks in batches to avoid payload limits if doc is huge
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            res = client.table("document_chunks").insert(batch).execute()
            if not res.data:
                raise Exception("Insert returned no data")
                
    except Exception:
        client.table("documents").update({"status": "failed"}).eq("id", str(document_id)).execute()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist indexed chunks to database"
        )
        
    # Success
    client.table("documents").update({"status": "processed"}).eq("id", str(document_id)).execute()
    
    return IndexingResponse(
        document_id=document_id,
        status="processed",
        chunk_count=len(chunks),
        embedding_dimension=768
    )
