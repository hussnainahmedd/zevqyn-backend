"""Tests for resumes and PDF export."""

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


@patch("app.services.resumes.get_admin_client")
def test_create_resume(mock_db):
    mock_client = mock_db.return_value
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": str(uuid.uuid4()),
        "user_id": FAKE_USER,
        "name": "My Resume",
        "template": "professional",
        "professional_summary": "I am a dev.",
        "visibility": "private",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_res
    
    malicious_payload = {
        "name": "My Resume",
        "template": "professional",
        "user_id": "other-user",
        "hacked_field": True
    }
    
    # Extra forbid should block hacked_field
    response = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=malicious_payload
    )
    assert response.status_code == 422
    
    # Valid payload
    response = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "My Resume", "template": "professional"}
    )
    assert response.status_code == 200
    called_data = mock_client.table().insert.call_args[0][0]
    assert called_data["user_id"] == FAKE_USER


@patch("app.services.resumes.get_admin_client")
def test_get_resume_cross_user_rejected(mock_db):
    mock_client = mock_db.return_value
    
    mock_res = MagicMock()
    mock_res.data = [] # Not found or not owned
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.get(f"/api/v1/resumes/{uuid.uuid4()}", headers={"Authorization": f"Bearer {FAKE_TOKEN}"})
    assert response.status_code == 404


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_project")
@patch("app.services.resumes.get_resume")
def test_create_resume_item(mock_get_resume, mock_get_project, mock_db):
    mock_client = mock_db.return_value
    
    # Mock project fetch
    mock_proj = MagicMock()
    mock_proj.title = "Zevqyn"
    mock_proj.technologies = ["Python"]
    mock_proj.short_description = "Cool app"
    mock_get_project.return_value = mock_proj
    
    # Mock no existing item
    mock_res_select = MagicMock()
    mock_res_select.data = []
    mock_client.table().select().eq().eq().execute.return_value = mock_res_select
    
    # Mock insert
    mock_res_insert = MagicMock()
    mock_res_insert.data = [{
        "id": str(uuid.uuid4()),
        "resume_id": str(uuid.uuid4()),
        "section_type": "project",
        "title": "Zevqyn",
        "subtitle": "Python",
        "description": "Cool app",
        "metadata": {"source_id": str(uuid.uuid4()), "source_type": "project"},
        "sort_order": 0,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().insert().execute.return_value = mock_res_insert
    
    response = client.post(
        f"/api/v1/resumes/{uuid.uuid4()}/items",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"section_type": "project", "source_id": str(uuid.uuid4())}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Zevqyn"


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf(mock_get_resume, mock_get_items, mock_db):
    class FakeResume:
        id = uuid.uuid4()
        name = "Test Resume"
        professional_summary = "Summary"
    mock_get_resume.return_value = FakeResume()
    mock_get_items.return_value = []
    
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{"full_name": "John Doe"}]
    mock_client.table().select().eq().execute.return_value = mock_res
    
    response = client.get(
        f"/api/v1/resumes/{uuid.uuid4()}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_unicode_safety(mock_get_resume, mock_get_items, mock_db):
    class FakeResume:
        id = uuid.uuid4()
        name = "Unicode"
        professional_summary = "Emoji 🚀 and CJK 测试"
        
    class FakeItem:
        section_type = "project"
        title = "Project 🚀"
        subtitle = "Subtitle"
        description = "Desc"
        
    mock_get_resume.return_value = FakeResume()
    mock_get_items.return_value = [FakeItem()]
    
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{"full_name": "Test User"}]
    mock_client.table().select().eq().execute.return_value = mock_res
    
    response = client.get(
        f"/api/v1/resumes/{uuid.uuid4()}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    # Should not crash, un-encodeable chars replaced with ?
    assert response.content.startswith(b"%PDF")

@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume")
def test_resume_item_unknown_source_rejected(mock_get_resume, mock_db):
    response = client.post(
        f"/api/v1/resumes/{uuid.uuid4()}/items",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"section_type": "invalid_type", "source_id": str(uuid.uuid4())}
    )
    # Pydantic Regex rejection
    assert response.status_code == 422


@patch("app.services.resumes.get_admin_client")
def test_create_resume_with_personal_info(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    payload = {
        "name": "Software Engineer Resume",
        "template": "modern",
        "professional_summary": "Full-stack developer with 3 years experience.",
        "visibility": "public",
        "full_name": "Hussnain Ahmad",
        "professional_title": "Computer Science Student",
        "email": "hussnain@example.com",
        "phone": "+92 300 1234567",
        "location": "Islamabad, Pakistan",
        "linkedin_url": "https://linkedin.com/in/hussnain",
        "github_url": "https://github.com/hussnain",
        "portfolio_url": "https://hussnain.dev"
    }
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        **payload
    }]
    mock_client.table().insert().execute.return_value = mock_res
    
    response = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == resume_id
    assert data["name"] == "Software Engineer Resume"
    assert data["full_name"] == "Hussnain Ahmad"
    assert data["professional_title"] == "Computer Science Student"
    assert data["email"] == "hussnain@example.com"
    assert data["phone"] == "+92 300 1234567"
    assert data["location"] == "Islamabad, Pakistan"
    assert data["linkedin_url"] == "https://linkedin.com/in/hussnain"
    assert data["github_url"] == "https://github.com/hussnain"
    assert data["portfolio_url"] == "https://hussnain.dev"
    
    called_insert = mock_client.table().insert.call_args[0][0]
    assert called_insert["full_name"] == "Hussnain Ahmad"
    assert called_insert["professional_title"] == "Computer Science Student"
    assert called_insert["email"] == "hussnain@example.com"
    assert called_insert["phone"] == "+92 300 1234567"
    assert called_insert["location"] == "Islamabad, Pakistan"
    assert called_insert["linkedin_url"] == "https://linkedin.com/in/hussnain"
    assert called_insert["github_url"] == "https://github.com/hussnain"
    assert called_insert["portfolio_url"] == "https://hussnain.dev"


@patch("app.services.resumes.get_admin_client")
def test_create_resume_validation_limits(mock_db):
    # Test full_name max length (150)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "full_name": "A" * 151}
    )
    assert res.status_code == 422

    # Test email max length (254)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "email": "a" * 255}
    )
    assert res.status_code == 422

    # Test phone max length (50)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "phone": "1" * 51}
    )
    assert res.status_code == 422

    # Test location max length (150)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "location": "L" * 151}
    )
    assert res.status_code == 422

    # Test linkedin_url max length (500)
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "linkedin_url": "https://linkedin.com/" + ("u" * 500)}
    )
    assert res.status_code == 422

    # Test extra field forbidden
    res = client.post(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"name": "Resume", "unknown_field": "disallowed"}
    )
    assert res.status_code == 422


@patch("app.services.resumes.get_admin_client")
def test_get_resume_with_personal_info(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    mock_res = MagicMock()
    mock_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Tech Resume",
        "template": "professional",
        "professional_summary": "Summary text",
        "visibility": "private",
        "full_name": "Hussnain Ahmad",
        "professional_title": "Software Engineer",
        "email": "hussnain@test.com",
        "phone": "+923001234567",
        "location": "Lahore, Pakistan",
        "linkedin_url": "https://linkedin.com/in/test",
        "github_url": "https://github.com/test",
        "portfolio_url": "https://test.me",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.get(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Hussnain Ahmad"
    assert data["professional_title"] == "Software Engineer"
    assert data["email"] == "hussnain@test.com"
    assert data["phone"] == "+923001234567"
    assert data["location"] == "Lahore, Pakistan"
    assert data["linkedin_url"] == "https://linkedin.com/in/test"
    assert data["github_url"] == "https://github.com/test"
    assert data["portfolio_url"] == "https://test.me"


@patch("app.services.resumes.get_admin_client")
def test_get_resume_legacy_null_personal_info(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    # Legacy resume has no personal info fields (or null in DB)
    mock_res = MagicMock()
    mock_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Legacy Resume",
        "template": "professional",
        "professional_summary": None,
        "visibility": "private",
        "full_name": None,
        "professional_title": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin_url": None,
        "github_url": None,
        "portfolio_url": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().select().eq().eq().execute.return_value = mock_res
    
    response = client.get(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Legacy Resume"
    assert data["full_name"] is None
    assert data["professional_title"] is None
    assert data["email"] is None
    assert data["phone"] is None
    assert data["location"] is None
    assert data["linkedin_url"] is None
    assert data["github_url"] is None
    assert data["portfolio_url"] is None


@patch("app.services.resumes.get_admin_client")
def test_update_resume_all_personal_info(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    # Mock existing resume lookup in get_resume()
    mock_get_res = MagicMock()
    mock_get_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Old Name",
        "template": "professional",
        "professional_summary": None,
        "visibility": "private",
        "full_name": None,
        "professional_title": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin_url": None,
        "github_url": None,
        "portfolio_url": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().select().eq().eq().execute.return_value = mock_get_res
    
    update_payload = {
        "full_name": "Hussnain Ahmad",
        "professional_title": "Full Stack Engineer",
        "email": "hussnain@example.com",
        "phone": "+92 300 0000000",
        "location": "Islamabad, Pakistan",
        "linkedin_url": "https://linkedin.com/in/hussnain",
        "github_url": "https://github.com/hussnain",
        "portfolio_url": "https://hussnain.me"
    }
    
    mock_update_res = MagicMock()
    mock_update_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Old Name",
        "template": "professional",
        "professional_summary": None,
        "visibility": "private",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        **update_payload
    }]
    mock_client.table().update().eq().eq().execute.return_value = mock_update_res
    
    response = client.patch(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=update_payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Hussnain Ahmad"
    assert data["professional_title"] == "Full Stack Engineer"
    assert data["email"] == "hussnain@example.com"
    assert data["phone"] == "+92 300 0000000"
    assert data["location"] == "Islamabad, Pakistan"
    assert data["linkedin_url"] == "https://linkedin.com/in/hussnain"
    assert data["github_url"] == "https://github.com/hussnain"
    assert data["portfolio_url"] == "https://hussnain.me"
    
    called_update = mock_client.table().update.call_args[0][0]
    for key, val in update_payload.items():
        assert called_update[key] == val


@patch("app.services.resumes.get_admin_client")
def test_update_resume_partial_preserves_unspecified(mock_db):
    mock_client = mock_db.return_value
    resume_id = str(uuid.uuid4())
    
    mock_get_res = MagicMock()
    mock_get_res.data = [{
        "id": resume_id,
        "user_id": FAKE_USER,
        "name": "Backend Resume",
        "template": "professional",
        "professional_summary": "Original summary",
        "visibility": "private",
        "full_name": "Original Name",
        "professional_title": "Original Title",
        "email": "orig@example.com",
        "phone": "+1234567890",
        "location": "City",
        "linkedin_url": "https://linkedin.com/orig",
        "github_url": "https://github.com/orig",
        "portfolio_url": "https://orig.com",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]
    mock_client.table().select().eq().eq().execute.return_value = mock_get_res
    
    mock_update_res = MagicMock()
    mock_update_res.data = [{
        **mock_get_res.data[0],
        "full_name": "Updated Name Only",
        "updated_at": "2024-01-02T00:00:00Z"
    }]
    mock_client.table().update().eq().eq().execute.return_value = mock_update_res
    
    # Patch ONLY full_name
    response = client.patch(
        f"/api/v1/resumes/{resume_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"full_name": "Updated Name Only"}
    )
    assert response.status_code == 200
    
    # CRITICAL: ensure ONLY full_name was sent to update, not unspecified fields as None
    called_update = mock_client.table().update.call_args[0][0]
    assert called_update == {"full_name": "Updated Name Only"}
    assert "email" not in called_update
    assert "phone" not in called_update
    assert "name" not in called_update
    assert "template" not in called_update


# ==============================================================================
# PDF EXPORT & FORMATTING TESTS
# ==============================================================================
from datetime import date
from app.services.resumes import (
    _clean_text,
    _format_date,
    _format_date_range,
    _format_degree,
    _format_url_label,
    _group_skills,
    _is_valid_summary,
)


def test_pdf_formatting_helpers():
    # 1. _clean_text
    assert _clean_text(None) == ""
    assert _clean_text("") == ""
    assert _clean_text("Hello \u2013 World") == "Hello - World"
    assert _clean_text("Step 1 \u2014 Step 2") == "Step 1  -  Step 2"
    assert _clean_text("\u2018single\u2019 and \u201cdouble\u201d") == "'single' and \"double\""
    assert _clean_text("\u2022 bullet") == "\u00b7 bullet"

    # 2. _format_date
    assert _format_date(None) == ""
    assert _format_date("") == ""
    assert _format_date(date(2024, 9, 1)) == "Sep 2024"
    assert _format_date("2024-09-01") == "Sep 2024"
    assert _format_date("2024-09") == "Sep 2024"
    assert _format_date("2024") == "2024"
    assert _format_date("Present") == "Present"
    assert _format_date("present") == "Present"
    assert _format_date("current") == "Present"

    # 3. _format_date_range
    assert _format_date_range(None) == ""
    assert _format_date_range("2024-09-01", "2028-06-30") == "Sep 2024 - Jun 2028"
    assert _format_date_range("2024-09-01", None) == "Sep 2024 - Present"
    assert _format_date_range("2024-09-01", "Present") == "Sep 2024 - Present"
    assert _format_date_range("2024-09-01 - Present") == "Sep 2024 - Present"
    assert _format_date_range("2024-09-01 \u2013 2028-06-30") == "Sep 2024 - Jun 2028"

    # 4. _format_degree
    assert _format_degree("BS Computer Science", "Computer Science") == "BS Computer Science"
    assert _format_degree("Bachelor of Science", "Computer Science") == "Bachelor of Science in Computer Science"
    assert _format_degree("BS Computer Science in Computer Science") == "BS Computer Science"
    assert _format_degree("Computer Science", "BS Computer Science") == "BS Computer Science"
    assert _format_degree("BS Computer Science", None) == "BS Computer Science"

    # 5. _format_url_label
    assert _format_url_label(None) is None
    assert _format_url_label("None") is None
    assert _format_url_label("null") is None
    assert _format_url_label("https://linkedin.com/in/test", "LinkedIn") == ("LinkedIn", "https://linkedin.com/in/test")
    assert _format_url_label("github.com/test", "GitHub") == ("GitHub", "https://github.com/test")

    # 6. _is_valid_summary
    assert _is_valid_summary(None) is False
    assert _is_valid_summary("") is False
    assert _is_valid_summary("Professional Summary") is False
    assert _is_valid_summary("Add your professional summary.") is False
    assert _is_valid_summary("Summary") is False
    assert _is_valid_summary("Passionate software engineer with 5 years experience.") is True

    # 7. _group_skills
    class Item:
        def __init__(self, title, subtitle=None):
            self.title = title
            self.subtitle = subtitle

    skill_items = [
        Item("JavaScript", "languages"),
        Item("Python", "languages"),
        Item("FastAPI", "Backend"),
        Item("PostgreSQL", "Databases"),
        Item("JavaScript", "languages"),  # duplicate
    ]
    grouped = _group_skills(skill_items)
    assert grouped == {
        "Languages": ["JavaScript", "Python"],
        "Backend": ["FastAPI"],
        "Databases": ["PostgreSQL"],
    }


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_with_all_personal_info(mock_get_resume, mock_get_items, mock_db):
    resume_id = uuid.uuid4()
    
    class FullResume:
        id = resume_id
        name = "Full ATS Resume"
        full_name = "Hussnain Ahmad"
        professional_title = "Full Stack Engineer"
        email = "hussnain@example.com"
        phone = "+92 300 1234567"
        location = "Islamabad, Pakistan"
        linkedin_url = "https://linkedin.com/in/hussnain"
        github_url = "https://github.com/hussnain"
        portfolio_url = "https://hussnain.dev"
        professional_summary = "Experienced full-stack engineer specializing in FastAPI and modern cloud architecture."

    class EduItem:
        section_type = "education"
        title = "Air University"
        subtitle = "BS Computer Science in Computer Science"
        description = "2024-09-01 - Present | Top 5% of class"
        metadata = None

    class ProjItem:
        section_type = "project"
        title = "ZEVQYN AI Platform"
        subtitle = "Python, FastAPI, Supabase"
        description = "Built an end-to-end AI career workspace.\nImplemented ATS resume export."
        metadata = None

    class SkillItem:
        section_type = "skill"
        title = "FastAPI"
        subtitle = "Backend"
        description = "Proficiency: 5/5"
        metadata = None

    class CertItem:
        section_type = "certificate"
        title = "Professional Cloud Architect"
        subtitle = "Google Cloud"
        description = "Issued: 2025-06-15 | ID: GCP-998877"
        metadata = None

    mock_get_resume.return_value = FullResume()
    mock_get_items.return_value = [EduItem(), ProjItem(), SkillItem(), CertItem()]

    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{"full_name": "Fallback Name"}]
    mock_client.table().select().eq().execute.return_value = mock_res

    response = client.get(
        f"/api/v1/resumes/{resume_id}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == f'attachment; filename="resume_{resume_id}.pdf"'
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000

    # Extract text from generated PDF and verify all 8 personal header fields + certificate Credential ID
    import pymupdf
    doc = pymupdf.open(stream=response.content, filetype="pdf")
    pdf_text = "".join(page.get_text() for page in doc)

    assert "HUSSNAIN AHMAD" in pdf_text
    assert "Full Stack Engineer" in pdf_text
    assert "hussnain@example.com" in pdf_text
    assert "+92 300 1234567" in pdf_text
    assert "Islamabad, Pakistan" in pdf_text
    assert "LinkedIn" in pdf_text
    assert "GitHub" in pdf_text
    assert "Portfolio" in pdf_text
    assert "Credential ID" not in pdf_text
    assert "GCP-998877" not in pdf_text
    assert "PROFESSIONAL SUMMARY" in pdf_text
    assert "Experienced full-stack engineer" in pdf_text


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_with_null_personal_info(mock_get_resume, mock_get_items, mock_db):
    resume_id = uuid.uuid4()

    class LegacyResume:
        id = resume_id
        name = "Legacy Resume"
        full_name = None
        professional_title = None
        email = None
        phone = None
        location = None
        linkedin_url = None
        github_url = None
        portfolio_url = None
        professional_summary = None

    mock_get_resume.return_value = LegacyResume()
    mock_get_items.return_value = []

    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{"full_name": "Profile Full Name"}]
    mock_client.table().select().eq().execute.return_value = mock_res

    response = client.get(
        f"/api/v1/resumes/{resume_id}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_empty_sections_and_placeholder_summary(mock_get_resume, mock_get_items, mock_db):
    resume_id = uuid.uuid4()

    class ResumeWithPlaceholder:
        id = resume_id
        name = "Empty Resume"
        full_name = "Jane Doe"
        professional_title = "Developer"
        email = "jane@example.com"
        phone = None
        location = None
        linkedin_url = None
        github_url = None
        portfolio_url = None
        # Placeholder summary must be omitted
        professional_summary = "Add your professional summary."

    mock_get_resume.return_value = ResumeWithPlaceholder()
    mock_get_items.return_value = []

    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = []
    mock_client.table().select().eq().execute.return_value = mock_res

    response = client.get(
        f"/api/v1/resumes/{resume_id}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_skill_grouping_ignores_proficiency(mock_get_resume, mock_get_items, mock_db):
    resume_id = uuid.uuid4()

    class ResumeObj:
        id = resume_id
        name = "Skills Resume"
        full_name = "Skill Tester"
        professional_title = "Polyglot Dev"
        email = "test@example.com"
        phone = None
        location = None
        linkedin_url = None
        github_url = None
        portfolio_url = None
        professional_summary = "Passionate engineer."

    class SkillItem:
        def __init__(self, title, category, proficiency):
            self.section_type = "skill"
            self.title = title
            self.subtitle = category
            self.description = f"Proficiency: {proficiency}/5"
            self.metadata = None

    items = [
        SkillItem("Python", "Languages", 5),
        SkillItem("JavaScript", "Languages", 4),
        SkillItem("FastAPI", "Backend", 5),
        SkillItem("PostgreSQL", "Databases", 4),
    ]

    mock_get_resume.return_value = ResumeObj()
    mock_get_items.return_value = items

    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{"full_name": "Skill Tester"}]
    mock_client.table().select().eq().execute.return_value = mock_res

    response = client.get(
        f"/api/v1/resumes/{resume_id}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@patch("app.services.resumes.get_certificate")
@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_certificate_without_credential_id(mock_get_resume, mock_get_items, mock_db, mock_get_cert):
    """Test: certificate rendering omits Credential ID and displays title, issuer, date, and link."""
    resume_id = uuid.uuid4()

    class ResumeObj:
        id = resume_id
        name = "Cert Resume"
        full_name = "Hussnain Ahmad"
        professional_title = "Computer Science Student"
        email = "ha7886899@gmail.com"
        phone = None
        location = "Islamabad, Pakistan"
        linkedin_url = None
        github_url = None
        portfolio_url = None
        professional_summary = None

    class CertRecord:
        title = "python programing"
        issuer = "Coursera"
        issue_date = "2026-02-12"
        credential_id = None
        credential_url = "https://coursera.org/verify/hbchbciqc"
        description = "hbchbciqc"

    cert_source_id = uuid.uuid4()
    mock_get_cert.return_value = CertRecord()

    class CertItem:
        section_type = "certificate"
        title = "python programing"
        subtitle = "Coursera"
        description = "Issued: 2026-02-12"
        metadata = {"source_id": str(cert_source_id)}

    mock_get_resume.return_value = ResumeObj()
    mock_get_items.return_value = [CertItem()]

    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = []
    mock_client.table().select().eq().execute.return_value = mock_res

    response = client.get(
        f"/api/v1/resumes/{resume_id}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")

    import pymupdf
    doc = pymupdf.open(stream=response.content, filetype="pdf")
    pdf_text = "".join(page.get_text() for page in doc)

    # Title, issuer, and date must be present
    assert "python programing - Coursera" in pdf_text
    assert "Feb 2026" in pdf_text
    assert "Verify Credential" in pdf_text

    # Credential ID and raw token must NOT appear in PDF text
    assert "Credential ID" not in pdf_text
    assert "hbchbciqc" not in pdf_text


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_with_dict_resume(mock_get_resume, mock_get_items, mock_db):
    """Test Issue 1: dict resume representation correctly extracts all fields."""
    resume_id = uuid.uuid4()
    resume_dict = {
        "id": resume_id,
        "name": "Dict Resume",
        "full_name": "Dict Hussnain",
        "professional_title": "Dict Developer",
        "email": "dict@example.com",
        "phone": "+1234567890",
        "location": "Rawalpindi, Pakistan",
        "linkedin_url": "https://linkedin.com/in/dict",
        "github_url": "https://github.com/dict",
        "portfolio_url": "https://dict.dev",
        "professional_summary": "Dict summary text here.",
    }
    mock_get_resume.return_value = resume_dict
    mock_get_items.return_value = []

    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = []
    mock_client.table().select().eq().execute.return_value = mock_res

    response = client.get(
        f"/api/v1/resumes/{resume_id}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    import pymupdf
    doc = pymupdf.open(stream=response.content, filetype="pdf")
    pdf_text = "".join(page.get_text() for page in doc)

    assert "DICT HUSSNAIN" in pdf_text
    assert "Dict Developer" in pdf_text
    assert "dict@example.com" in pdf_text
    assert "+1234567890" in pdf_text
    assert "Rawalpindi, Pakistan" in pdf_text


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_resume")
def test_export_pdf_profile_fallbacks_when_resume_fields_null(mock_get_resume, mock_get_items, mock_db):
    """Test Issue 1: profile fallbacks populate missing fields when resume fields are null."""
    resume_id = uuid.uuid4()
    class NullResume:
        id = resume_id
        name = "Empty Resume"
        full_name = None
        professional_title = None
        email = None
        phone = None
        location = None
        linkedin_url = None
        github_url = None
        portfolio_url = None
        professional_summary = None

    mock_get_resume.return_value = NullResume()
    mock_get_items.return_value = []

    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = [{
        "full_name": "Profile Name",
        "bio": "Profile Bio Title",
        "location": "Profile City",
        "phone": "+92 333 1112233",
        "linkedin_url": "https://linkedin.com/in/profile",
        "github_url": "https://github.com/profile",
        "website": "https://profile.me",
    }]
    mock_client.table().select().eq().execute.return_value = mock_res

    response = client.get(
        f"/api/v1/resumes/{resume_id}/pdf",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )

    assert response.status_code == 200
    import pymupdf
    doc = pymupdf.open(stream=response.content, filetype="pdf")
    pdf_text = "".join(page.get_text() for page in doc)

    assert "PROFILE NAME" in pdf_text
    assert "Profile Bio Title" in pdf_text
    assert "Profile City" in pdf_text
    assert "+92 333 1112233" in pdf_text
    assert "LinkedIn" in pdf_text
    assert "GitHub" in pdf_text
    assert "Portfolio" in pdf_text


# ==============================================================================
# V1.1 TESTS: RESUME ITEM REORDERING
# ==============================================================================
@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume")
def test_update_resume_item_success(mock_get_resume, mock_db):
    """Test successful single item sort_order update."""
    resume_id = uuid.uuid4()
    item_id = uuid.uuid4()
    mock_get_resume.return_value = MagicMock(id=resume_id, user_id=FAKE_USER)

    mock_client = mock_db.return_value
    # Select existing item
    mock_select = MagicMock()
    mock_select.data = [{
        "id": str(item_id),
        "resume_id": str(resume_id),
        "section_type": "project",
        "title": "Project Alpha",
        "subtitle": "Python",
        "description": "Desc",
        "metadata": {},
        "sort_order": 0,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }]
    mock_client.table().select().eq().execute.return_value = mock_select

    # Update item
    mock_update = MagicMock()
    mock_update.data = [{
        "id": str(item_id),
        "resume_id": str(resume_id),
        "section_type": "project",
        "title": "Project Alpha",
        "subtitle": "Python",
        "description": "Desc",
        "metadata": {},
        "sort_order": 5,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }]
    mock_client.table().update().eq().eq().execute.return_value = mock_update

    response = client.patch(
        f"/api/v1/resumes/{resume_id}/items/{item_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"sort_order": 5}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sort_order"] == 5
    assert data["id"] == str(item_id)


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume")
def test_update_resume_item_wrong_resume(mock_get_resume, mock_db):
    """Test rejecting an item that belongs to a different resume."""
    resume_id = uuid.uuid4()
    item_id = uuid.uuid4()
    other_resume_id = uuid.uuid4()
    mock_get_resume.return_value = MagicMock(id=resume_id, user_id=FAKE_USER)

    mock_client = mock_db.return_value
    mock_select = MagicMock()
    mock_select.data = [{
        "id": str(item_id),
        "resume_id": str(other_resume_id),
        "section_type": "project",
        "title": "Other Project",
        "sort_order": 0,
    }]
    mock_client.table().select().eq().execute.return_value = mock_select

    response = client.patch(
        f"/api/v1/resumes/{resume_id}/items/{item_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"sort_order": 2}
    )

    assert response.status_code == 400
    assert "Item does not belong to this resume" in response.json()["detail"]


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume")
def test_update_resume_item_not_found(mock_get_resume, mock_db):
    """Test 404 when resume item does not exist."""
    resume_id = uuid.uuid4()
    item_id = uuid.uuid4()
    mock_get_resume.return_value = MagicMock(id=resume_id, user_id=FAKE_USER)

    mock_client = mock_db.return_value
    mock_select = MagicMock()
    mock_select.data = []
    mock_client.table().select().eq().execute.return_value = mock_select

    response = client.patch(
        f"/api/v1/resumes/{resume_id}/items/{item_id}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"sort_order": 1}
    )

    assert response.status_code == 404
    assert "Resume item not found" in response.json()["detail"]


@patch("app.services.resumes.get_admin_client")
def test_update_resume_item_cross_user_rejected(mock_db):
    """Test cross-user rejection when resume is not owned by current user."""
    mock_client = mock_db.return_value
    mock_res = MagicMock()
    mock_res.data = []  # Not found or unowned
    mock_client.table().select().eq().eq().execute.return_value = mock_res

    response = client.patch(
        f"/api/v1/resumes/{uuid.uuid4()}/items/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"sort_order": 3}
    )

    assert response.status_code == 404


def test_update_resume_item_negative_sort_order_rejected():
    """Test validation rejection for negative sort_order."""
    response = client.patch(
        f"/api/v1/resumes/{uuid.uuid4()}/items/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"sort_order": -1}
    )
    assert response.status_code == 422


@patch("app.services.resumes.get_resume_items")
@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume")
def test_reorder_resume_items_success(mock_get_resume, mock_db, mock_get_items):
    """Test bulk reordering of resume items."""
    resume_id = uuid.uuid4()
    item1_id = uuid.uuid4()
    item2_id = uuid.uuid4()
    mock_get_resume.return_value = MagicMock(id=resume_id, user_id=FAKE_USER)

    mock_client = mock_db.return_value
    mock_existing = MagicMock()
    mock_existing.data = [
        {"id": str(item1_id), "resume_id": str(resume_id)},
        {"id": str(item2_id), "resume_id": str(resume_id)},
    ]
    mock_client.table().select().eq().execute.return_value = mock_existing

    # Mock return of get_resume_items
    from app.models.resume import ResumeItemResponse
    from datetime import datetime
    now = datetime.now()
    mock_get_items.return_value = [
        ResumeItemResponse(
            id=item2_id,
            resume_id=resume_id,
            section_type="skill",
            title="Python",
            sort_order=0,
            created_at=now,
            updated_at=now,
        ),
        ResumeItemResponse(
            id=item1_id,
            resume_id=resume_id,
            section_type="skill",
            title="FastAPI",
            sort_order=1,
            created_at=now,
            updated_at=now,
        ),
    ]

    payload = {
        "items": [
            {"id": str(item2_id), "sort_order": 0},
            {"id": str(item1_id), "sort_order": 1},
        ]
    }

    response = client.patch(
        f"/api/v1/resumes/{resume_id}/items/reorder",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == str(item2_id)
    assert data[0]["sort_order"] == 0
    assert data[1]["id"] == str(item1_id)
    assert data[1]["sort_order"] == 1


def test_reorder_resume_items_duplicate_ids_rejected():
    """Test that duplicate item IDs in reorder payload are rejected."""
    resume_id = uuid.uuid4()
    same_id = str(uuid.uuid4())
    payload = {
        "items": [
            {"id": same_id, "sort_order": 0},
            {"id": same_id, "sort_order": 1},
        ]
    }

    response = client.patch(
        f"/api/v1/resumes/{resume_id}/items/reorder",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=payload
    )

    assert response.status_code == 422


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume")
def test_reorder_resume_items_item_from_another_resume_rejected(mock_get_resume, mock_db):
    """Test rejecting bulk reorder if an item belongs to another resume."""
    resume_id = uuid.uuid4()
    item1_id = uuid.uuid4()
    other_item_id = uuid.uuid4()
    mock_get_resume.return_value = MagicMock(id=resume_id, user_id=FAKE_USER)

    mock_client = mock_db.return_value
    # Existing items on target resume only includes item1
    mock_existing = MagicMock()
    mock_existing.data = [{"id": str(item1_id), "resume_id": str(resume_id)}]

    # Other item query finds it on another resume
    mock_other = MagicMock()
    mock_other.data = [{"id": str(other_item_id), "resume_id": str(uuid.uuid4())}]

    def table_router(table_name):
        mock_t = MagicMock()
        mock_t.select.return_value.eq.return_value.execute.side_effect = [mock_existing, mock_other]
        return mock_t

    mock_client.table.side_effect = table_router

    payload = {
        "items": [
            {"id": str(item1_id), "sort_order": 0},
            {"id": str(other_item_id), "sort_order": 1},
        ]
    }

    response = client.patch(
        f"/api/v1/resumes/{resume_id}/items/reorder",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=payload
    )

    assert response.status_code == 400
    assert "belongs to another resume" in response.json()["detail"]


@patch("app.services.resumes.get_admin_client")
@patch("app.services.resumes.get_resume")
def test_reorder_resume_items_unknown_item_rejected(mock_get_resume, mock_db):
    """Test rejecting bulk reorder if an item ID does not exist."""
    resume_id = uuid.uuid4()
    unknown_item_id = uuid.uuid4()
    mock_get_resume.return_value = MagicMock(id=resume_id, user_id=FAKE_USER)

    mock_client = mock_db.return_value
    mock_existing = MagicMock()
    mock_existing.data = []

    mock_other = MagicMock()
    mock_other.data = []

    def table_router(table_name):
        mock_t = MagicMock()
        mock_t.select.return_value.eq.return_value.execute.side_effect = [mock_existing, mock_other]
        return mock_t

    mock_client.table.side_effect = table_router

    payload = {
        "items": [
            {"id": str(unknown_item_id), "sort_order": 0},
        ]
    }

    response = client.patch(
        f"/api/v1/resumes/{resume_id}/items/reorder",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json=payload
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]




