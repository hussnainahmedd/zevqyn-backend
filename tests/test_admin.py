"""Unit tests for the admin-panel auth and /api/v1/admin/* endpoints.

All tests use mocks — no real Supabase credentials or network needed.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core import admin_auth
from app.main import app

client = TestClient(app)

TEST_SECRET = "test-admin-jwt-secret-for-unit-tests-only"


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setattr(admin_auth.settings, "ADMIN_JWT_SECRET", TEST_SECRET)


def _token(username: str = "boss") -> str:
    return admin_auth.create_admin_token(username)


def _auth(username: str = "boss") -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(username)}"}


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_round_trip(self):
        h = admin_auth.hash_password("correct-horse-123")
        assert admin_auth.verify_password("correct-horse-123", h) is True

    def test_wrong_password_fails(self):
        h = admin_auth.hash_password("correct-horse-123")
        assert admin_auth.verify_password("wrong-password", h) is False

    def test_malformed_stored_hash_fails(self):
        assert admin_auth.verify_password("x", "not-a-hash") is False
        assert admin_auth.verify_password("x", "") is False

    def test_hashes_differ_per_call(self):
        assert admin_auth.hash_password("same") != admin_auth.hash_password("same")


# ---------------------------------------------------------------------------
# Admin JWT
# ---------------------------------------------------------------------------


class TestAdminJwt:
    def test_token_round_trip(self):
        assert admin_auth._decode_admin_token(_token("boss")) == "boss"

    def test_tampered_token_rejected(self):
        tok = _token("boss")
        bad = tok[:-2] + ("aa" if not tok.endswith("aa") else "bb")
        assert admin_auth._decode_admin_token(bad) is None

    def test_wrong_scope_rejected(self, monkeypatch):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        tok = pyjwt.encode(
            {"sub": "boss", "iat": now, "exp": now + timedelta(hours=1)},
            TEST_SECRET,
            algorithm="HS256",
        )
        assert admin_auth._decode_admin_token(tok) is None


# ---------------------------------------------------------------------------
# /login
# ---------------------------------------------------------------------------


class TestAdminLogin:
    def test_success(self):
        with patch("app.api.admin.verify_admin_credentials", return_value=True):
            r = client.post(
                "/api/v1/admin/login",
                json={"username": "boss", "password": "s3cret!"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert admin_auth._decode_admin_token(body["access_token"]) == "boss"

    def test_bad_credentials_generic_401(self):
        with patch("app.api.admin.verify_admin_credentials", return_value=False):
            r = client.post(
                "/api/v1/admin/login",
                json={"username": "boss", "password": "nope"},
            )
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid admin credentials"

    def test_missing_fields_422(self):
        r = client.post("/api/v1/admin/login", json={"username": "boss"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Protected routes require the admin token
# ---------------------------------------------------------------------------


class TestAdminGating:
    @pytest.mark.parametrize("path", ["/api/v1/admin/users", "/api/v1/admin/stats"])
    def test_no_token_401_or_403(self, path):
        r = client.get(path)
        assert r.status_code in (401, 403)

    def test_garbage_token_rejected(self):
        r = client.get(
            "/api/v1/admin/users", headers={"Authorization": "Bearer garbage"}
        )
        assert r.status_code == 401

    def test_valid_token_reaches_handler(self):
        with patch("app.api.admin._auth_admin") as mock_admin:
            mock_admin.return_value.list_users.return_value = []
            r = client.get("/api/v1/admin/users", headers=_auth())
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# /change-password
# ---------------------------------------------------------------------------


class TestChangePassword:
    def test_success(self):
        with patch("app.api.admin.change_admin_password", return_value=True):
            r = client.post(
                "/api/v1/admin/change-password",
                headers=_auth(),
                json={"current_password": "old-one-123", "new_password": "new-one-456"},
            )
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_wrong_current_password_401(self):
        with patch("app.api.admin.change_admin_password", return_value=False):
            r = client.post(
                "/api/v1/admin/change-password",
                headers=_auth(),
                json={"current_password": "wrong", "new_password": "new-one-456"},
            )
        assert r.status_code == 401

    def test_short_new_password_422(self):
        r = client.post(
            "/api/v1/admin/change-password",
            headers=_auth(),
            json={"current_password": "old-one-123", "new_password": "short"},
        )
        assert r.status_code == 422

    def test_no_token_rejected(self):
        r = client.post(
            "/api/v1/admin/change-password",
            json={"current_password": "a", "new_password": "b" * 9},
        )
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Seed logic never overwrites
# ---------------------------------------------------------------------------


class TestSeed:
    def test_no_env_no_seed(self, monkeypatch):
        monkeypatch.setattr(admin_auth.settings, "ADMIN_ID", "")
        monkeypatch.setattr(admin_auth.settings, "ADMIN_PASSWORD", "")
        assert admin_auth.ensure_seed_admin() is False

    def test_existing_row_not_overwritten(self, monkeypatch):
        monkeypatch.setattr(admin_auth.settings, "ADMIN_ID", "boss")
        monkeypatch.setattr(admin_auth.settings, "ADMIN_PASSWORD", "s3cret!")
        with patch.object(admin_auth, "get_admin_client") as mock_client:
            mock_client.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = (
                type("R", (), {"data": [{"id": "x"}]})()
            )
            assert admin_auth.ensure_seed_admin() is False
            # insert must never be called when a row exists
            mock_client.return_value.table.return_value.insert.assert_not_called()
