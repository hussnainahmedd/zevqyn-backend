"""API routes for public contact submission and protected inbox management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.auth import AuthenticatedUser, require_admin_user
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
async def submit_contact_message(
    data: ContactMessageCreate,
):
    """Public endpoint for submitting marketing website contact messages.

    Does NOT require authentication or access tokens.
    """
    return contact_service.create_contact_message(data)


# ==============================================================================
# 2. ADMIN INBOX MANAGEMENT (REQUIRES APP_METADATA.ROLE == 'ADMIN')
# ==============================================================================
@router.get("/messages", response_model=list[ContactMessageResponse])
async def list_contact_messages(
    admin: AuthenticatedUser = Depends(require_admin_user),
):
    """List all contact inquiries (admin only)."""
    return contact_service.get_contact_messages()


@router.get("/messages/{message_id}", response_model=ContactMessageResponse)
async def get_contact_message_detail(
    message_id: UUID,
    admin: AuthenticatedUser = Depends(require_admin_user),
):
    """Retrieve details for a single contact inquiry (admin only)."""
    return contact_service.get_contact_message(message_id)


@router.patch("/messages/{message_id}", response_model=ContactMessageResponse)
async def update_contact_message(
    message_id: UUID,
    update: ContactStatusUpdate,
    admin: AuthenticatedUser = Depends(require_admin_user),
):
    """Update review status of a contact inquiry (admin only)."""
    return contact_service.update_contact_message_status(message_id, update)
