"""Pydantic models for RAG chat and conversations."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for submitting a question to the RAG chat."""
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[UUID] = None
    document_id: Optional[UUID] = None


class Citation(BaseModel):
    """Structured citation mapping to a retrieved document chunk."""
    source_id: str
    document_id: UUID
    document_name: str
    page_number: Optional[int] = None
    source_label: Optional[str] = None
    chunk_id: UUID
    similarity: Optional[float] = None


class ChatResponse(BaseModel):
    """Response returned by the RAG chat endpoint."""
    answer: str
    citations: list[Citation]
    retrieved_chunks: int
    conversation_id: UUID
    message_id: UUID


class ConversationCreate(BaseModel):
    """Request body for creating a conversation explicitly."""
    title: str = Field(..., min_length=1, max_length=200)


class ConversationResponse(BaseModel):
    """Public representation of a conversation."""
    id: UUID
    user_id: UUID
    workspace_id: UUID
    title: str
    assistant_type: Optional[str] = None
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    """Public representation of a chat message."""
    id: UUID
    conversation_id: UUID
    user_id: UUID
    role: str
    content: str
    sources: Optional[list[dict]] = None
    created_at: str
