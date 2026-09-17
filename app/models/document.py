"""Pydantic models for document endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Public document metadata returned by the API.

    Never includes storage_path, credentials, or internal details.
    """
    id: UUID
    user_id: UUID
    workspace_id: UUID
    original_filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime
    updated_at: datetime | None = None


class DocumentDownloadResponse(BaseModel):
    """Short-lived signed URL for downloading a private document."""
    url: str
    expires_in_seconds: int = 60
