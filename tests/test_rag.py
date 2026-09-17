"""Unit tests for RAG chat endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FAKE_USER_ID = str(uuid.uuid4())
FAKE_WORKSPACE_ID = str(uuid.uuid4())
FAKE_DOC_ID = str(uuid.uuid4())
FAKE_TOKEN = "valid-token"
FAKE_CONV_ID = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def setup_auth(monkeypatch):
    """Automatically mock auth for all tests here unless overridden."""
    with patch("app.core.auth.get_admin_client") as mock_get:
        user = MagicMock()
        user.id = FAKE_USER_ID
        user.email = "test@example.com"
        response = MagicMock()
        response.user = user
        mock_get.return_value.auth.get_user.return_value = response
        yield mock_get


@patch("app.services.rag.search_workspace")
@patch("app.services.rag.generate_rag_answer")
@patch("app.services.rag.get_admin_client")
@patch("app.services.workspaces.get_admin_client")
def test_chat_new_conversation(mock_ws_db, mock_db, mock_gen, mock_search):
    # Mock workspace existence
    mock_ws_res = MagicMock()
    mock_ws_res.data = [{
        "id": FAKE_WORKSPACE_ID,
        "user_id": FAKE_USER_ID,
        "name": "Test",
        "description": "",
        "created_at": "2023-01-01T00:00:00",
        "updated_at": "2023-01-01T00:00:00"
    }]
    mock_ws_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_ws_res
    
    # Mock search retrieval
    mock_chunk = MagicMock()
    mock_chunk.chunk_id = uuid.uuid4()
    mock_chunk.document_id = uuid.UUID(FAKE_DOC_ID)
    mock_chunk.content = "Test chunk content."
    mock_chunk.page_number = 1
    mock_chunk.source_label = "Page 1"
    mock_chunk.similarity = 0.95
    mock_chunk.model_dump.return_value = {"mock": "dump"}
    mock_search.return_value = [mock_chunk]
    
    # Mock conversation creation
    mock_conv_res = MagicMock()
    mock_conv_res.data = [{"id": FAKE_CONV_ID}]
    mock_db.return_value.table.return_value.insert.return_value.execute.return_value = mock_conv_res
    
    # Mock document name resolution
    mock_doc_res = MagicMock()
    mock_doc_res.data = [{"id": FAKE_DOC_ID, "original_filename": "test.pdf"}]
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value = mock_doc_res
    
    # Mock Gemini answer
    mock_gen.return_value = "This is a grounded answer [SOURCE_1]."
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/chat",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "What is the test chunk?"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "This is a grounded answer [SOURCE_1]."
    assert data["retrieved_chunks"] == 1
    assert data["conversation_id"] == FAKE_CONV_ID
    
    citations = data["citations"]
    assert len(citations) == 1
    assert citations[0]["document_name"] == "test.pdf"
    assert citations[0]["page_number"] == 1
    
    # Ensure it saved user message and assistant message
    assert mock_db.return_value.table.return_value.insert.call_count >= 2





@patch("app.services.rag.search_workspace")
@patch("app.services.rag.get_admin_client")
@patch("app.services.workspaces.get_admin_client")
def test_chat_no_context_handled_cleanly(mock_ws_db, mock_db, mock_search):
    mock_ws_res = MagicMock()
    mock_ws_res.data = [{
        "id": FAKE_WORKSPACE_ID,
        "user_id": FAKE_USER_ID,
        "name": "Test",
        "description": "",
        "created_at": "2023-01-01T00:00:00",
        "updated_at": "2023-01-01T00:00:00"
    }]
    mock_ws_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_ws_res
    
    # Mock conversation get
    mock_conv_res = MagicMock()
    mock_conv_res.data = [{"id": FAKE_CONV_ID}]
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_conv_res
    
    # Mock message insert
    mock_msg_res = MagicMock()
    mock_msg_res.data = [{"id": FAKE_DOC_ID}]
    mock_db.return_value.table.return_value.insert.return_value.execute.return_value = mock_msg_res
    
    # Empty retrieval
    mock_search.return_value = []
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/chat",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "What is the test chunk?", "conversation_id": FAKE_CONV_ID}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "couldn't find enough relevant information" in data["answer"]
    assert len(data["citations"]) == 0

@patch("app.api.workspaces.get_admin_client")
@patch("app.services.workspaces.get_admin_client")
def test_list_conversations(mock_ws_db, mock_db):
    mock_ws_res = MagicMock()
    mock_ws_res.data = [{"id": FAKE_WORKSPACE_ID, "user_id": FAKE_USER_ID, "name": "Test", "description": "", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00"}]
    mock_ws_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_ws_res
    
    mock_conv_res = MagicMock()
    mock_conv_res.data = [{"id": FAKE_CONV_ID, "user_id": FAKE_USER_ID, "workspace_id": FAKE_WORKSPACE_ID, "title": "Test", "created_at": "2023", "updated_at": "2023"}]
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_conv_res
    
    response = client.get(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/conversations",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == FAKE_CONV_ID
