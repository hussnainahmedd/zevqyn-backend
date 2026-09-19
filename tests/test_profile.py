"""Tests for authenticated user Profile API."""

import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FAKE_USER = str(uuid.uuid4())
FAKE_TOKEN = "valid-token"

import pytest


@pytest.fixture(autouse=True)
def setup_auth():
    with patch("app.core.auth.get_admin_client") as mock_get:
        user = MagicMock()
        user.id = FAKE_USER
        user.email = "test@example.com"
        response = MagicMock()
        response.user = user
        mock_get.return_value.auth.get_user.return_value = response
        yield mock_get


# 1. GET profile requires authentication
def test_get_profile_requires_auth():
    # Calling without Authorization header should fail
    response = client.get("/api/v1/profile")
    assert response.status_code in (401, 403)


# 2. PATCH profile requires authentication
def test_patch_profile_requires_auth():
    response = client.patch(
        "/api/v1/profile",
        json={"full_name": "Unauthenticated User"}
    )
    assert response.status_code in (401, 403)


# 3. User can retrieve own profile
@patch("app.services.profile.get_admin_client")
def test_user_can_retrieve_own_profile(mock_db):
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{
        "id": FAKE_USER,
        "username": "hussnain",
        "full_name": "Hussnain Ahmad",
        "bio": "Senior Backend Engineer",
        "avatar_url": "https://example.com/avatar.png",
        "location": "Islamabad, Pakistan",
        "website": "https://hussnain.dev",
        "github_url": "https://github.com/hussnainahmedd",
        "linkedin_url": "https://linkedin.com/in/hussnain",
        "phone": "+923001234567",
        "created_at": "2026-09-18T08:10:06.957014Z",
        "updated_at": "2026-09-18T08:10:06.957014Z"
    }]
    mock_client.table().select().eq().execute.return_value = mock_res

    response = client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == FAKE_USER
    assert data["username"] == "hussnain"
    assert data["full_name"] == "Hussnain Ahmad"
    assert data["location"] == "Islamabad, Pakistan"
    assert data["website"] == "https://hussnain.dev"
    assert data["github_url"] == "https://github.com/hussnainahmedd"
    assert data["linkedin_url"] == "https://linkedin.com/in/hussnain"
    assert data["phone"] == "+923001234567"


# 4. User can update own profile
@patch("app.services.profile.get_admin_client")
def test_user_can_update_own_profile(mock_db):
    mock_client = mock_db.return_value

    # Existing profile check
    mock_select = MagicMock()
    mock_select.data = [{"id": FAKE_USER, "full_name": "Old Name"}]
    mock_client.table().select().eq().execute.return_value = mock_select

    # Update return
    mock_update = MagicMock()
    mock_update.data = [{
        "id": FAKE_USER,
        "username": "new_username",
        "full_name": "New Full Name",
        "bio": "Updated bio text",
        "avatar_url": "https://example.com/new.png",
        "location": "Lahore, Pakistan",
        "website": "https://new.dev",
        "github_url": "https://github.com/new",
        "linkedin_url": "https://linkedin.com/in/new",
        "phone": "+923111111111",
        "created_at": "2026-09-18T08:10:06.957014Z",
        "updated_at": "2026-09-19T10:00:00.000000Z"
    }]
    mock_client.table().update().eq().execute.return_value = mock_update

    response = client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={
            "username": "new_username",
            "full_name": "New Full Name",
            "bio": "Updated bio text",
            "location": "Lahore, Pakistan"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == FAKE_USER
    assert data["username"] == "new_username"
    assert data["full_name"] == "New Full Name"
    assert data["location"] == "Lahore, Pakistan"


# 5. Partial PATCH preserves fields not supplied
@patch("app.services.profile.get_admin_client")
def test_partial_patch_preserves_unsupplied_fields(mock_db):
    mock_client = mock_db.return_value

    # Existing profile check
    mock_select = MagicMock()
    mock_select.data = [{
        "id": FAKE_USER,
        "full_name": "Preserved Name",
        "bio": "Preserved Bio",
        "location": "Old Location"
    }]
    mock_client.table().select().eq().execute.return_value = mock_select

    mock_update = MagicMock()
    mock_update.data = [{
        "id": FAKE_USER,
        "full_name": "Preserved Name",
        "bio": "Preserved Bio",
        "location": "New Location"
    }]
    mock_client.table().update().eq().execute.return_value = mock_update

    response = client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"location": "New Location"}
    )
    assert response.status_code == 200

    # Verify that the update call only received 'location' and 'updated_at'
    assert mock_client.table().update.called
    passed_args = mock_client.table().update.call_args.args[0]
    assert "location" in passed_args
    assert passed_args["location"] == "New Location"
    assert "full_name" not in passed_args
    assert "bio" not in passed_args


# 6. User cannot modify profile ID
def test_user_cannot_modify_profile_id():
    response = client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={
            "id": str(uuid.uuid4()),
            "full_name": "Attacker"
        }
    )
    # Extra field forbidden -> 422
    assert response.status_code == 422
    assert "extra" in response.text.lower() or "id" in response.text.lower()


# 7. Missing profile is handled safely (auto-creation)
@patch("app.services.profile.get_admin_client")
def test_missing_profile_auto_created_on_get(mock_db):
    mock_client = mock_db.return_value

    # 1st select: profile does not exist
    mock_select_empty = MagicMock()
    mock_select_empty.data = []

    # Insert minimal profile
    mock_insert = MagicMock()
    mock_insert.data = [{
        "id": FAKE_USER,
        "username": None,
        "full_name": "Auth Prepopulated Name",
        "bio": None,
        "location": None,
        "created_at": "2026-09-19T10:00:00Z",
        "updated_at": "2026-09-19T10:00:00Z"
    }]

    mock_client.table().select().eq().execute.return_value = mock_select_empty
    mock_client.table().insert().execute.return_value = mock_insert

    # Mock admin auth get_user_by_id
    auth_user_mock = MagicMock()
    auth_user_mock.user.user_metadata = {"full_name": "Auth Prepopulated Name"}
    mock_client.auth.admin.get_user_by_id.return_value = auth_user_mock

    response = client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == FAKE_USER
    assert data["full_name"] == "Auth Prepopulated Name"


@patch("app.services.profile.get_admin_client")
def test_missing_profile_auto_created_on_patch(mock_db):
    mock_client = mock_db.return_value

    # 1st select: empty
    mock_select_empty = MagicMock()
    mock_select_empty.data = []

    mock_insert = MagicMock()
    mock_insert.data = [{"id": FAKE_USER}]

    mock_update = MagicMock()
    mock_update.data = [{
        "id": FAKE_USER,
        "full_name": "First Time Created Name",
        "location": "New York"
    }]

    mock_client.table().select().eq().execute.return_value = mock_select_empty
    mock_client.table().insert().execute.return_value = mock_insert
    mock_client.table().update().eq().execute.return_value = mock_update

    response = client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"full_name": "First Time Created Name", "location": "New York"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == FAKE_USER
    assert data["full_name"] == "First Time Created Name"


# 8. Invalid data is rejected appropriately
def test_invalid_data_rejected_appropriately():
    # Case A: Invalid URL format
    res_url = client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"website": "ftp://invalid-protocol.com"}
    )
    assert res_url.status_code == 422
    assert "URL must start with http" in res_url.text

    # Case B: Excessive length
    res_len = client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"full_name": "A" * 200}
    )
    assert res_len.status_code == 422

    # Case C: Invalid username pattern
    res_user = client.patch(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"username": "invalid user with spaces!"}
    )
    assert res_user.status_code == 422
