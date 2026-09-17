"""Pydantic models for Resumes and Resume Items."""

from __future__ import annotations

from typing import Optional, Any
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# RESUMES
# ==============================================================================
class ResumeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=200)
    template: str = Field("professional", max_length=100)
    professional_summary: Optional[str] = Field(None, max_length=2000)
    visibility: str = Field("private", pattern="^(public|private)$")


class ResumeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    template: Optional[str] = Field(None, max_length=100)
    professional_summary: Optional[str] = Field(None, max_length=2000)
    visibility: Optional[str] = Field(None, pattern="^(public|private)$")


class ResumeResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    template: str
    professional_summary: Optional[str] = None
    visibility: str
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# RESUME ITEMS
# ==============================================================================
class ResumeItemCreate(BaseModel):
    """Client provides the trusted source_id. We fetch title/subtitle/desc securely."""
    model_config = ConfigDict(extra="forbid")
    section_type: str = Field(..., pattern="^(project|skill|education|certificate)$")
    source_id: UUID
    sort_order: Optional[int] = Field(0)


class ResumeItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sort_order: Optional[int] = Field(None)


class ResumeItemResponse(BaseModel):
    id: UUID
    resume_id: UUID
    section_type: str
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    sort_order: int
    created_at: datetime
    updated_at: datetime
