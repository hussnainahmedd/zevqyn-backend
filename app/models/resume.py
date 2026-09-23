"""Pydantic models for Resumes and Resume Items."""

from __future__ import annotations

from typing import Optional, Any
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ==============================================================================
# RESUMES
# ==============================================================================
class ResumeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=200)
    template: str = Field("professional", max_length=100)
    professional_summary: Optional[str] = Field(None, max_length=2000)
    visibility: str = Field("private", pattern="^(public|private)$")
    full_name: Optional[str] = Field(None, max_length=150)
    professional_title: Optional[str] = Field(None, max_length=150)
    email: Optional[str] = Field(None, max_length=254)
    phone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=150)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    github_url: Optional[str] = Field(None, max_length=500)
    portfolio_url: Optional[str] = Field(None, max_length=500)


class ResumeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    template: Optional[str] = Field(None, max_length=100)
    professional_summary: Optional[str] = Field(None, max_length=2000)
    visibility: Optional[str] = Field(None, pattern="^(public|private)$")
    full_name: Optional[str] = Field(None, max_length=150)
    professional_title: Optional[str] = Field(None, max_length=150)
    email: Optional[str] = Field(None, max_length=254)
    phone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=150)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    github_url: Optional[str] = Field(None, max_length=500)
    portfolio_url: Optional[str] = Field(None, max_length=500)


class ResumeResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    template: str
    professional_summary: Optional[str] = None
    visibility: str
    full_name: Optional[str] = None
    professional_title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
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
    sort_order: Optional[int] = Field(None, ge=0)


class ResumeItemReorderEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    sort_order: int = Field(..., ge=0)


class ResumeItemsReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ResumeItemReorderEntry] = Field(..., min_length=1)

    @field_validator("items")
    @classmethod
    def check_unique_ids(cls, v: list[ResumeItemReorderEntry]) -> list[ResumeItemReorderEntry]:
        ids = [item.id for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate item IDs in reorder request")
        return v


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
