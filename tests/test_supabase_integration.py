"""Integration test — verify real Supabase connectivity.

Run manually with:
    python -m pytest tests/test_supabase_integration.py -v

Requires a valid .env with SUPABASE_URL and SUPABASE_SECRET_KEY.
This file is excluded from the default test suite (marked with the
``integration`` pytest marker) so that ``pytest`` alone only runs fast
offline tests.

SECURITY: This script never prints credentials or database contents.
"""

from __future__ import annotations

import pytest

from app.core.supabase import SupabaseConfigError, reset_admin_client

# Mark every test in this module as integration
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _fresh_client():
    reset_admin_client()
    yield
    reset_admin_client()


def test_database_connection():
    """Verify read-only connectivity to the profiles table."""
    from app.services.supabase_verify import verify_database_connection

    try:
        result = verify_database_connection()
        assert result is True
        print("Database connection: OK")
    except SupabaseConfigError:
        pytest.skip("Supabase credentials not configured in .env")


def test_storage_access():
    """Verify access to the research-documents bucket."""
    from app.services.supabase_verify import verify_storage_access

    try:
        result = verify_storage_access()
        assert result is True
        print("Storage access: OK")
    except SupabaseConfigError:
        pytest.skip("Supabase credentials not configured in .env")
