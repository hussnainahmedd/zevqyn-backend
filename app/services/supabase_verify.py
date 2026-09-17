"""Service-layer functions for Supabase connectivity verification.

These are internal helpers used by tests and development scripts — not
wired to any public API endpoint.
"""

from __future__ import annotations

from app.core.supabase import get_admin_client


def verify_database_connection() -> bool:
    """Perform a minimal read-only query against the ``profiles`` table.

    Returns ``True`` if the query succeeds. Raises on failure so the
    caller can inspect the error.

    The query selects only ``id``, limits to 1 row, and discards the
    result — it is completely harmless.
    """
    client = get_admin_client()
    response = client.table("profiles").select("id").limit(1).execute()
    # response.data is a list; an empty list is fine (table may be empty)
    if not isinstance(response.data, list):
        raise RuntimeError("Unexpected response format from Supabase")
    return True


def verify_storage_access() -> bool:
    """Check that the ``research-documents`` bucket is accessible.

    Returns ``True`` if the bucket metadata can be read.  Does **not**
    upload, delete, or modify any files.
    """
    client = get_admin_client()
    bucket = client.storage.get_bucket("research-documents")
    if bucket is None:
        raise RuntimeError(
            "Could not access the 'research-documents' storage bucket"
        )
    return True
