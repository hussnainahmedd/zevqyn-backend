"""Gemini embeddings service."""

from __future__ import annotations

from fastapi import HTTPException, status
from google import genai
from google.genai import types

from app.core.config import settings

_gemini_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """Lazy initialization of the Gemini client."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
        
    if not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API is not configured"
        )
        
    _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


def _embed_content(texts: list[str], task_type: str) -> list[list[float]]:
    """Internal helper to call Gemini embedding API."""
    if not texts:
        return []
        
    client = get_gemini_client()
    
    config = types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=768,
    )
    
    try:
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=texts,
            config=config
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate embeddings via Gemini API"
        )
        
    # Validation
    embeddings = []
    if not response.embeddings:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No embeddings returned from Gemini API"
        )
        
    for emb in response.embeddings:
        if len(emb.values) != 768:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected embedding dimension: {len(emb.values)} (expected 768)"
            )
        embeddings.append(emb.values)
        
    return embeddings


def embed_document(texts: list[str]) -> list[list[float]]:
    """Generate 768-d embeddings for document chunks."""
    # Process in batches if list is large to avoid payload limits
    # Gemini usually supports ~100 texts per request. We'll use 50 to be safe.
    batch_size = 50
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embs = _embed_content(batch, "RETRIEVAL_DOCUMENT")
        all_embeddings.extend(batch_embs)
        
    return all_embeddings


def embed_query(text: str) -> list[float]:
    """Generate a single 768-d embedding for a search query."""
    embeddings = _embed_content([text], "RETRIEVAL_QUERY")
    return embeddings[0]
