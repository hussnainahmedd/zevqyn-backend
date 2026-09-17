"""Tests for project CRUD and AI generation."""

import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

import pytest

client = TestClient(app)

FAKE_TOKEN = "valid-token"
FAKE_USER = str(uuid.uuid4())
FAKE_WS = str(uuid.uuid4())
FAKE_DOC = str(uuid.uuid4())

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


@patch("app.services.projects.get_admin_client")
def test_create_project(mock_db):
    mock_client = mock_db.return_value
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": str(uuid.uuid4()),
        "user_id": FAKE_USER,
        "title": "Test Proj",
        "short_description": "short",
        "description": "long",
        "technologies": ["python"],
        "skills": [],
        "visibility": "private",
        "featured": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_res
    
    response = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={
            "title": "Test Proj",
            "short_description": "short",
            "description": "long",
            "visibility": "private"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Proj"


@patch("app.services.projects.get_admin_client")
def test_get_project_cross_user(mock_db):
    mock_client = mock_db.return_value
    
    mock_res = MagicMock()
    mock_res.data = [] # empty means not found or not owned
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.get(f"/api/v1/projects/{uuid.uuid4()}", headers={"Authorization": f"Bearer {FAKE_TOKEN}"})
    assert response.status_code == 404

@patch("app.services.projects.get_admin_client")
def test_update_project_cross_user_rejected(mock_db):
    mock_client = mock_db.return_value
    
    # Simulate get_project failing due to ownership
    mock_res = MagicMock()
    mock_res.data = []
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.patch(
        f"/api/v1/projects/{uuid.uuid4()}", 
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"title": "Hacked Title"}
    )
    assert response.status_code == 404
    mock_client.table().update.assert_not_called()

@patch("app.services.projects.get_admin_client")
def test_delete_project_cross_user_rejected(mock_db):
    mock_client = mock_db.return_value
    
    # Simulate get_project failing due to ownership
    mock_res = MagicMock()
    mock_res.data = []
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.delete(
        f"/api/v1/projects/{uuid.uuid4()}", 
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 404
    mock_client.table().delete.assert_not_called()

@patch("app.services.projects.get_admin_client")
def test_mass_assignment_prevention(mock_db):
    mock_client = mock_db.return_value
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": str(uuid.uuid4()),
        "user_id": FAKE_USER,
        "title": "Valid Title",
        "short_description": "short",
        "description": "long",
        "technologies": [],
        "skills": [],
        "visibility": "private",
        "featured": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_res
    
    # Attempt to override ownership and featured status
    malicious_payload = {
        "title": "Valid Title",
        "short_description": "short",
        "description": "long",
        "visibility": "private",
        "user_id": "malicious-uuid",
        "featured": True, # Should be ignored on creation or caught
        "admin_status": "superuser"
    }
    
    response = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=malicious_payload
    )
    
    # Pydantic will drop 'admin_status' and 'featured' since it's not in ProjectCreate
    # And the service explicitly overrides 'user_id' with the authenticated user
    # Let's verify what data was actually sent to DB
    assert response.status_code == 200
    
    called_data = mock_client.table().insert.call_args[0][0]
    assert called_data["user_id"] == FAKE_USER # Security boundary held
    assert "admin_status" not in called_data
    assert "featured" not in called_data


from app.models.rag import Citation

@patch("app.services.projects.get_admin_client")
@patch("app.services.projects._get_context_and_citations")
@patch("app.services.projects._get_genai_client")
@patch("app.services.workspaces.get_workspace")
def test_research_to_project(mock_ws, mock_ai, mock_ctx, mock_db):
    # Mock research context
    citation = Citation(
        source_id="[SOURCE_1]",
        document_id=uuid.uuid4(),
        document_name="doc.pdf",
        chunk_id=uuid.uuid4(),
        similarity=None
    )
    mock_ctx.return_value = ("Context text", {"[SOURCE_1]": citation}, "workspace")
    
    # Mock Gemini response
    mock_ai_res = MagicMock()
    mock_ai_res.text = '''{
        "title": "AI Proj",
        "short_description": "short",
        "description": "long",
        "problem_statement": "problem",
        "suggested_features": ["feat1"],
        "suggested_technologies": ["python"],
        "suggested_skills": ["dev"],
        "source_ids": ["[SOURCE_1]", "[SOURCE_99]"]
    }'''
    mock_ai.return_value.models.generate_content.return_value = mock_ai_res
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WS}/research/create-project",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"instructions": "Make it cool"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "AI Proj"
    assert len(data["citations"]) == 1 # SOURCE_99 discarded
    assert data["citations"][0]["source_id"] == "[SOURCE_1]"
    # DB was NOT called to insert! (persistence is explicit)
    mock_db.return_value.table().insert.assert_not_called()
