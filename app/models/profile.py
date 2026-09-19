"""Pydantic models for user profile."""

from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ProfileUpdate(BaseModel):
    """Request payload for updating the authenticated user's profile."""
    model_config = ConfigDict(extra="forbid")

    username: Optional[str] = Field(None, min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: Optional[str] = Field(None, max_length=150)
    bio: Optional[str] = Field(None, max_length=2000)
    avatar_url: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=150)
    website: Optional[str] = Field(None, max_length=500)
    github_url: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)

    @field_validator("avatar_url", "website", "github_url", "linkedin_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() != "":
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("URL must start with http:// or https://")
        return v


class ProfileResponse(BaseModel):
    """Public representation of the authenticated user's profile."""
    id: UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
