"""Unit tests for the Supabase integration layer (mocked).

These tests run without internet or real credentials by mocking the
supabase client.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.supabase import (
    SupabaseConfigError,
    get_admin_client,
    reset_admin_client,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_client():
    """Ensure every test starts with a fresh (uncached) admin client."""
    reset_admin_client()
    yield
    reset_admin_client()


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

class TestAdminClientConfig:
    """get_admin_client must fail clearly when config is missing."""

    def test_missing_url_raises(self):
        with patch("app.core.supabase.settings") as mock_settings:
            mock_settings.SUPABASE_URL = ""
            mock_settings.SUPABASE_SECRET_KEY = "sk-fake"
            with pytest.raises(SupabaseConfigError, match="SUPABASE_URL"):
                get_admin_client()

    def test_missing_secret_key_raises(self):
        with patch("app.core.supabase.settings") as mock_settings:
            mock_settings.SUPABASE_URL = "https://fake.supabase.co"
            mock_settings.SUPABASE_SECRET_KEY = ""
            with pytest.raises(SupabaseConfigError, match="SUPABASE_SECRET_KEY"):
                get_admin_client()

    def test_both_missing_raises_url_first(self):
        with patch("app.core.supabase.settings") as mock_settings:
            mock_settings.SUPABASE_URL = ""
            mock_settings.SUPABASE_SECRET_KEY = ""
            with pytest.raises(SupabaseConfigError, match="SUPABASE_URL"):
                get_admin_client()


# ---------------------------------------------------------------------------
# Client creation
# ---------------------------------------------------------------------------

class TestAdminClientCreation:
    """get_admin_client should create and cache a client when config is valid."""

    @patch("app.core.supabase.create_client")
    def test_creates_client_with_correct_args(self, mock_create):
        mock_create.return_value = MagicMock()
        with patch("app.core.supabase.settings") as mock_settings:
            mock_settings.SUPABASE_URL = "https://fake.supabase.co"
            mock_settings.SUPABASE_SECRET_KEY = "sk-fake-secret"

            client = get_admin_client()

            mock_create.assert_called_once_with(
                "https://fake.supabase.co",
                "sk-fake-secret",
            )
            assert client is mock_create.return_value

    @patch("app.core.supabase.create_client")
    def test_returns_cached_singleton(self, mock_create):
        mock_create.return_value = MagicMock()
        with patch("app.core.supabase.settings") as mock_settings:
            mock_settings.SUPABASE_URL = "https://fake.supabase.co"
            mock_settings.SUPABASE_SECRET_KEY = "sk-fake-secret"

            first = get_admin_client()
            second = get_admin_client()

            assert first is second
            assert mock_create.call_count == 1


# ---------------------------------------------------------------------------
# Service verification helpers (mocked)
# ---------------------------------------------------------------------------

class TestVerifyDatabase:
    """verify_database_connection with a mocked Supabase client."""

    @patch("app.services.supabase_verify.get_admin_client")
    def test_success(self, mock_get):
        # Simulate a successful profiles query
        mock_response = MagicMock()
        mock_response.data = []
        mock_get.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response

        from app.services.supabase_verify import verify_database_connection

        assert verify_database_connection() is True

    @patch("app.services.supabase_verify.get_admin_client")
    def test_unexpected_format_raises(self, mock_get):
        mock_response = MagicMock()
        mock_response.data = None  # unexpected
        mock_get.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response

        from app.services.supabase_verify import verify_database_connection

        with pytest.raises(RuntimeError, match="Unexpected response"):
            verify_database_connection()


class TestVerifyStorage:
    """verify_storage_access with a mocked Supabase client."""

    @patch("app.services.supabase_verify.get_admin_client")
    def test_success(self, mock_get):
        mock_bucket = MagicMock()
        mock_get.return_value.storage.get_bucket.return_value = mock_bucket

        from app.services.supabase_verify import verify_storage_access

        assert verify_storage_access() is True
        mock_get.return_value.storage.get_bucket.assert_called_once_with(
            "research-documents"
        )

    @patch("app.services.supabase_verify.get_admin_client")
    def test_bucket_not_found_raises(self, mock_get):
        mock_get.return_value.storage.get_bucket.return_value = None

        from app.services.supabase_verify import verify_storage_access

        with pytest.raises(RuntimeError, match="research-documents"):
            verify_storage_access()
