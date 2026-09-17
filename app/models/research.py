"""Pydantic models for Research AI generation endpoints."""

from __future__ import annotations

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.rag import Citation


class ResearchRequest(BaseModel):
    """Base request for research features."""
    document_id: Optional[UUID] = None


class QuestionRequest(ResearchRequest):
    """Request to generate study questions."""
    count: int = Field(5, ge=1, le=20)


class FlashcardRequest(ResearchRequest):
    """Request to generate flashcards."""
    count: int = Field(10, ge=1, le=20)


class KeyPointRequest(ResearchRequest):
    """Request to generate key points."""
    count: int = Field(8, ge=1, le=10)


# Models for output

class SummaryResponse(BaseModel):
    """Response for research summary."""
    summary: str
    citations: list[Citation]
    scope: str


class KeyPoint(BaseModel):
    """A single key point."""
    text: str
    citations: list[Citation]


class KeyPointsResponse(BaseModel):
    """Response for key points."""
    key_points: list[KeyPoint]
    scope: str


class GeneratedQuestion(BaseModel):
    """A single generated question."""
    question: str
    answer: str
    difficulty: str = Field(default="medium")
    citations: list[Citation]


class QuestionsResponse(BaseModel):
    """Response for generated questions."""
    questions: list[GeneratedQuestion]
    scope: str


class GeneratedFlashcard(BaseModel):
    """A single generated flashcard."""
    front: str
    back: str
    citations: list[Citation]


class FlashcardsResponse(BaseModel):
    """Response for generated flashcards."""
    flashcards: list[GeneratedFlashcard]
    scope: str


# Gemini Structured Outputs (internal schemas without Citation objects, we map them later)

class _GeminiKeyPoint(BaseModel):
    text: str
    source_ids: list[str] = Field(description="List of SOURCE_N markers used.")

class _GeminiKeyPointsOutput(BaseModel):
    key_points: list[_GeminiKeyPoint]


class _GeminiQuestion(BaseModel):
    question: str
    answer: str
    difficulty: str = Field(description="easy, medium, or hard")
    source_ids: list[str] = Field(description="List of SOURCE_N markers used.")

class _GeminiQuestionsOutput(BaseModel):
    questions: list[_GeminiQuestion]


class _GeminiFlashcard(BaseModel):
    front: str
    back: str
    source_ids: list[str] = Field(description="List of SOURCE_N markers used.")

class _GeminiFlashcardsOutput(BaseModel):
    flashcards: list[_GeminiFlashcard]
