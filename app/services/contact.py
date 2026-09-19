"""Service layer for contact message storage and management."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase import get_admin_client
from app.models.contact import (
    ContactMessageCreate,
    ContactMessageResponse,
    ContactStatusUpdate,
    ContactSubmitResponse,
)

logger = logging.getLogger(__name__)


def create_contact_message(data: ContactMessageCreate) -> ContactSubmitResponse:
    """Persist a new contact submission using the privileged backend client.

    Bypasses RLS to insert into backend-owned table. Catches database errors
    and raises safe HTTP exceptions without exposing database internals.
    """
    client = get_admin_client()

    insert_payload = {
        "name": data.name,
        "email": data.email,
        "subject": data.subject,
        "message": data.message,
        "status": "new",
    }

    try:
        res = client.table("contact_messages").insert(insert_payload).execute()
        if not res.data:
            raise ValueError("Database returned no data after insert")
        created = res.data[0]
        return ContactSubmitResponse(
            success=True,
            message="Your message has been received.",
            id=UUID(created["id"]),
        )
    except Exception as e:
        logger.error("Failed to insert contact message: %s", repr(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit contact message",
        )


def get_contact_messages() -> list[ContactMessageResponse]:
    """Retrieve all contact messages ordered newest first."""
    client = get_admin_client()
    try:
        res = (
            client.table("contact_messages")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return [ContactMessageResponse(**row) for row in res.data or []]
    except Exception as e:
        logger.error("Failed to fetch contact messages: %s", repr(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve contact messages",
        )


def get_contact_message(message_id: UUID) -> ContactMessageResponse:
    """Retrieve a single contact message by its UUID."""
    client = get_admin_client()
    try:
        res = (
            client.table("contact_messages")
            .select("*")
            .eq("id", str(message_id))
            .execute()
        )
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact message not found",
            )
        return ContactMessageResponse(**res.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch contact message %s: %s", message_id, repr(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve contact message",
        )


def update_contact_message_status(
    message_id: UUID, update: ContactStatusUpdate
) -> ContactMessageResponse:
    """Update the review status of a contact message."""
    # Verify existence
    get_contact_message(message_id)

    client = get_admin_client()
    try:
        res = (
            client.table("contact_messages")
            .update({"status": update.status})
            .eq("id", str(message_id))
            .execute()
        )
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact message not found",
            )
        return ContactMessageResponse(**res.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update contact message %s: %s", message_id, repr(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update contact message status",
        )
