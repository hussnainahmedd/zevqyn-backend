"""v1 API router — protected endpoints under ``/api/v1/``."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/me")
async def me(user: AuthenticatedUser = Depends(get_current_user)):
    """Return the authenticated user's identity.

    The user ID and email are derived from the verified Supabase token —
    they are **never** accepted as client-supplied parameters.
    """
    return {
        "id": str(user.id),
        "email": user.email,
    }
