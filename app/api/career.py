"""API routes for career profile."""

from uuid import UUID
from fastapi import APIRouter, Depends

from typing import Optional

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.career import (
    SkillCreate, SkillUpdate, SkillResponse,
    EducationCreate, EducationUpdate, EducationResponse,
    CertificateCreate, CertificateUpdate, CertificateResponse,
    CareerAssistantRequest, CareerAssistantResponse
)
from app.models.career_ai import (
    CareerAnalysisResponse,
    SkillGapRequest,
    SkillGapResponse,
    ProjectSuggestionsRequest,
    ProjectSuggestionsResponse,
    ResumeReviewRequest,
    ResumeReviewResponse,
    PortfolioReviewRequest,
    PortfolioReviewResponse,
    ActionPlanRequest,
    ActionPlanResponse,
)
from app.services import career as career_service
from app.services import career_ai as career_ai_service

router = APIRouter(prefix="/api/v1/career", tags=["career"])

# ==============================================================================
# SKILLS
# ==============================================================================
@router.post("/skills", response_model=SkillResponse)
async def create_skill(skill: SkillCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.create_skill(user.id, skill)

@router.get("/skills", response_model=list[SkillResponse])
async def list_skills(user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.get_skills(user.id)

@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.get_skill(user.id, skill_id)

@router.patch("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(skill_id: UUID, skill: SkillUpdate, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.update_skill(user.id, skill_id, skill)

@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.delete_skill(user.id, skill_id)


# ==============================================================================
# EDUCATION
# ==============================================================================
@router.post("/education", response_model=EducationResponse)
async def create_education(edu: EducationCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.create_education(user.id, edu)

@router.get("/education", response_model=list[EducationResponse])
async def list_education(user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.get_educations(user.id)

@router.get("/education/{edu_id}", response_model=EducationResponse)
async def get_education(edu_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.get_education(user.id, edu_id)

@router.patch("/education/{edu_id}", response_model=EducationResponse)
async def update_education(edu_id: UUID, edu: EducationUpdate, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.update_education(user.id, edu_id, edu)

@router.delete("/education/{edu_id}")
async def delete_education(edu_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.delete_education(user.id, edu_id)


# ==============================================================================
# CERTIFICATES
# ==============================================================================
@router.post("/certificates", response_model=CertificateResponse)
async def create_certificate(cert: CertificateCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.create_certificate(user.id, cert)

@router.get("/certificates", response_model=list[CertificateResponse])
async def list_certificates(user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.get_certificates(user.id)

@router.get("/certificates/{cert_id}", response_model=CertificateResponse)
async def get_certificate(cert_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.get_certificate(user.id, cert_id)

@router.patch("/certificates/{cert_id}", response_model=CertificateResponse)
async def update_certificate(cert_id: UUID, cert: CertificateUpdate, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.update_certificate(user.id, cert_id, cert)

@router.delete("/certificates/{cert_id}")
async def delete_certificate(cert_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return career_service.delete_certificate(user.id, cert_id)


# ==============================================================================
# CAREER AI ASSISTANT
# ==============================================================================
@router.post("/assistant", response_model=CareerAssistantResponse)
async def ask_career_assistant(request: CareerAssistantRequest, user: AuthenticatedUser = Depends(get_current_user)):
    """Ask the career AI a grounded question about the user profile."""
    return career_service.ask_career_assistant(user.id, request.message)


# ==============================================================================
# CAREER AI (PHASE 1)
# ==============================================================================
@router.post("/ai/analyze", response_model=CareerAnalysisResponse)
async def analyze_career(user: AuthenticatedUser = Depends(get_current_user)):
    """Analyze the authenticated user's complete career profile and readiness."""
    return career_ai_service.analyze_career_profile(user.id)


@router.post("/ai/skill-gap", response_model=SkillGapResponse)
async def skill_gap_analysis(
    request: SkillGapRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Analyze skill gaps against a specified target role."""
    return career_ai_service.analyze_skill_gap(user.id, request)


@router.post("/ai/suggest-projects", response_model=ProjectSuggestionsResponse)
async def suggest_career_projects(
    request: Optional[ProjectSuggestionsRequest] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Recommend personalized portfolio project ideas bridging skill gaps."""
    req = request or ProjectSuggestionsRequest()
    return career_ai_service.suggest_projects(user.id, req)


@router.post("/ai/review-resume", response_model=ResumeReviewResponse)
async def review_user_resume(
    request: ResumeReviewRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Evaluate a user's resume for content, impact, and ATS optimization."""
    return career_ai_service.review_resume(user.id, request)


@router.post("/ai/review-portfolio", response_model=PortfolioReviewResponse)
async def review_user_portfolio(
    request: PortfolioReviewRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Review a user's portfolio showcase, headline, and attached items."""
    return career_ai_service.review_portfolio(user.id, request)


@router.post("/ai/action-plan", response_model=ActionPlanResponse)
async def career_action_plan(
    request: ActionPlanRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Generate a structured 30/60/90-day career roadmap towards target role."""
    return career_ai_service.generate_action_plan(user.id, request)

