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
    match_threshold: float = 0.5
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
                "filter_document_id": None
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
                document_id=UUID(item["document_id"]),
                content=item["content"],
                similarity=similarity,
                page_number=item.get("page_number"),
                source_label=item.get("source_label"),
                metadata=item.get("metadata") or {}
            )
        )
        
    return results
