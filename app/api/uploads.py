"""API routes for file uploads (profile pictures, etc.).

Uploads go to Supabase Storage via the backend admin client, so no
storage RLS policies or dashboard setup are needed. Files are validated
before upload: images only, max 5 MB.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.supabase import SupabaseConfigError, get_admin_client

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

BUCKET = "portfolio-images"
MAX_BYTES = 5 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def _ensure_bucket(client) -> None:
    """Create the public bucket if it does not exist yet."""
    try:
        buckets = client.storage.list_buckets()
        if any(getattr(b, "name", b.get("name") if isinstance(b, dict) else None) == BUCKET for b in buckets):
            return
    except Exception:
        pass  # fall through and try to create
    try:
        client.storage.create_bucket(BUCKET, options={"public": True})
    except Exception as e:
        # Bucket may already exist (race) — verify before failing.
        try:
            buckets = client.storage.list_buckets()
            if any(getattr(b, "name", b.get("name") if isinstance(b, dict) else None) == BUCKET for b in buckets):
                return
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Could not prepare image storage: {e}")


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Upload a profile/cover image. Returns the public URL."""
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WebP or GIF images are allowed.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image must be 5 MB or smaller.")

    try:
        client = get_admin_client()
    except SupabaseConfigError as e:
        raise HTTPException(status_code=500, detail=str(e))

    _ensure_bucket(client)

    ext = EXT_BY_TYPE[content_type]
    path = f"{user.id}/{uuid.uuid4().hex}.{ext}"
    try:
        client.storage.from_(BUCKET).upload(
            path, data, {"content-type": content_type, "upsert": "false"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    url = client.storage.from_(BUCKET).get_public_url(path)
    return {"url": url}
