"""Unit tests for Contact Messages system (public submission and admin inbox)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.contact import ContactStatusUpdate
from pydantic import ValidationError

client = TestClient(app)

FAKE_MESSAGE_ID = str(uuid.uuid4())
FAKE_USER_ID = str(uuid.uuid4())
FAKE_TOKEN = "valid-token"

VALID_PAYLOAD = {
    "name": "Ali Khan",
    "email": "ali@example.com",
    "subject": "Support",
    "message": "I need help with my portfolio project deployment.",
}


def _mock_user(
    *,
    user_id: str = FAKE_USER_ID,
    email: str = "user@example.com",
    app_metadata: dict | None = None,
    user_metadata: dict | None = None,
):
    """Build mock Supabase UserResponse with specific metadata."""
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.app_metadata = app_metadata if app_metadata is not None else {}
    user.user_metadata = user_metadata if user_metadata is not None else {}
    res = MagicMock()
    res.user = user
    return res


# ==============================================================================
# 1. PUBLIC CONTACT SUBMISSION & AUTH EXEMPTION
# ==============================================================================
@patch("app.services.contact.get_admin_client")
def test_valid_public_contact_submission(mock_db):
    """Test standard public contact submission succeeds with expected response schema."""
    mock_client = mock_db.return_value
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": FAKE_MESSAGE_ID}
    ]

    resp = client.post("/api/v1/contact", json=VALID_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["message"] == "Your message has been received."
    assert data["id"] == FAKE_MESSAGE_ID

    # Verify db insert was called with trimmed fields and default status="new"
    insert_call = mock_client.table.return_value.insert.call_args[0][0]
    assert insert_call["name"] == "Ali Khan"
    assert insert_call["email"] == "ali@example.com"
    assert insert_call["subject"] == "Support"
    assert insert_call["message"] == "I need help with my portfolio project deployment."
    assert insert_call["status"] == "new"


@patch("app.services.contact.get_admin_client")
def test_no_authorization_header_required_for_post(mock_db):
    """Verify that POST /api/v1/contact works completely anonymously without auth."""
    mock_client = mock_db.return_value
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": FAKE_MESSAGE_ID}
    ]

    resp = client.post("/api/v1/contact", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ==============================================================================
# 2. VALIDATION RULES
# ==============================================================================
@pytest.mark.parametrize(
    "invalid_email",
    [
        "not-an-email",
        "missing-at-sign.com",
        "@domain.com",
        "user@",
        "user@domain..com",
        "user@.com",
        "",
        "   ",
    ],
)
def test_invalid_email_rejected(invalid_email):
    payload = {**VALID_PAYLOAD, "email": invalid_email}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "invalid_subject",
    [
        "Sales",
        "Random",
        "Spam",
        "support",  # lowercase not allowed
        "",
        "OTHER",
    ],
)
def test_invalid_subject_rejected(invalid_subject):
    payload = {**VALID_PAYLOAD, "subject": invalid_subject}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 422


@pytest.mark.parametrize("valid_subject", ["Support", "Feedback", "Partnership", "Bug", "Other"])
@patch("app.services.contact.get_admin_client")
def test_all_valid_subjects_accepted(mock_db, valid_subject):
    mock_client = mock_db.return_value
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": FAKE_MESSAGE_ID}
    ]
    payload = {**VALID_PAYLOAD, "subject": valid_subject}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "short_name",
    [
        "A",
        " ",
        "",
        "  B  ",  # Trims to 1 char
    ],
)
def test_name_too_short_rejected(short_name):
    payload = {**VALID_PAYLOAD, "name": short_name}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 422


def test_name_too_long_rejected():
    payload = {**VALID_PAYLOAD, "name": "A" * 101}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "short_message",
    [
        "Short",
        "123456789",
        "",
        "   ",
        "  123456789  ",  # Trims to 9 chars
    ],
)
def test_message_too_short_rejected(short_message):
    payload = {**VALID_PAYLOAD, "message": short_message}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 422


def test_message_over_1500_chars_rejected():
    payload = {**VALID_PAYLOAD, "message": "x" * 1501}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 422


@patch("app.services.contact.get_admin_client")
def test_message_exactly_1500_chars_accepted(mock_db):
    mock_client = mock_db.return_value
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": FAKE_MESSAGE_ID}
    ]
    payload = {**VALID_PAYLOAD, "message": "x" * 1500}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 200


def test_extra_arbitrary_fields_rejected():
    payload = {**VALID_PAYLOAD, "extra_field": "injected", "status": "read"}
    resp = client.post("/api/v1/contact", json=payload)
    assert resp.status_code == 422


# ==============================================================================
# 3. ERROR RESILIENCE
# ==============================================================================
@patch("app.services.contact.get_admin_client")
def test_database_failure_returns_safe_error(mock_db):
    """Ensure database errors don't leak internal connection strings or stack traces."""
    mock_client = mock_db.return_value
    mock_client.table.return_value.insert.side_effect = Exception("Supabase connection timed out")

    resp = client.post("/api/v1/contact", json=VALID_PAYLOAD)
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to submit contact message"
    assert "Supabase" not in resp.text


# ==============================================================================
# 4. ADMIN MANAGEMENT & DATA ISOLATION
# ==============================================================================
@pytest.mark.parametrize(
    "endpoint,method,payload",
    [
        ("/api/v1/contact/messages", "get", None),
        (f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}", "get", None),
        (f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}", "patch", {"status": "read"}),
    ],
)
def test_management_endpoints_cannot_be_accessed_anonymously(endpoint, method, payload):
    """Anonymous visitors cannot access or mutate management routes and receive 401."""
    resp = client.request(method, endpoint, json=payload)
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "endpoint,method,payload",
    [
        ("/api/v1/contact/messages", "get", None),
        (f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}", "get", None),
        (f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}", "patch", {"status": "read"}),
    ],
)
@patch("app.core.auth.get_admin_client")
def test_normal_authenticated_user_cannot_access_management_endpoints(mock_auth, endpoint, method, payload):
    """Authenticated users without app_metadata.role == 'admin' receive 403."""
    mock_auth.return_value.auth.get_user.return_value = _mock_user(
        app_metadata={"role": "user"}
    )

    resp = client.request(
        method,
        endpoint,
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=payload,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


@pytest.mark.parametrize(
    "endpoint,method,payload",
    [
        ("/api/v1/contact/messages", "get", None),
        (f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}", "get", None),
        (f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}", "patch", {"status": "read"}),
    ],
)
@patch("app.core.auth.get_admin_client")
def test_spoofed_user_metadata_role_does_not_grant_admin(mock_auth, endpoint, method, payload):
    """Untrusted user_metadata containing role='admin' must be ignored and rejected with 403."""
    mock_auth.return_value.auth.get_user.return_value = _mock_user(
        user_metadata={"role": "admin"},  # Attacker injected into user_metadata
        app_metadata={"role": "user"},    # Trusted Supabase metadata is NOT admin
    )

    resp = client.request(
        method,
        endpoint,
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=payload,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


@patch("app.services.contact.get_admin_client")
@patch("app.core.auth.get_admin_client")
def test_admin_authenticated_user_can_list_messages(mock_auth, mock_db):
    """Admin user with app_metadata.role == 'admin' can list contact messages."""
    mock_auth.return_value.auth.get_user.return_value = _mock_user(
        app_metadata={"role": "admin"}
    )
    mock_client = mock_db.return_value
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {
            "id": FAKE_MESSAGE_ID,
            "name": "Ali Khan",
            "email": "ali@example.com",
            "subject": "Support",
            "message": "Need help with portfolio.",
            "status": "new",
            "created_at": "2026-09-19T10:00:00Z",
        }
    ]

    resp = client.get(
        "/api/v1/contact/messages",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == FAKE_MESSAGE_ID
    assert data[0]["name"] == "Ali Khan"
    assert data[0]["status"] == "new"


@patch("app.services.contact.get_admin_client")
@patch("app.core.auth.get_admin_client")
def test_admin_can_retrieve_single_message(mock_auth, mock_db):
    """Admin user can retrieve an individual message by ID."""
    mock_auth.return_value.auth.get_user.return_value = _mock_user(
        app_metadata={"role": "admin"}
    )
    mock_client = mock_db.return_value
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": FAKE_MESSAGE_ID,
            "name": "Ali Khan",
            "email": "ali@example.com",
            "subject": "Support",
            "message": "Need help with portfolio.",
            "status": "new",
            "created_at": "2026-09-19T10:00:00Z",
        }
    ]

    resp = client.get(
        f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == FAKE_MESSAGE_ID
    assert data["subject"] == "Support"


@patch("app.services.contact.get_admin_client")
@patch("app.core.auth.get_admin_client")
def test_admin_can_patch_status(mock_auth, mock_db):
    """Admin user can update message review status."""
    mock_auth.return_value.auth.get_user.return_value = _mock_user(
        app_metadata={"role": "admin"}
    )
    mock_client = mock_db.return_value
    # Select for existence check
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": FAKE_MESSAGE_ID,
            "name": "Ali Khan",
            "email": "ali@example.com",
            "subject": "Support",
            "message": "Need help with portfolio.",
            "status": "new",
            "created_at": "2026-09-19T10:00:00Z",
        }
    ]
    # Update call
    mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": FAKE_MESSAGE_ID,
            "name": "Ali Khan",
            "email": "ali@example.com",
            "subject": "Support",
            "message": "Need help with portfolio.",
            "status": "read",
            "created_at": "2026-09-19T10:00:00Z",
        }
    ]

    resp = client.patch(
        f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"status": "read"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == FAKE_MESSAGE_ID
    assert data["status"] == "read"


@patch("app.core.auth.get_admin_client")
def test_admin_patch_invalid_status_rejected(mock_auth):
    """Invalid status values are rejected with 422."""
    mock_auth.return_value.auth.get_user.return_value = _mock_user(
        app_metadata={"role": "admin"}
    )

    resp = client.patch(
        f"/api/v1/contact/messages/{FAKE_MESSAGE_ID}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"status": "deleted"},
    )
    assert resp.status_code == 422


# ==============================================================================
# 5. STATUS VALIDATION MODEL TESTS
# ==============================================================================
def test_status_update_model_validation():
    """Verify ContactStatusUpdate accepts only allowed status values."""
    for s in ["new", "read", "replied", "archived"]:
        m = ContactStatusUpdate(status=s)
        assert m.status == s

    with pytest.raises(ValidationError):
        ContactStatusUpdate(status="deleted")

    with pytest.raises(ValidationError):
        ContactStatusUpdate(status="pending")
