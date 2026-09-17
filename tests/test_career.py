"""Tests for career profile and AI assistant."""

import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

import pytest

client = TestClient(app)

FAKE_USER = str(uuid.uuid4())
FAKE_TOKEN = "valid-token"

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

@patch("app.services.career.get_admin_client")
def test_create_skill(mock_db):
    mock_client = mock_db.return_value
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": str(uuid.uuid4()),
        "user_id": FAKE_USER,
        "name": "Python",
        "category": "Language",
        "proficiency": 4,
        "created_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_res
    
    # Try mass assignment injection
    malicious_payload = {
        "name": "Python",
        "category": "Language",
        "proficiency": 4,
        "user_id": "other-user",
        "admin": True
    }
    
    response = client.post(
        "/api/v1/career/skills",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=malicious_payload
    )
    
    assert response.status_code == 200
    called_data = mock_client.table().insert.call_args[0][0]
    assert called_data["user_id"] == FAKE_USER
    assert "admin" not in called_data

@patch("app.services.career.get_admin_client")
def test_update_skill_cross_user_rejected(mock_db):
    mock_client = mock_db.return_value
    
    # Simulate get_skill failing due to ownership
    mock_res = MagicMock()
    mock_res.data = []
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.patch(
        f"/api/v1/career/skills/{uuid.uuid4()}", 
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Hacked Skill"}
    )
    assert response.status_code == 404
    mock_client.table().update.assert_not_called()

@patch("app.services.career.get_projects")
@patch("app.services.career.get_skills")
@patch("app.services.career.get_educations")
@patch("app.services.career.get_certificates")
def test_profile_truncation_limits(mock_certs, mock_edu, mock_skills, mock_projs):
    from app.services.career import get_career_profile
    import uuid
    from app.models.project import ProjectResponse
    from datetime import datetime
    
    # Create 35 projects to test max 30 limit, and one with a massive description
    long_desc = "A" * 2000
    projects = []
    for i in range(35):
        projects.append(ProjectResponse(
            id=uuid.uuid4(),
            user_id=uuid.UUID(FAKE_USER),
            title=f"Proj {i}",
            short_description="short",
            description=long_desc if i == 0 else "desc",
            technologies=[],
            skills=[],
            visibility="private",
            featured=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ))
        
    mock_projs.return_value = projects
    mock_skills.return_value = []
    mock_edu.return_value = []
    mock_certs.return_value = []
    
    profile = get_career_profile(uuid.UUID(FAKE_USER))
    
    # Assert limited to 30
    assert len(profile["projects"]) == 30
    # Assert string truncation
    assert len(profile["projects"][0]["description"]) <= 1050 # 1000 + len("... [TRUNCATED]")
    assert profile["projects"][0]["description"].endswith("[TRUNCATED]")


@patch("app.services.career.get_projects")
@patch("app.services.career.get_skills")
@patch("app.services.career.get_educations")
@patch("app.services.career.get_certificates")
@patch("app.services.career._get_genai_client")
def test_career_assistant_empty_profile(mock_ai, mock_certs, mock_edu, mock_skills, mock_projs):
    mock_projs.return_value = []
    mock_skills.return_value = []
    mock_edu.return_value = []
    mock_certs.return_value = []
    
    response = client.post(
        "/api/v1/career/assistant",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "What should I do next?"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "Your ZEVQYN career profile doesn't contain enough information yet" in data["answer"]
    assert data["profile_used"]["projects"] == 0
    # Ensure AI was not called
    mock_ai.assert_not_called()


@patch("app.services.career.get_projects")
@patch("app.services.career.get_skills")
@patch("app.services.career.get_educations")
@patch("app.services.career.get_certificates")
@patch("app.services.career._get_genai_client")
def test_career_assistant_with_profile(mock_ai, mock_certs, mock_edu, mock_skills, mock_projs):
    mock_projs.return_value = []
    mock_skills.return_value = [MagicMock(model_dump_json=lambda **kw: '{"name": "Python"}')]
    mock_edu.return_value = []
    mock_certs.return_value = []
    
    mock_ai_res = MagicMock()
    mock_ai_res.text = '{"answer": "Based on your Python skill..."}'
    mock_ai.return_value.models.generate_content.return_value = mock_ai_res
    
    response = client.post(
        "/api/v1/career/assistant",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "What should I do next?"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Based on your Python skill..."
    assert data["profile_used"]["skills"] == 1
