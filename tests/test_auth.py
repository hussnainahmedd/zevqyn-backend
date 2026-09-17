"""Unit tests for the authentication module and /api/v1/me endpoint.

All tests use mocks — no real Supabase credentials or network needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FAKE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
FAKE_EMAIL = "test@zevqyn.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_supabase_user(*, uid: str = FAKE_UUID, email: str | None = FAKE_EMAIL):
    """Build a mock Supabase UserResponse."""
    user = MagicMock()
    user.id = uid
    user.email = email
    response = MagicMock()
    response.user = user
    return response


# ---------------------------------------------------------------------------
# Missing / malformed auth
# ---------------------------------------------------------------------------

class TestMissingAuth:
    """Requests without valid credentials must be rejected."""

    def test_no_auth_header(self):
        r = client.get("/api/v1/me")
        assert r.status_code == 401

    def test_empty_bearer(self):
        r = client.get("/api/v1/me", headers={"Authorization": "Bearer "})
        assert r.status_code == 401

    def test_wrong_scheme(self):
        r = client.get("/api/v1/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert r.status_code == 401

    def test_garbage_header(self):
        r = client.get("/api/v1/me", headers={"Authorization": "not-a-real-header"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Invalid token
# ---------------------------------------------------------------------------

class TestInvalidToken:
    """Tokens that Supabase rejects must yield 401."""

    @patch("app.core.auth.get_admin_client")
    def test_supabase_rejects_token(self, mock_get):
        mock_get.return_value.auth.get_user.side_effect = Exception("invalid")
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer fake-invalid-token"},
        )
        assert r.status_code == 401
        body = r.json()
        assert "invalid" in body["detail"].lower() or "expired" in body["detail"].lower()
        # Must NOT leak the internal exception message
        assert "fake-invalid-token" not in body.get("detail", "")

    @patch("app.core.auth.get_admin_client")
    def test_supabase_returns_none_user(self, mock_get):
        response = MagicMock()
        response.user = None
        mock_get.return_value.auth.get_user.return_value = response
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer token-with-null-user"},
        )
        assert r.status_code == 401

    @patch("app.core.auth.get_admin_client")
    def test_supabase_returns_none_response(self, mock_get):
        mock_get.return_value.auth.get_user.return_value = None
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer token-none-response"},
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Valid token
# ---------------------------------------------------------------------------

class TestValidToken:
    """Successfully authenticated requests must return user info."""

    @patch("app.core.auth.get_admin_client")
    def test_returns_uuid_and_email(self, mock_get):
        mock_get.return_value.auth.get_user.return_value = _mock_supabase_user()
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer valid-token"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == FAKE_UUID
        assert body["email"] == FAKE_EMAIL

    @patch("app.core.auth.get_admin_client")
    def test_email_null_when_missing(self, mock_get):
        mock_get.return_value.auth.get_user.return_value = _mock_supabase_user(
            email=None
        )
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer valid-token"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == FAKE_UUID
        assert body["email"] is None

    @patch("app.core.auth.get_admin_client")
    def test_token_not_in_response(self, mock_get):
        mock_get.return_value.auth.get_user.return_value = _mock_supabase_user()
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer super-secret-token"},
        )
        assert r.status_code == 200
        body_text = r.text
        assert "super-secret-token" not in body_text

    @patch("app.core.auth.get_admin_client")
    def test_response_has_no_secret_fields(self, mock_get):
        mock_get.return_value.auth.get_user.return_value = _mock_supabase_user()
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer valid-token"},
        )
        body = r.json()
        # Only id and email should be present
        assert set(body.keys()) == {"id", "email"}


# ---------------------------------------------------------------------------
# Supabase config errors
# ---------------------------------------------------------------------------

class TestSupabaseConfigFailure:
    """Auth must not crash if Supabase is misconfigured."""

    @patch("app.core.auth.get_admin_client")
    def test_missing_config_returns_503(self, mock_get):
        from app.core.supabase import SupabaseConfigError

        mock_get.side_effect = SupabaseConfigError("not configured")
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer some-token"},
        )
        assert r.status_code == 503
        assert "not configured" not in r.json().get("detail", "").lower() or \
               "authentication service" in r.json().get("detail", "").lower()
