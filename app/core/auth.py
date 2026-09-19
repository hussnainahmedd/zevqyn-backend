"""Authentication module for ZEVQYN.

Validates Supabase access tokens and provides a reusable FastAPI
dependency that returns an ``AuthenticatedUser`` for protected endpoints.

Security
--------
* Tokens are validated server-side via Supabase Auth (``get_user``),
  NOT by local JWT decoding alone.
* The access token is **never** stored in the user model or returned
  in API responses.
* The admin/service-role client is used for the ``get_user`` call
  because it has the authority to validate any user's token.
* Client-supplied ``user_id`` parameters must **never** be trusted for
  ownership — always use ``AuthenticatedUser.id`` from this dependency.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.supabase import SupabaseConfigError, get_admin_client

# ---------------------------------------------------------------------------
# Bearer token extraction
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(
    description="Supabase access token obtained from Supabase Auth",
)


# ---------------------------------------------------------------------------
# Authenticated user model
# ---------------------------------------------------------------------------
class AuthenticatedUser(BaseModel):
    """Minimal verified-user context for protected endpoints.

    Never includes the access token, refresh token, password, or
    any secret keys.
    """

    id: UUID
    email: str | None = None
    app_metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """FastAPI dependency — validate the Bearer token and return the user.

    Raises ``HTTPException(401)`` for invalid/expired/missing tokens.
    Raises ``HTTPException(503)`` if Supabase is unreachable or
    misconfigured.
    """
    token = credentials.credentials

    try:
        client = get_admin_client()
    except SupabaseConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured",
        )

    try:
        response = client.auth.get_user(token)
    except Exception:
        # Catch all Supabase/network errors without leaking details
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if response is None or response.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = response.user
    raw_app_meta = getattr(user, "app_metadata", None)
    app_metadata = raw_app_meta if isinstance(raw_app_meta, dict) else {}

    return AuthenticatedUser(
        id=UUID(user.id),
        email=user.email,
        app_metadata=app_metadata,
    )


async def require_admin_user(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """FastAPI dependency — verify that the authenticated user has admin privileges.

    Enforces that the user's verified Supabase app_metadata has role == 'admin'.
    Unauthenticated requests yield 401 (via get_current_user).
    Authenticated non-admin requests yield 403.
    """
    role = user.app_metadata.get("role") if isinstance(user.app_metadata, dict) else None
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user

