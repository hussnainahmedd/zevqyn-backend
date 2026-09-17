"""Retrieval service for searching indexed documents."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase import get_admin_client
from app.models.chunking import RetrievedChunk
from app.services.embeddings import embed_query


def search_workspace(
    user_id: UUID, 
    workspace_id: UUID, 
    query: str, 
    match_count: int = 5,
    match_threshold: float = 0.5,
    document_id: UUID | None = None
) -> list[RetrievedChunk]:
    """Retrieve semantically relevant chunks for a given query in a workspace."""
    if not query.strip():
        return []
        
    # Generate query embedding
    try:
        query_embedding = embed_query(query)
    except Exception as e:
        raise e  # Already a safe HTTPException from embed_query
        
    client = get_admin_client()
    
    # Call Supabase RPC
    try:
        response = client.rpc(
            "match_document_chunks",
            {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count,
                "filter_user_id": str(user_id),
                "filter_workspace_id": str(workspace_id),
                "filter_document_id": str(document_id) if document_id else None
            }
        ).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute search query"
        )
        
    if not response.data:
        return []
        
    # Parse results
    results = []
    for item in response.data:
        # Protect against schema mismatches if RPC is not updated yet
        similarity = item.get("similarity", 0.0)
        
        # If the RPC returns raw chunks we map them:
        results.append(
            RetrievedChunk(
                chunk_id=UUID(item["id"]),
                document_id=UUID(item["document_id"]),
                content=item["content"],
                similarity=similarity,
                page_number=item.get("page_number"),
                source_label=item.get("source_label"),
                metadata=item.get("metadata") or {}
            )
        )
        
    return results

def get_representative_chunks(
    user_id: UUID,
    workspace_id: UUID,
    document_id: UUID | None = None,
    limit: int = 50
) -> list[RetrievedChunk]:
    """Retrieve representative chunks from a workspace or document for broad summaries.
    
    Implements deterministic broad sampling across documents/chunks:
    - If chunks fit within limit, uses all.
    - If not, samples evenly from beginning, middle, and end.
    - Preserves original document order.
    - Distributes workspace budget reasonably across available documents.
    """
    client = get_admin_client()
    
    try:
        if document_id:
            # Document scope
            target_doc_ids = [str(document_id)]
        else:
            # Workspace scope
            docs_res = client.table("documents").select("id").eq("workspace_id", str(workspace_id)).eq("user_id", str(user_id)).order("created_at", desc=False).execute()
            if not docs_res.data:
                return []
            target_doc_ids = [d["id"] for d in docs_res.data]
            
        if not target_doc_ids:
            return []
            
        # Distribute budget
        num_docs = len(target_doc_ids)
        
        # If we have more docs than limit, take the most recent ones
        if num_docs > limit:
            target_doc_ids = target_doc_ids[-limit:]
            num_docs = len(target_doc_ids)
            
        limit_per_doc = max(1, limit // num_docs)
        
        selected_chunk_ids = []
        
        for did in target_doc_ids:
            # Get all chunk IDs and indices for this document
            idx_res = client.table("document_chunks").select("id, chunk_index").eq("user_id", str(user_id)).eq("document_id", did).order("chunk_index", desc=False).execute()
            doc_chunks = idx_res.data
            
            if not doc_chunks:
                continue
                
            n_chunks = len(doc_chunks)
            if n_chunks <= limit_per_doc:
                # Fits within budget
                selected_chunk_ids.extend([c["id"] for c in doc_chunks])
            else:
                # Sample evenly across the document: must include first and last
                if limit_per_doc == 1:
                    selected_chunk_ids.append(doc_chunks[0]["id"])
                else:
                    step = (n_chunks - 1) / (limit_per_doc - 1)
                    indices = set()
                    for i in range(limit_per_doc):
                        idx = int(round(i * step))
                        idx = min(max(idx, 0), n_chunks - 1)
                        if idx not in indices:
                            indices.add(idx)
                            selected_chunk_ids.append(doc_chunks[idx]["id"])
                    
                    # If due to rounding/budget we have fewer unique than expected,
                    # we can pad, but a set guarantees no duplicates. Order is maintained by the append.
                    
        if not selected_chunk_ids:
            return []
            
        # Now fetch the actual chunk content for the selected IDs
        # To maintain order, we just fetch them all and sort them in Python
        # Because IN query doesn't guarantee order.
        
        # We might have more than 100 ids, so chunk the queries if needed, 
        # but max limit is 50, so one query is fine.
        chunks_res = client.table("document_chunks").select("id, document_id, content, page_number, source_label, metadata, chunk_index").in_("id", selected_chunk_ids).execute()
        
        fetched_chunks = chunks_res.data
        
        # Sort by document_id index (to preserve doc order) then chunk_index
        doc_order = {did: i for i, did in enumerate(target_doc_ids)}
        
        def sort_key(c):
            return (doc_order.get(c["document_id"], 999), c.get("chunk_index", 0))
            
        fetched_chunks.sort(key=sort_key)
        
        results = []
        for item in fetched_chunks:
            results.append(
                RetrievedChunk(
                    chunk_id=UUID(item["id"]),
                    document_id=UUID(item["document_id"]),
                    content=item["content"],
                    similarity=None, # Not a semantic search
                    page_number=item.get("page_number"),
                    source_label=item.get("source_label"),
                    metadata=item.get("metadata") or {}
                )
            )
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve representative chunks")
