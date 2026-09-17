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

