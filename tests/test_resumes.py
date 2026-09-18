"""Tests for resumes and PDF export."""

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


@patch("app.services.resumes.get_admin_client")
def test_create_resume(mock_db):
    mock_client = mock_db.return_value
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": str(uuid.uuid4()),
        "user_id": FAKE_USER,
        "name": "My Resume",
        "template": "professional",
        "professional_summary": "I am a dev.",
        "visibility": "private",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_res
    
    malicious_payload = {
        "name": "My Resume",
        "template": "professional",
        "user_id": "other-user",
        "hacked_field": True
    }
    
    # Extra forbid should block hacked_field
    response = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=malicious_payload
    )
    assert response.status_code == 422
    
    # Valid payload
    response = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "My Resume", "template": "professional"}
    )
    assert response.status_code == 200
    called_data = mock_client.table().insert.call_args[0][0]
    assert called_data["user_id"] == FAKE_USER


@patch("app.services.resumes.get_admin_client")
def test_get_resume_cross_user_rejected(mock_db):
    mock_client = mock_db.return_value
    
    mock_res = MagicMock()
    mock_res.data = [] # Not found or not owned
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.get(f"/api/v1/resumes/{uuid.uuid4()}", headers={"Authorization": f"Bearer {FAKE_TOKEN}"})
    assert response.status_code == 404


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_project")
@patch("app.services.resumes.get_resume")
def test_create_resume_item(mock_get_resume, mock_get_project, mock_db):
    mock_client = mock_db.return_value
    
    # Mock project fetch
    mock_proj = MagicMock()
    mock_proj.title = "Zevqyn"
    mock_proj.technologies = ["Python"]
    mock_proj.short_description = "Cool app"
    mock_get_project.return_value = mock_proj
    
    # Mock no existing item
    mock_res_select = MagicMock()
    mock_res_select.data = []
    mock_client.table().select().eq().eq().execute.return_value = mock_res_select
    
    # Mock insert
    mock_res_insert = MagicMock()
    mock_res_insert.data = [{
        "id": str(uuid.uuid4()),
        "resume_id": str(uuid.uuid4()),
        "section_type": "project",
        "title": "Zevqyn",
        "subtitle": "Python",
        "description": "Cool app",
        "metadata": {"source_id": str(uuid.uuid4()), "source_type": "project"},
        "sort_order": 0,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_res_insert
    
    response = client.post(
        f"/api/v1/resumes/{uuid.uuid4()}/items",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"section_type": "project", "source_id": str(uuid.uuid4())}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Zevqyn"


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf(mock_get_resume, mock_get_items, mock_db):
    class FakeResume:
        id = uuid.uuid4()
        name = "Test Resume"
        professional_summary = "Summary"
    mock_get_resume.return_value = FakeResume()
    mock_get_items.return_value = []
    
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{"full_name": "John Doe"}]
    mock_client.table().select().eq().execute.return_value = mock_res
    
    response = client.get(
        f"/api/v1/resumes/{uuid.uuid4()}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_unicode_safety(mock_get_resume, mock_get_items, mock_db):
    class FakeResume:
        id = uuid.uuid4()
        name = "Unicode"
        professional_summary = "Emoji 🚀 and CJK 测试"
        
    class FakeItem:
        section_type = "project"
        title = "Project 🚀"
        subtitle = "Subtitle"
        description = "Desc"
        
    mock_get_resume.return_value = FakeResume()
    mock_get_items.return_value = [FakeItem()]
    
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{"full_name": "Test User"}]
    mock_client.table().select().eq().execute.return_value = mock_res
    
    response = client.get(
        f"/api/v1/resumes/{uuid.uuid4()}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    # Should not crash, un-encodeable chars replaced with ?
    assert response.content.startswith(b"%PDF")

@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume")
def test_resume_item_unknown_source_rejected(mock_get_resume, mock_db):
    response = client.post(
        f"/api/v1/resumes/{uuid.uuid4()}/items",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"section_type": "invalid_type", "source_id": str(uuid.uuid4())}
    )
    # Pydantic Regex rejection
    assert response.status_code == 422


@patch("app.services.resumes.get_admin_client")
def test_create_resume_with_personal_info(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    payload = {
        "name": "Software Engineer Resume",
        "template": "modern",
        "professional_summary": "Full-stack developer with 3 years experience.",
        "visibility": "public",
        "full_name": "Hussnain Ahmad",
        "professional_title": "Computer Science Student",
        "email": "hussnain@example.com",
        "phone": "+92 300 1234567",
        "location": "Islamabad, Pakistan",
        "linkedin_url": "https://linkedin.com/in/hussnain",
        "github_url": "https://github.com/hussnain",
        "portfolio_url": "https://hussnain.dev"
    }
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        **payload
    }]
    mock_client.table().insert().execute.return_value = mock_res
    
    response = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == resume_id
    assert data["name"] == "Software Engineer Resume"
    assert data["full_name"] == "Hussnain Ahmad"
    assert data["professional_title"] == "Computer Science Student"
    assert data["email"] == "hussnain@example.com"
    assert data["phone"] == "+92 300 1234567"
    assert data["location"] == "Islamabad, Pakistan"
    assert data["linkedin_url"] == "https://linkedin.com/in/hussnain"
    assert data["github_url"] == "https://github.com/hussnain"
    assert data["portfolio_url"] == "https://hussnain.dev"
    
    called_insert = mock_client.table().insert.call_args[0][0]
    assert called_insert["full_name"] == "Hussnain Ahmad"
    assert called_insert["professional_title"] == "Computer Science Student"
    assert called_insert["email"] == "hussnain@example.com"
    assert called_insert["phone"] == "+92 300 1234567"
    assert called_insert["location"] == "Islamabad, Pakistan"
    assert called_insert["linkedin_url"] == "https://linkedin.com/in/hussnain"
    assert called_insert["github_url"] == "https://github.com/hussnain"
    assert called_insert["portfolio_url"] == "https://hussnain.dev"


@patch("app.services.resumes.get_admin_client")
def test_create_resume_validation_limits(mock_db):
    # Test full_name max length (150)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "full_name": "A" * 151}
    )
    assert res.status_code == 422

    # Test email max length (254)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "email": "a" * 255}
    )
    assert res.status_code == 422

    # Test phone max length (50)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "phone": "1" * 51}
    )
    assert res.status_code == 422

    # Test location max length (150)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "location": "L" * 151}
    )
    assert res.status_code == 422

    # Test linkedin_url max length (500)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "linkedin_url": "https://linkedin.com/" + ("u" * 500)}
    )
    assert res.status_code == 422

    # Test extra field forbidden
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "unknown_field": "disallowed"}
    )
    assert res.status_code == 422


@patch("app.services.resumes.get_admin_client")
def test_get_resume_with_personal_info(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Tech Resume",
        "template": "professional",
        "professional_summary": "Summary text",
        "visibility": "private",
        "full_name": "Hussnain Ahmad",
        "professional_title": "Software Engineer",
        "email": "hussnain@test.com",
        "phone": "+923001234567",
        "location": "Lahore, Pakistan",
        "linkedin_url": "https://linkedin.com/in/test",
        "github_url": "https://github.com/test",
        "portfolio_url": "https://test.me",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.get(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Hussnain Ahmad"
    assert data["professional_title"] == "Software Engineer"
    assert data["email"] == "hussnain@test.com"
    assert data["phone"] == "+923001234567"
    assert data["location"] == "Lahore, Pakistan"
    assert data["linkedin_url"] == "https://linkedin.com/in/test"
    assert data["github_url"] == "https://github.com/test"
    assert data["portfolio_url"] == "https://test.me"


@patch("app.services.resumes.get_admin_client")
def test_get_resume_legacy_null_personal_info(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    # Legacy resume has no personal info fields (or null in DB)
    mock_res = MagicMock()
    mock_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Legacy Resume",
        "template": "professional",
        "professional_summary": None,
        "visibility": "private",
        "full_name": None,
        "professional_title": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin_url": None,
        "github_url": None,
        "portfolio_url": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.get(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Legacy Resume"
    assert data["full_name"] is None
    assert data["professional_title"] is None
    assert data["email"] is None
    assert data["phone"] is None
    assert data["location"] is None
    assert data["linkedin_url"] is None
    assert data["github_url"] is None
    assert data["portfolio_url"] is None


@patch("app.services.resumes.get_admin_client")
def test_update_resume_all_personal_info(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    # Mock existing resume lookup in get_resume()
    mock_get_res = MagicMock()
    mock_get_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Old Name",
        "template": "professional",
        "professional_summary": None,
        "visibility": "private",
        "full_name": None,
        "professional_title": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin_url": None,
        "github_url": None,
        "portfolio_url": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().select().eq().eq().execute.return_value = mock_get_res
    
    update_payload = {
        "full_name": "Hussnain Ahmad",
        "professional_title": "Full Stack Engineer",
        "email": "hussnain@example.com",
        "phone": "+92 300 0000000",
        "location": "Islamabad, Pakistan",
        "linkedin_url": "https://linkedin.com/in/hussnain",
        "github_url": "https://github.com/hussnain",
        "portfolio_url": "https://hussnain.me"
    }
    
    mock_update_res = MagicMock()
    mock_update_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Old Name",
        "template": "professional",
        "professional_summary": None,
        "visibility": "private",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        **update_payload
    }]
    mock_client.table().update().eq().eq().execute.return_value = mock_update_res
    
    response = client.patch(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=update_payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Hussnain Ahmad"
    assert data["professional_title"] == "Full Stack Engineer"
    assert data["email"] == "hussnain@example.com"
    assert data["phone"] == "+92 300 0000000"
    assert data["location"] == "Islamabad, Pakistan"
    assert data["linkedin_url"] == "https://linkedin.com/in/hussnain"
    assert data["github_url"] == "https://github.com/hussnain"
    assert data["portfolio_url"] == "https://hussnain.me"
    
    called_update = mock_client.table().update.call_args[0][0]
    for key, val in update_payload.items():
        assert called_update[key] == val


@patch("app.services.resumes.get_admin_client")
def test_update_resume_partial_preserves_unspecified(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    mock_get_res = MagicMock()
    mock_get_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Backend Resume",
        "template": "professional",
        "professional_summary": "Original summary",
        "visibility": "private",
        "full_name": "Original Name",
        "professional_title": "Original Title",
        "email": "orig@example.com",
        "phone": "+1234567890",
        "location": "City",
        "linkedin_url": "https://linkedin.com/orig",
        "github_url": "https://github.com/orig",
        "portfolio_url": "https://orig.com",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().select().eq().eq().execute.return_value = mock_get_res
    
    mock_update_res = MagicMock()
    mock_update_res.data = [{
        **mock_get_res.data[0],
        "full_name": "Updated Name Only",
        "updated_at": "2024-01-02T00:00:00Z"
    }]
    mock_client.table().update().eq().eq().execute.return_value = mock_update_res
    
    # Patch ONLY full_name
    response = client.patch(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"full_name": "Updated Name Only"}
    )
    assert response.status_code == 200
    
    # CRITICAL: ensure ONLY full_name was sent to update, not unspecified fields as None
    called_update = mock_client.table().update.call_args[0][0]
    assert called_update == {"full_name": "Updated Name Only"}
    assert "email" not in called_update
    assert "phone" not in called_update
    assert "name" not in called_update
    assert "template" not in called_update


