"""Tests for Phase 7 Research AI capabilities."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FAKE_USER_ID = str(uuid.uuid4())
FAKE_WORKSPACE_ID = str(uuid.uuid4())
FAKE_DOC_ID = str(uuid.uuid4())
FAKE_TOKEN = "valid-token"

@pytest.fixture(autouse=True)
def setup_auth(monkeypatch):
    with patch("app.core.auth.get_admin_client") as mock_get:
        user = MagicMock()
        user.id = FAKE_USER_ID
        user.email = "test@example.com"
        response = MagicMock()
        response.user = user
        mock_get.return_value.auth.get_user.return_value = response
        yield mock_get


def _make_mock_chunk():
    chunk = MagicMock()
    chunk.chunk_id = uuid.uuid4()
    chunk.document_id = uuid.UUID(FAKE_DOC_ID)
    chunk.content = "Test content"
    chunk.page_number = 1
    chunk.source_label = "Page 1"
    chunk.similarity = 1.0
    return chunk


@patch("app.api.research.workspace_service.get_workspace")
@patch("app.services.research_ai.get_representative_chunks")
@patch("app.services.research_ai.resolve_document_names")
@patch("app.services.research_ai._get_genai_client")
def test_generate_summary_success(mock_ai, mock_resolve, mock_chunks, mock_ws):
    # Setup mocks
    mock_chunks.return_value = [_make_mock_chunk()]
    mock_resolve.return_value = {uuid.UUID(FAKE_DOC_ID): "test.pdf"}
    
    mock_response = MagicMock()
    mock_response.text = "Here is a summary based on [SOURCE_1]."
    mock_ai.return_value.models.generate_content.return_value = mock_response
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/research/summary",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"document_id": FAKE_DOC_ID}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert data["scope"] == "document"
    assert data["summary"] == "Here is a summary based on [SOURCE_1]."


@patch("app.api.research.workspace_service.get_workspace")
@patch("app.services.research_ai.get_representative_chunks")
@patch("app.services.research_ai.resolve_document_names")
@patch("app.services.research_ai._get_genai_client")
def test_generate_key_points(mock_ai, mock_resolve, mock_chunks, mock_ws):
    mock_chunks.return_value = [_make_mock_chunk()]
    mock_resolve.return_value = {uuid.UUID(FAKE_DOC_ID): "test.pdf"}
    
    mock_response = MagicMock()
    mock_response.text = '{"key_points": [{"text": "Point 1", "source_ids": ["[SOURCE_1]"]}]}'
    mock_ai.return_value.models.generate_content.return_value = mock_response
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/research/key-points",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["key_points"]) == 1
    assert data["key_points"][0]["text"] == "Point 1"
    assert data["scope"] == "workspace"


@patch("app.api.research.workspace_service.get_workspace")
@patch("app.services.research_ai.get_representative_chunks")
@patch("app.services.research_ai.resolve_document_names")
@patch("app.services.research_ai._get_genai_client")
def test_generate_questions(mock_ai, mock_resolve, mock_chunks, mock_ws):
    mock_chunks.return_value = [_make_mock_chunk()]
    mock_resolve.return_value = {uuid.UUID(FAKE_DOC_ID): "test.pdf"}
    
    mock_response = MagicMock()
    mock_response.text = '{"questions": [{"question": "Q1?", "answer": "A1.", "difficulty": "hard", "source_ids": ["[SOURCE_1]"]}]}'
    mock_ai.return_value.models.generate_content.return_value = mock_response
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/research/questions",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"count": 5}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["questions"]) == 1
    assert data["questions"][0]["question"] == "Q1?"


@patch("app.api.research.workspace_service.get_workspace")
@patch("app.services.research_ai.get_representative_chunks")
@patch("app.services.research_ai.resolve_document_names")
@patch("app.services.research_ai._get_genai_client")
def test_generate_flashcards(mock_ai, mock_resolve, mock_chunks, mock_ws):
    mock_chunks.return_value = [_make_mock_chunk()]
    mock_resolve.return_value = {uuid.UUID(FAKE_DOC_ID): "test.pdf"}
    
    mock_response = MagicMock()
    mock_response.text = '{"flashcards": [{"front": "Front 1", "back": "Back 1", "source_ids": ["[SOURCE_1]"]}]}'
    mock_ai.return_value.models.generate_content.return_value = mock_response
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/research/flashcards",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"count": 10}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["flashcards"]) == 1
    assert data["flashcards"][0]["front"] == "Front 1"


@patch("app.api.research.workspace_service.get_workspace")
@patch("app.services.research_ai.get_representative_chunks")
def test_no_content_aborts_early(mock_chunks, mock_ws):
    mock_chunks.return_value = []
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/research/summary",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={}
    )
    
    assert response.status_code == 400
    assert "No indexed research content" in response.json()["detail"]


@patch("app.api.research.workspace_service.get_workspace")
@patch("app.services.research_ai.get_representative_chunks")
@patch("app.services.research_ai.resolve_document_names")
@patch("app.services.research_ai._get_genai_client")
def test_ai_provider_failure(mock_ai, mock_resolve, mock_chunks, mock_ws):
    mock_chunks.return_value = [_make_mock_chunk()]
    mock_resolve.return_value = {uuid.UUID(FAKE_DOC_ID): "test.pdf"}
    
    mock_ai.return_value.models.generate_content.side_effect = Exception("API down")
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/research/summary",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={}
    )
    
    assert response.status_code == 502
    assert "Failed to generate summary with AI provider" in response.json()["detail"]


def test_invalid_count_validation():
    # Should reject count > 20 for questions
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/research/questions",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"count": 50}
    )
    assert response.status_code == 422
