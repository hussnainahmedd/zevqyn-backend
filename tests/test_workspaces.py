"""Unit tests for workspace endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FAKE_USER_ID = str(uuid.uuid4())
FAKE_WORKSPACE_ID = str(uuid.uuid4())
FAKE_TOKEN = "valid-token"

# Mock auth dependency
def mock_get_user(mock_auth):
    user = MagicMock()
    user.id = FAKE_USER_ID
    user.email = "test@example.com"
    response = MagicMock()
    response.user = user
    mock_auth.return_value.auth.get_user.return_value = response


@pytest.fixture(autouse=True)
def setup_auth(monkeypatch):
    """Automatically mock auth for all tests here unless overridden."""
    with patch("app.core.auth.get_admin_client") as mock_get:
        mock_get_user(mock_get)
        yield mock_get


def test_create_workspace(setup_auth):
    with patch("app.services.workspaces.get_admin_client") as mock_db:
        mock_db_res = MagicMock()
        mock_db_res.data = [{
            "id": FAKE_WORKSPACE_ID,
            "user_id": FAKE_USER_ID,
            "name": "Test Workspace",
            "description": "A test workspace",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }]
        mock_db.return_value.table.return_value.insert.return_value.execute.return_value = mock_db_res
        
        response = client.post(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
            json={"name": "Test Workspace", "description": "A test workspace"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == FAKE_WORKSPACE_ID
        assert data["user_id"] == FAKE_USER_ID
        assert data["name"] == "Test Workspace"


def test_list_workspaces(setup_auth):
    with patch("app.services.workspaces.get_admin_client") as mock_db:
        mock_db_res = MagicMock()
        mock_db_res.data = [{
            "id": FAKE_WORKSPACE_ID,
            "user_id": FAKE_USER_ID,
            "name": "Test Workspace",
            "description": "A test workspace",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }]
        # Setup the fluent chain
        chain = mock_db.return_value.table.return_value.select.return_value.eq.return_value.execute
        chain.return_value = mock_db_res
        
        response = client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == FAKE_WORKSPACE_ID


def test_get_workspace_not_found(setup_auth):
    with patch("app.services.workspaces.get_admin_client") as mock_db:
        mock_db_res = MagicMock()
        mock_db_res.data = []
        
        # Setup the fluent chain
        chain = mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute
        chain.return_value = mock_db_res
        
        response = client.get(
            f"/api/v1/workspaces/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
        )
        
        assert response.status_code == 404


def test_unauthenticated_create():
    # Intentionally bypass the setup_auth fixture by not sending token
    # The app should reject it before hitting the mocked service
    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Test Workspace", "description": "A test workspace"}
    )
    assert response.status_code == 401


def test_delete_workspace_with_documents(setup_auth):
    with patch("app.services.workspaces.get_admin_client") as mock_db:
        # 1. get_workspace passes (workspace exists)
        mock_ws_res = MagicMock()
        mock_ws_res.data = [{"id": FAKE_WORKSPACE_ID, "user_id": FAKE_USER_ID, "name": "Test Workspace", "description": "", "created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z"}]
        
        # 2. Document check finds documents
        mock_doc_res = MagicMock()
        mock_doc_res.data = [{"id": "some-doc-id"}]
        
        # We need a side effect or separate mocks for different table calls, but for simplicity
        # we can just mock the whole get_admin_client.table behavior based on the table name.
        def mock_table(name):
            t = MagicMock()
            if name == "workspaces":
                t.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_ws_res
            elif name == "documents":
                t.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_doc_res
            return t
            
        mock_db.return_value.table.side_effect = mock_table
        
        response = client.delete(
            f"/api/v1/workspaces/{FAKE_WORKSPACE_ID}",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
        )
        
        assert response.status_code == 409
        assert "documents" in response.json()["detail"].lower()
