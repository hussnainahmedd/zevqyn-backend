"""API routes for Portfolios."""

from uuid import UUID
from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.portfolio import (
    PortfolioCreate, PortfolioUpdate, PortfolioResponse,
    PortfolioProjectCreate, PortfolioProjectResponse,
    PortfolioSkillCreate, PortfolioSkillResponse,
    PortfolioEducationCreate, PortfolioEducationResponse,
    PortfolioCertificateCreate, PortfolioCertificateResponse,
    PublicPortfolioResponse
)
from app.services import portfolios as portfolio_service

router = APIRouter(prefix="/api/v1", tags=["portfolios"])

# ==============================================================================
# AUTHENTICATED PORTFOLIO CRUD
# ==============================================================================
@router.post("/portfolios", response_model=PortfolioResponse)
async def create_portfolio(portfolio: PortfolioCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.create_portfolio(user.id, portfolio)

@router.get("/portfolios", response_model=list[PortfolioResponse])
async def list_portfolios(user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.get_portfolios(user.id)

@router.get("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(portfolio_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.get_portfolio(user.id, portfolio_id)

@router.patch("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(portfolio_id: UUID, portfolio: PortfolioUpdate, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.update_portfolio(user.id, portfolio_id, portfolio)

@router.delete("/portfolios/{portfolio_id}")
async def delete_portfolio(portfolio_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.delete_portfolio(user.id, portfolio_id)


# ==============================================================================
# PORTFOLIO PROJECTS
# ==============================================================================
@router.post("/portfolios/{portfolio_id}/projects", response_model=PortfolioProjectResponse)
async def add_portfolio_project(portfolio_id: UUID, item: PortfolioProjectCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.add_portfolio_project(user.id, portfolio_id, item)

@router.get("/portfolios/{portfolio_id}/projects", response_model=list[PortfolioProjectResponse])
async def list_portfolio_projects(portfolio_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.get_portfolio_projects(user.id, portfolio_id)

@router.delete("/portfolios/{portfolio_id}/projects/{project_id}")
async def remove_portfolio_project(portfolio_id: UUID, project_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.remove_portfolio_project(user.id, portfolio_id, project_id)


# ==============================================================================
# PORTFOLIO SKILLS
# ==============================================================================
@router.post("/portfolios/{portfolio_id}/skills", response_model=PortfolioSkillResponse)
async def add_portfolio_skill(portfolio_id: UUID, item: PortfolioSkillCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.add_portfolio_skill(user.id, portfolio_id, item)

@router.get("/portfolios/{portfolio_id}/skills", response_model=list[PortfolioSkillResponse])
async def list_portfolio_skills(portfolio_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.get_portfolio_skills(user.id, portfolio_id)

@router.delete("/portfolios/{portfolio_id}/skills/{skill_id}")
async def remove_portfolio_skill(portfolio_id: UUID, skill_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.remove_portfolio_skill(user.id, portfolio_id, skill_id)


# ==============================================================================
# PORTFOLIO EDUCATION
# ==============================================================================
@router.post("/portfolios/{portfolio_id}/education", response_model=PortfolioEducationResponse)
async def add_portfolio_education(portfolio_id: UUID, item: PortfolioEducationCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.add_portfolio_education(user.id, portfolio_id, item)

@router.get("/portfolios/{portfolio_id}/education", response_model=list[PortfolioEducationResponse])
async def list_portfolio_education(portfolio_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.get_portfolio_education(user.id, portfolio_id)

@router.delete("/portfolios/{portfolio_id}/education/{education_id}")
async def remove_portfolio_education(portfolio_id: UUID, education_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.remove_portfolio_education(user.id, portfolio_id, education_id)


# ==============================================================================
# PORTFOLIO CERTIFICATES
# ==============================================================================
@router.post("/portfolios/{portfolio_id}/certificates", response_model=PortfolioCertificateResponse)
async def add_portfolio_certificate(portfolio_id: UUID, item: PortfolioCertificateCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.add_portfolio_certificate(user.id, portfolio_id, item)

@router.get("/portfolios/{portfolio_id}/certificates", response_model=list[PortfolioCertificateResponse])
async def list_portfolio_certificates(portfolio_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.get_portfolio_certificates(user.id, portfolio_id)

@router.delete("/portfolios/{portfolio_id}/certificates/{certificate_id}")
async def remove_portfolio_certificate(portfolio_id: UUID, certificate_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return portfolio_service.remove_portfolio_certificate(user.id, portfolio_id, certificate_id)


# ==============================================================================
# PUBLIC ENDPOINTS
# ==============================================================================
@router.get("/public/portfolios/{slug}", response_model=PublicPortfolioResponse)
async def get_public_portfolio(slug: str):
    """Anonymous public route. Resolves slugs to published portfolios safely."""
    return portfolio_service.get_public_portfolio(slug)
