"""API routes for public contact submission and protected inbox management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.core.admin_auth import require_admin_combined
from app.core.rate_limit import limiter
from app.models.contact import (
    ContactMessageCreate,
    ContactMessageResponse,
    ContactStatusUpdate,
    ContactSubmitResponse,
)
from app.services import contact as contact_service

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])


# ==============================================================================
# 1. PUBLIC CONTACT SUBMISSION
# ==============================================================================
@router.post("", response_model=ContactSubmitResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def submit_contact_message(
    request: Request,
    data: ContactMessageCreate,
):
    """Public endpoint for submitting marketing website contact messages.

    Does NOT require authentication or access tokens. Rate-limited per IP
    to prevent spam/abuse.
    """
    return contact_service.create_contact_message(data)


# ==============================================================================
# 2. ADMIN INBOX MANAGEMENT (admin panel JWT or legacy app_metadata.role == 'admin')
# ==============================================================================
@router.get("/messages", response_model=list[ContactMessageResponse])
async def list_contact_messages(
    admin: str = Depends(require_admin_combined),
):
    """List all contact inquiries (admin only)."""
    return contact_service.get_contact_messages()


@router.get("/messages/{message_id}", response_model=ContactMessageResponse)
async def get_contact_message_detail(
    message_id: UUID,
    admin: str = Depends(require_admin_combined),
):
    """Retrieve details for a single contact inquiry (admin only)."""
    return contact_service.get_contact_message(message_id)


@router.patch("/messages/{message_id}", response_model=ContactMessageResponse)
async def update_contact_message(
    message_id: UUID,
    update: ContactStatusUpdate,
    admin: str = Depends(require_admin_combined),
):
    """Update review status of a contact inquiry (admin only)."""
    return contact_service.update_contact_message_status(message_id, update)
