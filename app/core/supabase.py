"""Supabase client factory.

Provides a lazily-created *admin* (service-role) client for trusted
backend operations.  The client is NOT created at import time so that
basic endpoints (``/``, ``/health``) can start without Supabase
credentials.

Security
--------
* The admin client uses ``SUPABASE_SECRET_KEY`` — it bypasses Row Level
  Security and must **never** be exposed to frontend code or API
  responses.
* ``SUPABASE_PUBLISHABLE_KEY`` is kept in ``Settings`` for future
  user-scoped / authenticated operations but is not used in this module.
"""

from __future__ import annotations

from supabase import Client, create_client

from app.core.config import settings


class SupabaseConfigError(Exception):
    """Raised when required Supabase environment variables are missing."""


# ---------------------------------------------------------------------------
# Admin (service-role) client — singleton
# ---------------------------------------------------------------------------
_admin_client: Client | None = None


def get_admin_client() -> Client:
    """Return the privileged Supabase admin client (lazy singleton).

    Raises ``SupabaseConfigError`` if ``SUPABASE_URL`` or
    ``SUPABASE_SECRET_KEY`` are not configured.
    """
    global _admin_client
    if _admin_client is not None:
        return _admin_client

    if not settings.SUPABASE_URL:
        raise SupabaseConfigError(
            "SUPABASE_URL is not configured. "
            "Set it in your .env file."
        )
    if not settings.SUPABASE_SECRET_KEY:
        raise SupabaseConfigError(
            "SUPABASE_SECRET_KEY is not configured. "
            "Set it in your .env file."
        )

    _admin_client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SECRET_KEY,
    )
    return _admin_client


def reset_admin_client() -> None:
    """Discard the cached admin client (useful for testing)."""
    global _admin_client
    _admin_client = None
