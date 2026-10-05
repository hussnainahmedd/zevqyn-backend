"""Admin panel API — user management, stats, and admin auth.

All routes here require the dedicated admin session token
(``POST /api/v1/admin/login``), EXCEPT ``/login`` itself.

Security
--------
* Admin credentials live in the ``admin_users`` table (PBKDF2 hashes),
  never in code or logs.
* Login is strictly rate-limited per IP; failures return generic 401s.
* User management goes through the Supabase Auth *admin* API with the
  service-role key — it never touches end-user sessions.
* Client-supplied user IDs are path parameters only; ownership is not
  inferred from them.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.admin_auth import (
    change_admin_password,
    create_admin_token,
    get_admin_principal,
    verify_admin_credentials,
)
from app.core.rate_limit import limiter
from app.core.supabase import SupabaseConfigError, get_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    banned: bool | None = None


class AdminUserSummary(BaseModel):
    id: str
    email: str | None
    full_name: str | None = None
    created_at: str | None = None
    last_sign_in_at: str | None = None
    banned: bool = False


# ---------------------------------------------------------------------------
# Helpers — Supabase Auth admin API
# ---------------------------------------------------------------------------


def _summarize(user: Any) -> AdminUserSummary:
    meta = getattr(user, "user_metadata", None) or {}
    banned_until = getattr(user, "banned_until", None)
    return AdminUserSummary(
        id=str(getattr(user, "id", "")),
        email=getattr(user, "email", None),
        full_name=meta.get("full_name") if isinstance(meta, dict) else None,
        created_at=str(getattr(user, "created_at", "") or "") or None,
        last_sign_in_at=str(getattr(user, "last_sign_in_at", "") or "") or None,
        banned=bool(banned_until),
    )


def _auth_admin():
    try:
        return get_admin_client().auth.admin
    except SupabaseConfigError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User directory is not configured",
        ) from e


# ---------------------------------------------------------------------------
# 1. Admin auth
# ---------------------------------------------------------------------------


@router.post("/login", response_model=AdminLoginResponse)
@limiter.limit("10/minute")
async def admin_login(request: Request, data: AdminLoginRequest):
    """Exchange admin ID + password for a 12-hour session token."""
    if not verify_admin_credentials(data.username, data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )
    return AdminLoginResponse(access_token=create_admin_token(data.username.strip()))


@router.post("/change-password")
async def admin_change_password(
    data: ChangePasswordRequest,
    admin: str = Depends(get_admin_principal),
):
    """Change the admin password (current password required)."""
    if not change_admin_password(admin, data.current_password, data.new_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    return {"success": True, "message": "Admin password updated."}


# ---------------------------------------------------------------------------
# 2. User directory (Supabase Auth users)
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[AdminUserSummary])
async def list_users(
    page: int = 1,
    per_page: int = 50,
    admin: str = Depends(get_admin_principal),
):
    """List end users (paginated)."""
    page = max(1, page)
    per_page = min(max(1, per_page), 100)
    try:
        users = _auth_admin().list_users(page=page, per_page=per_page)
    except Exception as e:
        logger.error("Admin list_users failed: %r", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not load users",
        ) from e
    return [_summarize(u) for u in users]


@router.post("/users", response_model=AdminUserSummary, status_code=status.HTTP_201_CREATED)
async def create_user(data: AdminUserCreate, admin: str = Depends(get_admin_principal)):
    """Manually create an end user (email pre-confirmed)."""
    attrs: dict[str, Any] = {
        "email": str(data.email),
        "password": data.password,
        "email_confirm": True,
    }
    if data.full_name:
        attrs["user_metadata"] = {"full_name": data.full_name}
    try:
        res = _auth_admin().create_user(attrs)
    except Exception as e:
        logger.error("Admin create_user failed: %r", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create user (email may already exist)",
        ) from e
    user = getattr(res, "user", None) or res
    return _summarize(user)


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
async def update_user(
    user_id: str, data: AdminUserUpdate, admin: str = Depends(get_admin_principal)
):
    """Update email / password / banned state of an end user."""
    attrs: dict[str, Any] = {}
    if data.email is not None:
        attrs["email"] = str(data.email)
    if data.password is not None:
        attrs["password"] = data.password
    if data.banned is not None:
        attrs["ban_duration"] = "8760h" if data.banned else "none"
    if not attrs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update"
        )
    try:
        res = _auth_admin().update_user_by_id(user_id, attrs)
    except Exception as e:
        logger.error("Admin update_user failed: %r", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update user"
        ) from e
    user = getattr(res, "user", None) or res
    return _summarize(user)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: str = Depends(get_admin_principal)):
    """Delete an end user permanently (auth record only)."""
    try:
        _auth_admin().delete_user(user_id)
    except Exception as e:
        logger.error("Admin delete_user failed: %r", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not delete user"
        ) from e
    return {"success": True}


# ---------------------------------------------------------------------------
# 3. Stats
# ---------------------------------------------------------------------------


def _count(table: str) -> int | None:
    try:
        client = get_admin_client()
        res = client.table(table).select("id", count="exact").limit(1).execute()
        return res.count
    except Exception:
        return None


@router.get("/stats")
async def admin_stats(admin: str = Depends(get_admin_principal)):
    """Rough platform totals for the admin dashboard."""
    total_users: int | None = None
    try:
        users = _auth_admin().list_users(page=1, per_page=1000)
        total_users = len(users)
    except Exception:
        pass
    return {
        "users": total_users,
        "workspaces": _count("workspaces"),
        "documents": _count("documents"),
        "projects": _count("projects"),
        "contact_messages": _count("contact_messages"),
    }
