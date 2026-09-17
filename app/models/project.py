"""Pydantic models for projects and research-to-project."""

from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.rag import Citation


# Database Models
class ProjectCreate(BaseModel):
    """Request to explicitly create a project (from scratch or accepted preview)."""
    title: str = Field(..., min_length=1, max_length=200)
    short_description: str = Field(..., max_length=500)
    description: str = Field(..., max_length=5000)
    technologies: list[str] = Field(default_factory=list, max_length=20)
    skills: list[str] = Field(default_factory=list, max_length=20)
    github_url: Optional[str] = Field(None, max_length=500)
    live_url: Optional[str] = Field(None, max_length=500)
    image_url: Optional[str] = Field(None, max_length=500)
    visibility: str = Field("private", pattern="^(public|private)$")
    workspace_id: Optional[UUID] = None
    source_document_id: Optional[UUID] = None


class ProjectUpdate(BaseModel):
    """Request to update a project."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    short_description: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    technologies: Optional[list[str]] = Field(None, max_length=20)
    skills: Optional[list[str]] = Field(None, max_length=20)
    github_url: Optional[str] = Field(None, max_length=500)
    live_url: Optional[str] = Field(None, max_length=500)
    image_url: Optional[str] = Field(None, max_length=500)
    visibility: Optional[str] = Field(None, pattern="^(public|private)$")
    featured: Optional[bool] = None


class ProjectResponse(BaseModel):
    """Public representation of a project."""
    id: UUID
    user_id: UUID
    workspace_id: Optional[UUID] = None
    source_document_id: Optional[UUID] = None
    title: str
    short_description: str
    description: str
    technologies: list[str]
    skills: list[str]
    github_url: Optional[str] = None
    live_url: Optional[str] = None
    image_url: Optional[str] = None
    visibility: str
    featured: bool
    created_at: datetime
    updated_at: datetime


# AI Generation Models
class ResearchProjectRequest(BaseModel):
    """Request to generate a project proposal from research."""
    document_id: Optional[UUID] = None
    instructions: str = Field(default="Turn this research into a practical project", max_length=1000)


class ProjectProposalPreview(BaseModel):
    """Preview of a generated project before it is saved."""
    title: str
    short_description: str
    description: str
    problem_statement: str
    suggested_features: list[str]
    suggested_technologies: list[str]
    suggested_skills: list[str]
    citations: list[Citation]

class _GeminiProjectProposal(BaseModel):
    """Internal model for strictly parsing Gemini's project output."""
    title: str
    short_description: str
    description: str
    problem_statement: str
    suggested_features: list[str]
    suggested_technologies: list[str]
    suggested_skills: list[str]
    source_ids: list[str]
