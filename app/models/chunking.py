"""Pydantic models for document chunks and indexing."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentChunk(BaseModel):
    """A generated text chunk ready for embedding/storage."""
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    source_label: Optional[str] = None
    metadata: dict = {}


class IndexingResponse(BaseModel):
    """Response returned when indexing is complete."""
    document_id: UUID
    status: str
    chunk_count: int
    embedding_dimension: int


class RetrievedChunk(BaseModel):
    """A matched chunk returned by the retrieval service."""
    document_id: UUID
    content: str
    similarity: float
    page_number: Optional[int] = None
    source_label: Optional[str] = None
    metadata: dict = {}
