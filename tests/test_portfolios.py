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


# ==============================================================================
# SKILLS TESTS
# ==============================================================================
@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_skill")
@patch("app.services.portfolios.get_portfolio")
def test_add_portfolio_skill_success(mock_get_port, mock_get_skill, mock_db):
    port_id = str(uuid.uuid4())
    skill_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    
    mock_get_port.return_value = MagicMock()
    mock_get_skill.return_value = MagicMock()
    
    mock_client = mock_db.return_value
    mock_select = MagicMock()
    mock_select.data = []
    mock_client.table().select().eq().eq().execute.return_value = mock_select
    
    mock_insert = MagicMock()
    mock_insert.data = [{
        "id": item_id,
        "portfolio_id": port_id,
        "skill_id": skill_id,
        "sort_order": 1,
        "created_at": "2026-09-19T10:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_insert
    
    response = client.post(
        f"/api/v1/portfolios/{port_id}/skills",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"skill_id": skill_id, "sort_order": 1}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["portfolio_id"] == port_id
    assert data["skill_id"] == skill_id
    assert data["sort_order"] == 1


@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_skill")
@patch("app.services.portfolios.get_portfolio")
def test_add_portfolio_skill_duplicate_rejected(mock_get_port, mock_get_skill, mock_db):
    port_id = str(uuid.uuid4())
    skill_id = str(uuid.uuid4())
    
    mock_get_port.return_value = MagicMock()
    mock_get_skill.return_value = MagicMock()
    
    mock_client = mock_db.return_value
    mock_select = MagicMock()
    mock_select.data = [{"id": str(uuid.uuid4())}]
    mock_client.table().select().eq().eq().execute.return_value = mock_select
    
    response = client.post(
        f"/api/v1/portfolios/{port_id}/skills",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"skill_id": skill_id}
    )
    assert response.status_code == 400
    assert "already in portfolio" in response.json()["detail"]


@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_skill")
@patch("app.services.portfolios.get_portfolio")
def test_add_portfolio_skill_cross_user_rejected(mock_get_port, mock_get_skill, mock_db):
    from fastapi import HTTPException
    mock_get_port.return_value = MagicMock()
    mock_get_skill.side_effect = HTTPException(status_code=404, detail="Skill not found")
    
    response = client.post(
        f"/api/v1/portfolios/{uuid.uuid4()}/skills",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"skill_id": str(uuid.uuid4())}
    )
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_portfolio")
def test_remove_portfolio_skill(mock_get_port, mock_db):
    mock_get_port.return_value = MagicMock()
    mock_client = mock_db.return_value
    
    port_id = str(uuid.uuid4())
    skill_id = str(uuid.uuid4())
    response = client.delete(
        f"/api/v1/portfolios/{port_id}/skills/{skill_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


# ==============================================================================
# EDUCATION TESTS
# ==============================================================================
@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_education")
@patch("app.services.portfolios.get_portfolio")
def test_add_portfolio_education_success(mock_get_port, mock_get_edu, mock_db):
    port_id = str(uuid.uuid4())
    edu_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    
    mock_get_port.return_value = MagicMock()
    mock_get_edu.return_value = MagicMock()
    
    mock_client = mock_db.return_value
    mock_select = MagicMock()
    mock_select.data = []
    mock_client.table().select().eq().eq().execute.return_value = mock_select
    
    mock_insert = MagicMock()
    mock_insert.data = [{
        "id": item_id,
        "portfolio_id": port_id,
        "education_id": edu_id,
        "sort_order": 0,
        "created_at": "2026-09-19T10:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_insert
    
    response = client.post(
        f"/api/v1/portfolios/{port_id}/education",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"education_id": edu_id}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["education_id"] == edu_id


@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_education")
@patch("app.services.portfolios.get_portfolio")
def test_add_portfolio_education_cross_user_rejected(mock_get_port, mock_get_edu, mock_db):
    from fastapi import HTTPException
    mock_get_port.return_value = MagicMock()
    mock_get_edu.side_effect = HTTPException(status_code=404, detail="Education not found")
    
    response = client.post(
        f"/api/v1/portfolios/{uuid.uuid4()}/education",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"education_id": str(uuid.uuid4())}
    )
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_portfolio")
def test_remove_portfolio_education(mock_get_port, mock_db):
    mock_get_port.return_value = MagicMock()
    port_id = str(uuid.uuid4())
    edu_id = str(uuid.uuid4())
    response = client.delete(
        f"/api/v1/portfolios/{port_id}/education/{edu_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


# ==============================================================================
# CERTIFICATES TESTS
# ==============================================================================
@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_certificate")
@patch("app.services.portfolios.get_portfolio")
def test_add_portfolio_certificate_success(mock_get_port, mock_get_cert, mock_db):
    port_id = str(uuid.uuid4())
    cert_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    
    mock_get_port.return_value = MagicMock()
    mock_get_cert.return_value = MagicMock()
    
    mock_client = mock_db.return_value
    mock_select = MagicMock()
    mock_select.data = []
    mock_client.table().select().eq().eq().execute.return_value = mock_select
    
    mock_insert = MagicMock()
    mock_insert.data = [{
        "id": item_id,
        "portfolio_id": port_id,
        "certificate_id": cert_id,
        "sort_order": 0,
        "created_at": "2026-09-19T10:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_insert
    
    response = client.post(
        f"/api/v1/portfolios/{port_id}/certificates",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"certificate_id": cert_id}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["certificate_id"] == cert_id


@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_certificate")
@patch("app.services.portfolios.get_portfolio")
def test_add_portfolio_certificate_cross_user_rejected(mock_get_port, mock_get_cert, mock_db):
    from fastapi import HTTPException
    mock_get_port.return_value = MagicMock()
    mock_get_cert.side_effect = HTTPException(status_code=404, detail="Certificate not found")
    
    response = client.post(
        f"/api/v1/portfolios/{uuid.uuid4()}/certificates",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"certificate_id": str(uuid.uuid4())}
    )
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


@patch("app.services.portfolios.get_admin_client")
@patch("app.services.portfolios.get_portfolio")
def test_remove_portfolio_certificate(mock_get_port, mock_db):
    mock_get_port.return_value = MagicMock()
    port_id = str(uuid.uuid4())
    cert_id = str(uuid.uuid4())
    response = client.delete(
        f"/api/v1/portfolios/{port_id}/certificates/{cert_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


# ==============================================================================
# PUBLIC ENRICHED PORTFOLIO TESTS
# ==============================================================================
@patch("app.services.portfolios.get_admin_client")
def test_public_portfolio_with_all_career_records(mock_db):
    mock_client = mock_db.return_value
    port_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    skill_id = str(uuid.uuid4())
    edu_id = str(uuid.uuid4())
    cert_id = str(uuid.uuid4())
    
    mock_port_res = MagicMock()
    mock_port_res.data = [{
        "id": port_id,
        "slug": "hussnain-portfolio",
        "display_name": "Hussnain Ahmad",
        "headline": "Backend Dev",
        "about": "Passionate engineer",
        "profile_image_url": "https://img.com/avatar.jpg",
        "theme": "dark",
        "is_published": True,
        "show_contact": True,
        "show_certificates": True,
        "github_url": "https://github.com/hussnain",
        "linkedin_url": "https://linkedin.com/in/hussnain",
        "website_url": "https://hussnain.dev"
    }]
    
    def mock_table(table_name):
        tbl = MagicMock()
        if table_name == "portfolios":
            tbl.select.return_value.eq.return_value.execute.return_value = mock_port_res
        elif table_name == "portfolio_projects":
            res = MagicMock()
            res.data = [{"project_id": proj_id}]
            tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = res
        elif table_name == "projects":
            res = MagicMock()
            res.data = [{
                "id": proj_id,
                "title": "ZEVQYN AI",
                "short_description": "AI Workspace",
                "description": "Full details",
                "technologies": ["Python", "FastAPI"],
                "skills": ["API Design"],
                "github_url": "https://github.com/zevqyn",
                "live_url": "https://zevqyn.com",
                "image_url": "https://zevqyn.com/logo.png"
            }]
            tbl.select.return_value.in_.return_value.execute.return_value = res
        elif table_name == "portfolio_skills":
            res = MagicMock()
            res.data = [{"skill_id": skill_id}]
            tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = res
        elif table_name == "skills":
            res = MagicMock()
            res.data = [{
                "id": skill_id,
                "name": "Python",
                "category": "Backend",
                "proficiency": 5
            }]
            tbl.select.return_value.in_.return_value.execute.return_value = res
        elif table_name == "portfolio_education":
            res = MagicMock()
            res.data = [{"education_id": edu_id}]
            tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = res
        elif table_name == "education":
            res = MagicMock()
            res.data = [{
                "id": edu_id,
                "institution": "University of Engineering & Tech",
                "degree": "BS",
                "field_of_study": "Computer Science",
                "start_date": "2020-09-01",
                "end_date": "2024-06-30",
                "description": "Honors graduate"
            }]
            tbl.select.return_value.in_.return_value.execute.return_value = res
        elif table_name == "portfolio_certificates":
            res = MagicMock()
            res.data = [{"certificate_id": cert_id}]
            tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = res
        elif table_name == "certificates":
            res = MagicMock()
            res.data = [{
                "id": cert_id,
                "title": "Python Specialist",
                "issuer": "Coursera",
                "issue_date": "2024-01-15",
                "expiry_date": None,
                "credential_id": "CERT-1234",
                "credential_url": "https://coursera.org/verify/1234",
                "description": "Advanced Python"
            }]
            tbl.select.return_value.in_.return_value.execute.return_value = res
        return tbl
        
    mock_client.table.side_effect = mock_table
    
    response = client.get("/api/v1/public/portfolios/hussnain-portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "hussnain-portfolio"
    assert len(data["projects"]) == 1
    assert data["projects"][0]["title"] == "ZEVQYN AI"
    assert len(data["skills"]) == 1
    assert data["skills"][0]["name"] == "Python"
    assert data["skills"][0]["proficiency"] == 5
    assert len(data["education"]) == 1
    assert data["education"][0]["institution"] == "University of Engineering & Tech"
    assert len(data["certificates"]) == 1
    assert data["certificates"][0]["title"] == "Python Specialist"
    
    # Assert privacy
    assert "user_id" not in data
    assert "id" not in data["skills"][0]
    assert "id" not in data["education"][0]
    assert "id" not in data["certificates"][0]


@patch("app.services.portfolios.get_admin_client")
def test_public_portfolio_show_certificates_false(mock_db):
    mock_client = mock_db.return_value
    port_id = str(uuid.uuid4())
    
    mock_port_res = MagicMock()
    mock_port_res.data = [{
        "id": port_id,
        "slug": "hussnain-portfolio",
        "display_name": "Hussnain Ahmad",
        "theme": "light",
        "is_published": True,
        "show_certificates": False
    }]
    
    def mock_table(table_name):
        tbl = MagicMock()
        if table_name == "portfolios":
            tbl.select.return_value.eq.return_value.execute.return_value = mock_port_res
        else:
            res = MagicMock()
            res.data = []
            tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = res
        return tbl
        
    mock_client.table.side_effect = mock_table
    
    response = client.get("/api/v1/public/portfolios/hussnain-portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["certificates"] == []

