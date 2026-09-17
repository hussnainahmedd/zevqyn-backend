"""Unit tests for indexing and retrieval API endpoints."""

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


@patch("app.services.indexing.process_document")
@patch("app.services.indexing.chunk_document")
@patch("app.services.indexing.embed_document")
@patch("app.services.indexing.get_admin_client")
def test_index_endpoint_success(mock_db, mock_embed, mock_chunk, mock_process):
    # Setup extraction
    mock_ext_doc = MagicMock()
    mock_process.return_value = mock_ext_doc
    
    # Setup chunking
    mock_chunk1 = MagicMock()
    mock_chunk1.chunk_index = 0
    mock_chunk1.content = "Text"
    mock_chunk1.page_number = 1
    mock_chunk1.source_label = "Page 1"
    mock_chunk1.metadata = {}
    mock_chunk.return_value = [mock_chunk1]
    
    # Setup embedding
    mock_embed.return_value = [[0.1] * 768]
    
    # Setup DB insert
    mock_db_res = MagicMock()
    mock_db_res.data = [{"id": "some-id"}]
    mock_db.return_value.table.return_value.insert.return_value.execute.return_value = mock_db_res
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/documents/{FAKE_DOC_ID}/index",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["chunk_count"] == 1
    assert data["embedding_dimension"] == 768
    
    # Verify idempotent deletion was called
    mock_db.return_value.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.assert_called()


@patch("app.services.retrieval.embed_query")
@patch("app.services.retrieval.get_admin_client")
@patch("app.services.workspaces.get_admin_client")
def test_search_endpoint_success(mock_ws_db, mock_db, mock_embed_q):
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
    
    # Mock embedding
    mock_embed_q.return_value = [0.1] * 768
    
    # Mock RPC result
    mock_rpc_res = MagicMock()
    mock_rpc_res.data = [
        {
            "id": FAKE_DOC_ID,
            "document_id": FAKE_DOC_ID,
            "content": "Match 1",
            "similarity": 0.95,
            "page_number": 1,
            "source_label": "Page 1",
            "metadata": {}
        }
    ]
    mock_db.return_value.rpc.return_value.execute.return_value = mock_rpc_res
    
    response = client.post(
        f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/search",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"query": "test query", "match_count": 5}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["content"] == "Match 1"
    assert data[0]["similarity"] == 0.95
    
    # Verify correct user_id filtering was passed to RPC
    args, kwargs = mock_db.return_value.rpc.call_args
    assert args[0] == "match_document_chunks"
    assert args[1]["filter_user_id"] == FAKE_USER_ID
