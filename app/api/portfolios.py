"""API routes for Portfolios."""

from uuid import UUID
from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.portfolio import (
    PortfolioCreate, PortfolioUpdate, PortfolioResponse,
    PortfolioProjectCreate, PortfolioProjectResponse,
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
# PUBLIC ENDPOINTS
# ==============================================================================
@router.get("/public/portfolios/{slug}", response_model=PublicPortfolioResponse)
async def get_public_portfolio(slug: str):
    """Anonymous public route. Resolves slugs to published portfolios safely."""
    return portfolio_service.get_public_portfolio(slug)
