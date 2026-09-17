"""Pydantic models for Portfolios and Portfolio Projects."""

from __future__ import annotations

from typing import Optional, Any
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from app.models.project import ProjectResponse

# ==============================================================================
# PORTFOLIOS
# ==============================================================================
class PortfolioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(..., min_length=3, max_length=100, pattern="^[a-zA-Z0-9_-]+$")
    display_name: str = Field(..., min_length=1, max_length=200)
    headline: Optional[str] = Field(None, max_length=200)
    about: Optional[str] = Field(None, max_length=2000)
    profile_image_url: Optional[str] = Field(None, max_length=500)
    theme: str = Field("light", max_length=50)
    is_published: bool = Field(False)
    show_resume: bool = Field(False)
    show_research: bool = Field(False)
    show_certificates: bool = Field(False)
    show_contact: bool = Field(False)
    github_url: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    website_url: Optional[str] = Field(None, max_length=500)


class PortfolioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: Optional[str] = Field(None, min_length=3, max_length=100, pattern="^[a-zA-Z0-9_-]+$")
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    headline: Optional[str] = Field(None, max_length=200)
    about: Optional[str] = Field(None, max_length=2000)
    profile_image_url: Optional[str] = Field(None, max_length=500)
    theme: Optional[str] = Field(None, max_length=50)
    is_published: Optional[bool] = Field(None)
    show_resume: Optional[bool] = Field(None)
    show_research: Optional[bool] = Field(None)
    show_certificates: Optional[bool] = Field(None)
    show_contact: Optional[bool] = Field(None)
    github_url: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    website_url: Optional[str] = Field(None, max_length=500)


class PortfolioResponse(BaseModel):
    id: UUID
    user_id: UUID
    slug: str
    display_name: str
    headline: Optional[str] = None
    about: Optional[str] = None
    profile_image_url: Optional[str] = None
    theme: str
    is_published: bool
    show_resume: bool
    show_research: bool
    show_certificates: bool
    show_contact: bool
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    website_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# PORTFOLIO PROJECTS
# ==============================================================================
class PortfolioProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    sort_order: Optional[int] = Field(0)


class PortfolioProjectResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    project_id: UUID
    sort_order: int
    created_at: datetime


# ==============================================================================
# PUBLIC SERIALIZATION
# ==============================================================================
class PublicPortfolioProject(BaseModel):
    title: str
    short_description: str
    description: str
    technologies: list[str]
    skills: list[str]
    github_url: Optional[str]
    live_url: Optional[str]
    image_url: Optional[str]

class PublicPortfolioResponse(BaseModel):
    """Safely exposes only intended public information."""
    slug: str
    display_name: str
    headline: Optional[str]
    about: Optional[str]
    profile_image_url: Optional[str]
    theme: str
    github_url: Optional[str]
    linkedin_url: Optional[str]
    website_url: Optional[str]
    
    projects: list[PublicPortfolioProject]
    # No user UUID, email, or private career fields exposed by default.
