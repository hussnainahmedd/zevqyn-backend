"""Dedicated admin-panel authentication for ZEVQYN.

The admin panel (user management, inbox, stats) is gated by its OWN
credential system, separate from Supabase Auth end users:

* ``admin_users`` table holds ``username`` + PBKDF2-HMAC-SHA256 password hash.
* First admin is seeded on startup from ``ADMIN_ID`` / ``ADMIN_PASSWORD``
  env vars, but ONLY when the table is empty — the seed never overwrites.
  The password can be changed later from the admin UI.
* ``POST /api/v1/admin/login`` verifies the password and returns a short
  lived JWT signed with ``ADMIN_JWT_SECRET`` (HS256, 12h expiry).
* ``require_admin_token`` validates that JWT for protected admin routes.
* ``require_admin`` accepts EITHER the new admin JWT or the legacy
  Supabase ``app_metadata.role == "admin"`` check, so the contact inbox
  keeps working for both login styles during migration.

Security notes
--------------
* Passwords are hashed with PBKDF2-HMAC-SHA256 (260k iterations, 32-byte
  random salt); verification uses ``hmac.compare_digest``.
* Login failures always return a generic 401 — never reveal whether the
  username exists.
* The login route is rate-limited per IP (see ``app/api/admin.py``).
* ``ADMIN_JWT_SECRET`` must be a long random value in production; tokens
  are rejected when it is not configured.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.supabase import SupabaseConfigError, get_admin_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing — PBKDF2-HMAC-SHA256 (stdlib, no new dependency)
# ---------------------------------------------------------------------------

_PBKDF2_ITERATIONS = 260_000
_SALT_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a password. Format: ``pbkdf2$<iterations>$<salt_hex>$<hash_hex>``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time password verification. Never raises on bad input."""
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Seed — create the first admin from env, only when the table is empty
# ---------------------------------------------------------------------------


def ensure_seed_admin() -> bool:
    """Seed the initial admin row if the table is empty and env is set.

    Returns True when a row was created. Never overwrites existing rows.
    Never raises — startup must not crash if Supabase is unreachable.
    """
    if not settings.ADMIN_ID or not settings.ADMIN_PASSWORD:
        return False
    try:
        client = get_admin_client()
    except SupabaseConfigError as e:
        logger.warning("Admin seed skipped: %s", e)
        return False
    try:
        existing = client.table("admin_users").select("id").limit(1).execute()
        if existing.data:
            return False
        client.table("admin_users").insert(
            {
                "username": settings.ADMIN_ID.strip(),
                "password_hash": hash_password(settings.ADMIN_PASSWORD),
            }
        ).execute()
        logger.info("Seeded initial admin user '%s'.", settings.ADMIN_ID.strip())
        return True
    except Exception as e:
        logger.warning("Admin seed failed: %r", e)
        return False


def _get_admin_row(username: str) -> dict | None:
    client = get_admin_client()
    res = (
        client.table("admin_users")
        .select("id,username,password_hash")
        .eq("username", username)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def verify_admin_credentials(username: str, password: str) -> bool:
    """Check admin ID + password. Generic False on any failure (no leaks)."""
    try:
        row = _get_admin_row(username.strip())
    except (SupabaseConfigError, Exception):
        return False
    if not row:
        # Run a dummy verify to keep timing roughly uniform.
        verify_password(password, "pbkdf2$260000$" + "00" * 32 + "$" + "00" * 32)
        return False
    return verify_password(password, row["password_hash"])


def change_admin_password(username: str, current_password: str, new_password: str) -> bool:
    """Verify current password, then store the new hash. Returns success."""
    try:
        row = _get_admin_row(username.strip())
    except (SupabaseConfigError, Exception):
        return False
    if not row or not verify_password(current_password, row["password_hash"]):
        return False
    try:
        client = get_admin_client()
        client.table("admin_users").update(
            {"password_hash": hash_password(new_password)}
        ).eq("id", row["id"]).execute()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Admin session tokens (PyJWT, HS256)
# ---------------------------------------------------------------------------

_TOKEN_TTL = timedelta(hours=12)
_admin_bearer = HTTPBearer(description="Admin panel session token")


def _jwt_secret() -> str:
    secret = settings.ADMIN_JWT_SECRET
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured",
        )
    return secret


def create_admin_token(username: str) -> str:
    """Mint a 12-hour admin session JWT."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": username, "iat": now, "exp": now + _TOKEN_TTL, "scope": "zevqyn-admin"},
        _jwt_secret(),
        algorithm="HS256",
    )


def _decode_admin_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token, _jwt_secret(), algorithms=["HS256"], options={"require": ["exp", "sub"]}
        )
    except Exception:
        return None
    if payload.get("scope") != "zevqyn-admin":
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub else None


async def get_admin_principal(
    credentials: HTTPAuthorizationCredentials = Depends(_admin_bearer),
) -> str:
    """FastAPI dependency — validate the admin JWT, return the username."""
    username = _decode_admin_token(credentials.credentials)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


async def require_admin_combined(
    credentials: HTTPAuthorizationCredentials = Depends(_admin_bearer),
) -> str:
    """Admin gate accepting new JWT first, legacy Supabase role second."""
    username = _decode_admin_token(credentials.credentials)
    if username:
        return username
    # Legacy path: validate the Supabase token and its admin role.
    user = await get_current_user(credentials)
    role = user.app_metadata.get("role") if isinstance(user.app_metadata, dict) else None
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return f"supabase:{user.email or user.id}"
