"""Service for managing authenticated user profiles."""

from __future__ import annotations

from typing import Any
from uuid import UUID
from datetime import datetime, timezone
from fastapi import HTTPException

from app.core.supabase import get_admin_client
from app.models.profile import ProfileUpdate, ProfileResponse


def _create_minimal_profile(user_id: UUID) -> dict[str, Any]:
    """Ensure a minimal profile row exists for user_id in the database."""
    client = get_admin_client()
    initial_data: dict[str, Any] = {
        "id": str(user_id),
    }

    # Best-effort attempt to pre-populate full_name from Supabase Auth user_metadata
    try:
        auth_user = client.auth.admin.get_user_by_id(str(user_id))
        user_obj = getattr(auth_user, "user", None)
        if user_obj:
            user_meta = getattr(user_obj, "user_metadata", {}) or {}
            full_name = user_meta.get("full_name") or user_meta.get("name")
            if full_name and isinstance(full_name, str) and full_name.strip():
                initial_data["full_name"] = full_name.strip()
    except Exception:
        pass

    try:
        res = client.table("profiles").insert(initial_data).execute()
        if res.data:
            return res.data[0]
    except Exception:
        # In case row already exists or was created concurrently
        pass

    # Fetch to return the latest row
    try:
        fetch_res = client.table("profiles").select("*").eq("id", str(user_id)).execute()
        if fetch_res.data:
            return fetch_res.data[0]
    except Exception:
        pass

    raise HTTPException(status_code=500, detail="Failed to initialize user profile")


def get_profile(user_id: UUID) -> ProfileResponse:
    """Fetch the authenticated user's profile, automatically creating one if absent."""
    client = get_admin_client()
    try:
        res = client.table("profiles").select("*").eq("id", str(user_id)).execute()
        if res.data and len(res.data) > 0:
            return ProfileResponse(**res.data[0])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch profile")

    # Profile row does not exist yet -> create minimal profile row safely
    row = _create_minimal_profile(user_id)
    return ProfileResponse(**row)


def update_profile(user_id: UUID, profile_update: ProfileUpdate) -> ProfileResponse:
    """Update the authenticated user's profile. Creates row first if not present."""
    client = get_admin_client()

    # Ensure profile row exists
    try:
        res = client.table("profiles").select("*").eq("id", str(user_id)).execute()
        if not res.data:
            _create_minimal_profile(user_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to verify existing profile")

    data = profile_update.model_dump(exclude_unset=True)
    if not data:
        # No updates provided, return current profile
        return get_profile(user_id)

    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        update_res = client.table("profiles").update(data).eq("id", str(user_id)).execute()
        if update_res.data and len(update_res.data) > 0:
            return ProfileResponse(**update_res.data[0])
        # Fallback to re-fetching
        return get_profile(user_id)
    except Exception as e:
        err = str(e).lower()
        if "23505" in err or "duplicate key" in err or "unique constraint" in err:
            raise HTTPException(status_code=409, detail="Username is already in use")
        raise HTTPException(status_code=500, detail="Failed to update profile")
