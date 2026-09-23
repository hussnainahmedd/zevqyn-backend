"""Unit tests for document endpoints."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

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


def test_upload_document_success(setup_auth):
    with patch("app.services.documents.get_workspace") as mock_get_ws, \
         patch("app.services.documents.get_admin_client") as mock_db:
         
        # Workspace exists
        mock_get_ws.return_value = True
        
        # Storage upload success
        mock_db.return_value.storage.from_.return_value.upload.return_value = {"Key": "test"}
        
        # DB insert success
        mock_db_res = MagicMock()
        mock_db_res.data = [{
            "id": FAKE_DOC_ID,
            "user_id": FAKE_USER_ID,
            "workspace_id": FAKE_WORKSPACE_ID,
            "original_filename": "test.txt",
            "file_type": ".txt",
            "file_size": 12,
            "status": "uploaded",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }]
        mock_db.return_value.table.return_value.insert.return_value.execute.return_value = mock_db_res
        
        file_content = b"Hello, world"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        
        response = client.post(
            f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/documents",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
            files=files
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == FAKE_DOC_ID
        assert data["original_filename"] == "test.txt"
        assert "storage_path" not in data


def test_upload_invalid_extension(setup_auth):
    with patch("app.services.documents.get_workspace") as mock_get_ws:
        mock_get_ws.return_value = True
        
        files = {"file": ("test.exe", io.BytesIO(b"bad"), "application/x-msdownload")}
        
        response = client.post(
            f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/documents",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
            files=files
        )
        
        assert response.status_code == 415
        assert "Unsupported file type" in response.json()["detail"]


def test_upload_too_large(setup_auth, monkeypatch):
    # Temporarily set max size to 0 bytes so anything fails (can't easily set to 10 bytes via MB)
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    
    with patch("app.services.documents.get_workspace") as mock_get_ws:
        mock_get_ws.return_value = True
        
        file_content = b"This is more than 10 bytes long"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        
        response = client.post(
            f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/documents",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
            files=files
        )
        
        assert response.status_code == 413
        assert "exceeds maximum allowed size" in response.json()["detail"]


def test_upload_db_failure_rolls_back_storage(setup_auth):
    with patch("app.services.documents.get_workspace") as mock_get_ws, \
         patch("app.services.documents.get_admin_client") as mock_db:
         
        mock_get_ws.return_value = True
        
        # Storage succeeds
        mock_storage = mock_db.return_value.storage.from_.return_value
        mock_storage.upload.return_value = {"Key": "test"}
        
        # DB fails
        mock_db.return_value.table.return_value.insert.return_value.execute.side_effect = Exception("DB Error")
        
        file_content = b"Hello, world"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        
        response = client.post(
            f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/documents",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
            files=files
        )
        
        assert response.status_code == 500
        # Ensure remove was called on storage
        assert mock_storage.remove.called


def test_delete_document(setup_auth):
    with patch("app.services.documents.get_document") as mock_get_doc, \
         patch("app.services.documents.get_admin_client") as mock_db:
         
        mock_get_doc.return_value = True
        
        # DB returning storage path
        mock_db_res = MagicMock()
        mock_db_res.data = [{"storage_path": "user/ws/doc/test.txt"}]
        mock_table_select = mock_db.return_value.table.return_value.select.return_value
        mock_table_select.eq.return_value.execute.return_value = mock_db_res
        
        # DB deletion success
        mock_db_del = MagicMock()
        mock_db_del.data = [{"id": FAKE_DOC_ID}]
        mock_table_del = mock_db.return_value.table.return_value.delete.return_value
        mock_table_del.eq.return_value.eq.return_value.execute.return_value = mock_db_del
        
        response = client.delete(
            f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}/documents/{FAKE_DOC_ID}",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
        )
        
        assert response.status_code == 204
        
        # Storage removal should have been called
        mock_db.return_value.storage.from_.return_value.remove.assert_called_with(["user/ws/doc/test.txt"])


# ==============================================================================
# V1.1 TESTS: GLOBAL DOCUMENTS
# ==============================================================================
def _sample_doc_row(doc_id=None, ws_id=None, filename="document.pdf", file_type="pdf", status="uploaded"):
    return {
        "id": str(doc_id or uuid.uuid4()),
        "user_id": FAKE_USER_ID,
        "workspace_id": str(ws_id or uuid.uuid4()),
        "original_filename": filename,
        "file_type": file_type,
        "file_size": 1024,
        "status": status,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


@patch("app.services.documents.get_admin_client")
def test_list_global_documents_all(mock_db, setup_auth):
    """Test retrieving all documents for the authenticated user."""
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [
        _sample_doc_row(filename="doc1.pdf"),
        _sample_doc_row(filename="doc2.docx", file_type="docx"),
    ]

    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value = mock_query
    mock_query.order.return_value.range.return_value.execute.return_value = mock_res

    response = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["original_filename"] == "doc1.pdf"
    assert data[1]["original_filename"] == "doc2.docx"


@patch("app.services.documents.get_admin_client")
def test_list_global_documents_empty(mock_db, setup_auth):
    """Test retrieving documents when user has none."""
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = []

    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value = mock_query
    mock_query.order.return_value.range.return_value.execute.return_value = mock_res

    response = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_global_documents_unauthenticated():
    """Test that listing documents requires authentication."""
    response = client.get("/api/v1/documents")
    assert response.status_code in (401, 403)


@patch("app.services.documents.get_admin_client")
def test_list_global_documents_filters(mock_db, setup_auth):
    """Test applying workspace_id, file_type, status, and search filters."""
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [_sample_doc_row(filename="search_result.pdf", file_type="pdf", status="indexed")]

    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.ilike.return_value = mock_query
    mock_query.order.return_value.range.return_value.execute.return_value = mock_res

    target_ws = str(uuid.uuid4())
    response = client.get(
        f"/api/v1/documents?workspace_id={target_ws}&file_type=pdf&status=indexed&search=search_result&limit=10&offset=0",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["original_filename"] == "search_result.pdf"


def test_list_global_documents_invalid_limit(setup_auth):
    """Test validation rejection for invalid limit (<1 or >100)."""
    resp_zero = client.get("/api/v1/documents?limit=0", headers={"Authorization": f"Bearer {FAKE_TOKEN}"})
    assert resp_zero.status_code == 422

    resp_too_high = client.get("/api/v1/documents?limit=101", headers={"Authorization": f"Bearer {FAKE_TOKEN}"})
    assert resp_too_high.status_code == 422


def test_list_global_documents_invalid_offset(setup_auth):
    """Test validation rejection for negative offset."""
    resp = client.get("/api/v1/documents?offset=-1", headers={"Authorization": f"Bearer {FAKE_TOKEN}"})
    assert resp.status_code == 422
