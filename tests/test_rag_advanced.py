"""Tests for RAG citation validation and persistence errors."""

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
def test_citation_sanitization(mock_ws_db, mock_db, mock_gen, mock_search):
    # Mock workspace
    mock_ws_res = MagicMock()
    mock_ws_res.data = [{"id": FAKE_WORKSPACE_ID, "user_id": FAKE_USER_ID, "name": "Test", "description": "", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00"}]
    mock_ws_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_ws_res
    
    # Mock search retrieval (returns 2 chunks)
    mock_chunk1 = MagicMock()
    mock_chunk1.chunk_id = uuid.uuid4()
    mock_chunk1.document_id = uuid.UUID(FAKE_DOC_ID)
    mock_chunk1.content = "Test 1"
    mock_chunk1.page_number = 1
    mock_chunk1.source_label = "Page 1"
    mock_chunk1.similarity = 0.95
    
    mock_chunk2 = MagicMock()
    mock_chunk2.chunk_id = uuid.uuid4()
    mock_chunk2.document_id = uuid.UUID(FAKE_DOC_ID)
    mock_chunk2.content = "Test 2"
    mock_chunk2.page_number = 2
    mock_chunk2.source_label = "Page 2"
    mock_chunk2.similarity = 0.85
    
    mock_search.return_value = [mock_chunk1, mock_chunk2]
    
    # Mock conversation get
    mock_conv_res = MagicMock()
    mock_conv_res.data = [{"id": FAKE_CONV_ID}]
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_conv_res
    
    # Mock document name resolution
    mock_doc_res = MagicMock()
    mock_doc_res.data = [{"id": FAKE_DOC_ID, "original_filename": "test.pdf"}]
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value = mock_doc_res
    
    # Mock message insert
    mock_msg_res = MagicMock()
    mock_msg_res.data = [{"id": str(uuid.uuid4())}]
    mock_db.return_value.table.return_value.insert.return_value.execute.return_value = mock_msg_res
    
    # Mock Gemini answer with a valid source, an unused valid source, and a hallucinated source
    mock_gen.return_value = "Answer [SOURCE_1] and fake [SOURCE_99] and [SOURCE_9999]"
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/chat",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "What is the test?", "conversation_id": FAKE_CONV_ID}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify hallucinated sources were stripped
    assert "[SOURCE_99]" not in data["answer"]
    assert "fake  and" in data["answer"]
    
    # Verify valid sources were kept
    assert "[SOURCE_1]" in data["answer"]
    
    # Verify citations array only contains SOURCE_1, not SOURCE_2 or SOURCE_99
    citations = data["citations"]
    assert len(citations) == 1
    assert citations[0]["source_id"] == "SOURCE_1"


@patch("app.services.rag.get_admin_client")
@patch("app.services.workspaces.get_admin_client")
def test_user_persistence_failure(mock_ws_db, mock_db):
    mock_ws_res = MagicMock()
    mock_ws_res.data = [{"id": FAKE_WORKSPACE_ID, "user_id": FAKE_USER_ID, "name": "Test", "description": "", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00"}]
    mock_ws_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_ws_res
    
    # Mock conversation get
    mock_conv_res = MagicMock()
    mock_conv_res.data = [{"id": FAKE_CONV_ID}]
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_conv_res
    
    # Force insert failure
    mock_db.return_value.table.return_value.insert.return_value.execute.side_effect = Exception("DB Error")
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/chat",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "Hello", "conversation_id": FAKE_CONV_ID}
    )
    
    assert response.status_code == 500
    assert "Failed to persist user message" in response.json()["detail"]


@patch("app.services.rag.search_workspace")
@patch("app.services.rag.generate_rag_answer")
@patch("app.services.rag.get_admin_client")
@patch("app.services.workspaces.get_admin_client")
def test_assistant_persistence_failure(mock_ws_db, mock_db, mock_gen, mock_search):
    mock_ws_res = MagicMock()
    mock_ws_res.data = [{"id": FAKE_WORKSPACE_ID, "user_id": FAKE_USER_ID, "name": "Test", "description": "", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00"}]
    mock_ws_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_ws_res
    
    mock_conv_res = MagicMock()
    mock_conv_res.data = [{"id": FAKE_CONV_ID}]
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_conv_res
    
    mock_chunk1 = MagicMock()
    mock_chunk1.chunk_id = uuid.uuid4()
    mock_chunk1.document_id = uuid.UUID(FAKE_DOC_ID)
    mock_chunk1.similarity = 0.95
    mock_chunk1.page_number = None
    mock_chunk1.source_label = None
    mock_chunk1.model_dump.return_value = {"mock": "dump"}
    mock_search.return_value = [mock_chunk1]
    
    # First insert (user) succeeds, second (assistant) fails
    mock_user_insert = MagicMock()
    mock_user_insert.data = [{"id": str(uuid.uuid4())}]
    
    def side_effect(*args, **kwargs):
        # We check the role being inserted
        role = args[0].get("role")
        if role == "user":
            mock_res = MagicMock()
            mock_res.execute.return_value = mock_user_insert
            return mock_res
        else:
            mock_res = MagicMock()
            mock_res.execute.side_effect = Exception("DB Error")
            return mock_res
            
    mock_db.return_value.table.return_value.insert.side_effect = side_effect
    
    mock_gen.return_value = "Answer [SOURCE_1]"
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/chat",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "Hello", "conversation_id": FAKE_CONV_ID}
    )
    
    assert response.status_code == 500
    assert "Failed to persist assistant message" in response.json()["detail"]


@patch("app.api.workspaces.workspace_service.get_workspace")
def test_empty_message_rejection(mock_get_ws):
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/chat",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "   "}
    )
    assert response.status_code == 400 # Manual strip check

@patch("app.api.workspaces.workspace_service.get_workspace")
def test_oversized_message_rejection(mock_get_ws):
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/chat",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"message": "A" * 3000}
    )
    assert response.status_code == 422 # Pydantic max_length=2000
