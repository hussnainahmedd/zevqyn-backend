"""Pydantic models for contact form submissions and inbox management."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ContactSubject = Literal["Support", "Feedback", "Partnership", "Bug", "Other"]
ContactStatus = Literal["new", "read", "replied", "archived"]

# RFC 5322 compatible email pattern for dependency-free validation
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)


class ContactMessageCreate(BaseModel):
    """Public contact message submission payload."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=254)
    subject: ContactSubject
    message: str = Field(..., min_length=10, max_length=1500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Name must be at least 2 characters long")
        return trimmed

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        trimmed = v.strip().lower()
        if not EMAIL_REGEX.match(trimmed):
            raise ValueError("Invalid email address format")
        return trimmed

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 10:
            raise ValueError("Message must be at least 10 characters long")
        return trimmed


class ContactSubmitResponse(BaseModel):
    """Clean response returned upon successful public contact submission."""

    success: bool = True
    message: str = "Your message has been received."
    id: UUID


class ContactStatusUpdate(BaseModel):
    """Admin request payload to update message review status."""

    model_config = ConfigDict(extra="forbid")
    status: ContactStatus


class ContactMessageResponse(BaseModel):
    """Representation of a persisted contact message for admin inbox."""

    id: UUID
    name: str
    email: str
    subject: str
    message: str
    status: str
    created_at: datetime
