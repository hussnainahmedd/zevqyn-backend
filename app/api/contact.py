"""API routes for public contact submission and protected inbox management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.contact import (
    ContactMessageCreate,
    ContactMessageResponse,
    ContactStatusUpdate,
    ContactSubmitResponse,
)
from app.services import contact as contact_service

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])


async def require_admin_user(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """FastAPI dependency to verify administrative privileges for contact message management.

    SECURITY NOTE:
    ZEVQYN currently lacks an admin-role / RBAC model on users and profiles.
    Allowing any authenticated student/user to inspect or modify contact messages would
    compromise customer privacy and data isolation.

    Therefore, access to contact management routes is safely disabled (HTTP 403)
    until an admin authorization mechanism (e.g. Supabase user metadata role or
    a dedicated role column on profiles) is implemented.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin authorization is not configured. Access to contact messages is disabled.",
    )


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
# 2. ADMIN INBOX MANAGEMENT (SAFELY DISABLED UNTIL ADMIN RBAC IS CONFIGURED)
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
