"""Pydantic models for workspace endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    """Request body for creating a workspace."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class WorkspaceUpdate(BaseModel):
    """Request body for updating a workspace (all fields optional)."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceResponse(BaseModel):
    """Public workspace representation returned by the API."""
    id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
