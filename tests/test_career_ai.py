"""Tests for Career AI Phase 1 endpoints."""

import json
import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app

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


# ==============================================================================
# AUTHENTICATION ENFORCEMENT
# ==============================================================================
@pytest.mark.parametrize(
    "endpoint,method,payload",
    [
        ("/api/v1/career/ai/analyze", "post", None),
        ("/api/v1/career/ai/skill-gap", "post", {"target_role": "Backend Engineer"}),
        ("/api/v1/career/ai/suggest-projects", "post", {"count": 3}),
        ("/api/v1/career/ai/review-resume", "post", {"resume_id": str(uuid.uuid4())}),
        ("/api/v1/career/ai/review-portfolio", "post", {"portfolio_id": str(uuid.uuid4())}),
        ("/api/v1/career/ai/action-plan", "post", {"target_role": "Cloud Architect"}),
    ],
)
def test_career_ai_requires_auth(endpoint, method, payload):
    with patch("app.core.auth.get_admin_client") as mock_get:
        # Simulate invalid/missing credentials
        mock_get.return_value.auth.get_user.side_effect = Exception("No auth")
        resp = client.request(method, endpoint, json=payload)
        assert resp.status_code in (401, 403)


# ==============================================================================
# A. CAREER PROFILE ANALYSIS
# ==============================================================================
@patch("app.services.career_ai._get_genai_client")
@patch("app.services.career_ai.get_projects")
@patch("app.services.career_ai.get_skills")
@patch("app.services.career_ai.get_educations")
@patch("app.services.career_ai.get_certificates")
@patch("app.services.career_ai.get_resumes")
@patch("app.services.career_ai.get_portfolios")
@patch("app.services.career_ai.get_profile")
def test_career_analysis_success(
    mock_profile, mock_ports, mock_resumes, mock_certs, mock_edu, mock_skills, mock_projs, mock_ai
):
    prof = MagicMock()
    prof.full_name = "Alice Developer"
    prof.bio = "Full stack engineer with Python experience"
    prof.location = "Remote"
    prof.website = "https://alice.dev"
    prof.github_url = "https://github.com/alice"
    prof.linkedin_url = "https://linkedin.com/in/alice"
    mock_profile.return_value = prof

    proj = MagicMock()
    proj.title = "E-Commerce API"
    proj.short_description = "FastAPI store"
    proj.description = "Built with FastAPI and PostgreSQL"
    proj.technologies = ["Python", "FastAPI"]
    proj.skills = ["API Design"]
    proj.featured = True
    mock_projs.return_value = [proj]

    sk1 = MagicMock()
    sk1.name = "Python"
    sk1.category = "Language"
    sk1.proficiency = 5

    sk2 = MagicMock()
    sk2.name = "Docker"
    sk2.category = "DevOps"
    sk2.proficiency = 4
    mock_skills.return_value = [sk1, sk2]

    mock_edu.return_value = []
    mock_certs.return_value = []

    res = MagicMock()
    res.name = "Standard Resume"
    res.professional_title = "Senior Dev"
    res.professional_summary = "Experienced dev"
    mock_resumes.return_value = [res]
    mock_ports.return_value = []

    mock_gemini_res = MagicMock()
    mock_gemini_res.text = json.dumps({
        "readiness_score": 78,
        "summary": "Strong foundational backend skills with well-documented projects.",
        "strengths": ["Clear API architecture experience", "Strong Python proficiency", "Active resume"],
        "improvement_areas": ["Needs cloud certifications", "Portfolio is not yet created"],
        "next_actions": ["Create a portfolio", "Deploy e-commerce API to AWS", "Add CI/CD pipeline"],
    })
    mock_ai.return_value.models.generate_content.return_value = mock_gemini_res

    resp = client.post(
        "/api/v1/career/ai/analyze",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["readiness_score"] == 78
    assert len(data["strengths"]) == 3
    assert len(data["improvement_areas"]) == 2
    assert len(data["next_actions"]) == 3
    assert data["profile_stats"] == {
        "projects": 1,
        "skills": 2,
        "education": 0,
        "certificates": 0,
        "resumes": 1,
        "portfolios": 0,
    }


# ==============================================================================
# B. SKILL GAP ANALYSIS
# ==============================================================================
@patch("app.services.career_ai._get_genai_client")
def test_skill_gap_success(mock_ai):
    mock_gemini_res = MagicMock()
    mock_gemini_res.text = json.dumps({
        "current_strengths": ["Python", "FastAPI", "SQL"],
        "skill_gaps": [
            {
                "skill": "Kubernetes",
                "reason": "Required for microservice orchestration in target role.",
                "priority": "High",
                "suggested_action": "Complete CKAD certification course and deploy minikube cluster.",
            },
            {
                "skill": "gRPC",
                "reason": "Needed for low-latency inter-service RPCs.",
                "priority": "Medium",
                "suggested_action": "Implement protobuf schemas in a side project.",
            },
        ],
        "recommended_learning": ["Kubernetes documentation", "gRPC with Python guide"],
        "recommended_projects": ["Distributed microservices cluster with Kubernetes"],
    })
    mock_ai.return_value.models.generate_content.return_value = mock_gemini_res

    resp = client.post(
        "/api/v1/career/ai/skill-gap",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"target_role": "Senior Cloud Infrastructure Engineer"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["target_role"] == "Senior Cloud Infrastructure Engineer"
    assert "Kubernetes" in data["skill_gaps"][0]["skill"]
    assert data["skill_gaps"][0]["priority"] == "High"
    assert len(data["recommended_projects"]) == 1


def test_skill_gap_validation():
    # Target role too short
    resp = client.post(
        "/api/v1/career/ai/skill-gap",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"target_role": "A"},
    )
    assert resp.status_code == 422

    # Extra fields forbidden
    resp = client.post(
        "/api/v1/career/ai/skill-gap",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"target_role": "DevOps", "hacked_field": 123},
    )
    assert resp.status_code == 422


# ==============================================================================
# C. PROJECT SUGGESTIONS
# ==============================================================================
@patch("app.services.career_ai._get_genai_client")
def test_project_suggestions_success(mock_ai):
    mock_gemini_res = MagicMock()
    mock_gemini_res.text = json.dumps({
        "suggestions": [
            {
                "title": "Real-Time Event Streaming Platform",
                "description": "Kafka-based ingestion engine with FastAPI consumer services.",
                "why_it_fits": "Proves distributed streaming capabilities.",
                "suggested_features": ["Event producer", "Dead-letter queue", "Metrics dashboard"],
                "technologies": ["Python", "FastAPI", "Apache Kafka", "Docker"],
                "skills_developed": ["Message queue architecture", "Event-driven design"],
                "difficulty": "Intermediate",
            }
        ]
    })
    mock_ai.return_value.models.generate_content.return_value = mock_gemini_res

    resp = client.post(
        "/api/v1/career/ai/suggest-projects",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"target_role": "Data Engineer", "count": 1},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["target_role"] == "Data Engineer"
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["title"] == "Real-Time Event Streaming Platform"
    assert data["suggestions"][0]["difficulty"] == "Intermediate"


def test_project_suggestions_validation():
    # Count > 5
    resp = client.post(
        "/api/v1/career/ai/suggest-projects",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"count": 10},
    )
    assert resp.status_code == 422

    # Count < 1
    resp = client.post(
        "/api/v1/career/ai/suggest-projects",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"count": 0},
    )
    assert resp.status_code == 422


# ==============================================================================
# D. RESUME REVIEW
# ==============================================================================
@patch("app.services.career_ai.get_resume")
@patch("app.services.career_ai.get_resume_items")
@patch("app.services.career_ai._get_genai_client")
def test_review_resume_success(mock_ai, mock_items, mock_resume):
    resume_id = uuid.uuid4()
    res = MagicMock()
    res.id = resume_id
    res.name = "Tech Resume"
    res.professional_title = "Backend Developer"
    res.professional_summary = "Experienced in microservices"
    res.location = "Islamabad, Pakistan"
    res.email = "test@example.com"
    res.phone = "+923000000000"
    res.linkedin_url = "https://linkedin.com"
    res.github_url = "https://github.com"
    res.portfolio_url = "https://portfolio.com"
    mock_resume.return_value = res

    item = MagicMock()
    item.section_type = "experience"
    item.title = "Software Engineer"
    item.subtitle = "Tech Corp"
    item.description = "Built scalable microservices handling 10k RPS"
    mock_items.return_value = [item]

    mock_gemini_res = MagicMock()
    mock_gemini_res.text = json.dumps({
        "score": 85,
        "summary": "Strong technical accomplishments with clear quantifiable results.",
        "strengths": ["Quantified 10k RPS metric", "Clear professional title"],
        "improvements": ["Add more action verbs in earlier experience"],
        "ats_suggestions": ["Ensure standard section headings like Experience and Education"],
        "content_suggestions": ["Mention specific database optimization techniques"],
        "missing_elements": ["Certifications section"],
    })
    mock_ai.return_value.models.generate_content.return_value = mock_gemini_res

    resp = client.post(
        "/api/v1/career/ai/review-resume",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"resume_id": str(resume_id)},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["resume_id"] == str(resume_id)
    assert data["score"] == 85
    assert len(data["strengths"]) == 2
    assert "Certifications section" in data["missing_elements"]


@patch("app.services.career_ai.get_resume")
def test_review_resume_not_found(mock_resume):
    from fastapi import HTTPException
    mock_resume.side_effect = HTTPException(status_code=404, detail="Resume not found")

    resp = client.post(
        "/api/v1/career/ai/review-resume",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"resume_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


# ==============================================================================
# E. PORTFOLIO REVIEW
# ==============================================================================
@patch("app.services.career_ai.get_portfolio")
@patch("app.services.career_ai.get_portfolio_projects")
@patch("app.services.career_ai.get_portfolio_skills")
@patch("app.services.career_ai.get_portfolio_education")
@patch("app.services.career_ai.get_portfolio_certificates")
@patch("app.services.career_ai._get_genai_client")
def test_review_portfolio_success(
    mock_ai, mock_certs, mock_edu, mock_skills, mock_projs, mock_portfolio
):
    port_id = uuid.uuid4()
    mock_portfolio.return_value = MagicMock(
        id=port_id,
        slug="hussnain-portfolio",
        display_name="Hussnain Ahmad",
        headline="AI & Backend Systems Engineer",
        about="Passionate engineer building autonomous software.",
        theme="modern",
        is_published=True,
        show_contact=True,
        show_certificates=True,
    )
    mock_projs.return_value = [MagicMock()]
    mock_skills.return_value = [MagicMock(), MagicMock()]
    mock_edu.return_value = []
    mock_certs.return_value = []

    mock_gemini_res = MagicMock()
    mock_gemini_res.text = json.dumps({
        "score": 82,
        "summary": "Engaging headline and clean modern theme setup.",
        "strengths": ["Focused headline", "Published status with visible contact"],
        "improvements": ["Attach more featured projects", "Add education record"],
        "presentation_suggestions": ["Include a high-level architecture diagram in project descriptions"],
        "missing_elements": ["Education section", "Certificates"],
    })
    mock_ai.return_value.models.generate_content.return_value = mock_gemini_res

    resp = client.post(
        "/api/v1/career/ai/review-portfolio",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"portfolio_id": str(port_id)},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["portfolio_id"] == str(port_id)
    assert data["score"] == 82
    assert "Engaging headline" in data["summary"]
    assert len(data["presentation_suggestions"]) == 1


@patch("app.services.career_ai.get_portfolio")
def test_review_portfolio_not_found(mock_portfolio):
    from fastapi import HTTPException
    mock_portfolio.side_effect = HTTPException(status_code=404, detail="Portfolio not found")

    resp = client.post(
        "/api/v1/career/ai/review-portfolio",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"portfolio_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


# ==============================================================================
# F. ACTION PLAN
# ==============================================================================
@patch("app.services.career_ai._get_genai_client")
def test_action_plan_success(mock_ai):
    mock_gemini_res = MagicMock()
    mock_gemini_res.text = json.dumps({
        "summary": "3-month roadmap to transition to Senior Backend Engineer.",
        "days_30": [
            {
                "title": "Master Async Python & FastAPI Internals",
                "description": "Build an event-loop benchmark suite.",
                "category": "Skills",
                "priority": "High",
            }
        ],
        "days_60": [
            {
                "title": "Ship High-Throughput Microservice",
                "description": "Design and publish an open source gRPC gateway.",
                "category": "Projects",
                "priority": "High",
            }
        ],
        "days_90": [
            {
                "title": "ATS Resume Polish and Targeted Applications",
                "description": "Update ZEVQYN resume with metrics and apply to 15 tier-1 companies.",
                "category": "Resume",
                "priority": "Medium",
            }
        ],
    })
    mock_ai.return_value.models.generate_content.return_value = mock_gemini_res

    resp = client.post(
        "/api/v1/career/ai/action-plan",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"target_role": "Senior Backend Engineer"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["target_role"] == "Senior Backend Engineer"
    assert len(data["days_30"]) == 1
    assert data["days_30"][0]["category"] == "Skills"
    assert len(data["days_60"]) == 1
    assert len(data["days_90"]) == 1


# ==============================================================================
# G. ERROR HANDLING (502 BAD GATEWAY / 500 PARSE ERROR)
# ==============================================================================
@patch("app.services.career_ai._get_genai_client")
def test_gemini_failure_returns_502(mock_ai):
    mock_ai.return_value.models.generate_content.side_effect = RuntimeError("GenAI connection timeout")

    resp = client.post(
        "/api/v1/career/ai/action-plan",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"target_role": "Backend Engineer"},
    )
    assert resp.status_code == 502
    assert "AI generation service temporarily unavailable" in resp.json()["detail"]


@patch("app.services.career_ai._get_genai_client")
def test_gemini_invalid_json_returns_500(mock_ai):
    mock_res = MagicMock()
    mock_res.text = "NOT JSON CONTENT"
    mock_ai.return_value.models.generate_content.return_value = mock_res

    resp = client.post(
        "/api/v1/career/ai/action-plan",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        json={"target_role": "Backend Engineer"},
    )
    assert resp.status_code == 500
    assert "Failed to parse structured response from AI" in resp.json()["detail"]
