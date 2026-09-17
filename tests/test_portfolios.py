"""Tests for portfolios and public access."""

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


@patch("app.services.portfolios.get_admin_client")
def test_create_portfolio_slug_uniqueness(mock_db):
    mock_client = mock_db.return_value
    
    # Simulate slug taken
    mock_res = MagicMock()
    mock_res.data = [{"id": str(uuid.uuid4())}]
    mock_client.table().select().eq().execute.return_value = mock_res
    
    response = client.post(
        "/api/v1/portfolios",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={
            "slug": "taken-slug",
            "display_name": "My Port"
        }
    )
    
    assert response.status_code == 409
    assert "Slug is already in use" in response.json()["detail"]


@patch("app.services.portfolios.get_admin_client")
def test_public_portfolio_visibility(mock_db):
    mock_client = mock_db.return_value
    
    # Simulate private portfolio
    mock_port_res = MagicMock()
    mock_port_res.data = [{
        "id": str(uuid.uuid4()),
        "slug": "my-slug",
        "display_name": "Test",
        "theme": "light",
        "is_published": False
    }]
    mock_client.table().select().eq().execute.return_value = mock_port_res
    
    # Anonymous request
    response = client.get("/api/v1/public/portfolios/my-slug")
    assert response.status_code == 404 # Concealed as 404
    
    # Change to public
    mock_port_res.data[0]["is_published"] = True
    
    # Mock projects empty
    mock_proj_res = MagicMock()
    mock_proj_res.data = []
    mock_client.table().select().eq().order().execute.return_value = mock_proj_res
    
    response2 = client.get("/api/v1/public/portfolios/my-slug")
    assert response2.status_code == 200
    assert response2.json()["display_name"] == "Test"
    # Ensure no sensitive fields like user_id leak
    assert "user_id" not in response2.json()


@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_project")
@patch("app.services.portfolios.get_portfolio")
def test_add_portfolio_project_cross_user_rejected(mock_get_port, mock_get_proj, mock_db):
    # Simulate project fetch failing due to ownership
    from fastapi import HTTPException
    mock_get_proj.side_effect = HTTPException(status_code=404, detail="Not found")
    
    response = client.post(
        f"/api/v1/portfolios/{uuid.uuid4()}/projects",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"project_id": str(uuid.uuid4())}
    )
    
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


@patch("app.services.portfolios.get_admin_client")
def test_create_portfolio_slug_db_constraint(mock_db):
    mock_client = mock_db.return_value
    
    # Pre-check passes
    mock_select = MagicMock()
    mock_select.data = []
    mock_client.table().select().eq().execute.return_value = mock_select
    
    # DB insert fails with unique constraint
    mock_client.table().insert().execute.side_effect = Exception("duplicate key value violates unique constraint 'portfolios_slug_key'")
    
    response = client.post(
        "/api/v1/portfolios",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={
            "slug": "taken-slug",
            "display_name": "My Port"
        }
    )
    
    assert response.status_code == 409
    assert "Slug is already in use" in response.json()["detail"]


@patch("app.services.portfolios.get_portfolio")
@patch("app.services.portfolios.get_admin_client")
def test_update_portfolio_slug_db_constraint(mock_db, mock_get_port):
    # Mock portfolio ownership
    mock_get_port.return_value = MagicMock()
    
    mock_client = mock_db.return_value
    
    # Pre-check passes
    mock_select = MagicMock()
    mock_select.data = []
    mock_client.table().select().eq().neq().execute.return_value = mock_select
    
    # DB update fails with 23505
    mock_client.table().update().eq().eq().execute.side_effect = Exception("error code 23505")
    
    response = client.patch(
        f"/api/v1/portfolios/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={
            "slug": "new-taken-slug"
        }
    )
    
    assert response.status_code == 409
    assert "Slug is already in use" in response.json()["detail"]
