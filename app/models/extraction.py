"""Pydantic models for extraction endpoints."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ExtractedUnit(BaseModel):
    """A logical chunk of extracted text (e.g., page or paragraph)."""
    index: int
    text: str
    page_number: Optional[int] = None
    source_label: Optional[str] = None


class ExtractedDocument(BaseModel):
    """Structured representation of an extracted document."""
    document_id: UUID
    original_filename: str
    file_type: str
    unit_count: int
    character_count: int
    units: list[ExtractedUnit]
