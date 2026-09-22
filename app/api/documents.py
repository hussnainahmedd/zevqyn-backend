"""API routes for Global Documents."""

from __future__ import annotations

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.document import DocumentResponse
from app.services import documents as document_service

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
async def list_global_documents(
    workspace_id: Optional[UUID] = Query(None, description="Filter by workspace ID"),
    file_type: Optional[str] = Query(None, description="Filter by file type/extension"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    search: Optional[str] = Query(None, description="Filter by filename substring"),
    limit: int = Query(50, ge=1, le=100, description="Max number of documents to return"),
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """List all documents owned by the authenticated user across workspaces."""
    return document_service.get_user_documents(
        user_id=user.id,
        workspace_id=workspace_id,
        file_type=file_type,
        status_filter=status,
        search=search,
        limit=limit,
        offset=offset,
    )
