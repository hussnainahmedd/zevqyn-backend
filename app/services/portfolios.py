"""Service for managing portfolios, portfolio projects, and public serialization."""

from __future__ import annotations

from uuid import UUID
from fastapi import HTTPException

from app.core.supabase import get_admin_client
from app.models.portfolio import (
    PortfolioCreate, PortfolioUpdate, PortfolioResponse,
    PortfolioProjectCreate, PortfolioProjectResponse,
    PublicPortfolioResponse, PublicPortfolioProject
)
from app.services.projects import get_project


# ==============================================================================
# PORTFOLIO CRUD
# ==============================================================================
def create_portfolio(user_id: UUID, portfolio: PortfolioCreate) -> PortfolioResponse:
    client = get_admin_client()
    data = portfolio.model_dump(exclude_unset=True)
    data["user_id"] = str(user_id)
    
    # Check if slug is taken globally (slug must be unique)
    existing = client.table("portfolios").select("id").eq("slug", data["slug"]).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Slug is already in use")
        
    try:
        res = client.table("portfolios").insert(data).execute()
        return PortfolioResponse(**res.data[0])
    except Exception as e:
        err = str(e).lower()
        if "23505" in err or "duplicate key" in err or "unique constraint" in err:
            raise HTTPException(status_code=409, detail="Slug is already in use")
        raise HTTPException(status_code=500, detail="Failed to create portfolio")

def get_portfolios(user_id: UUID) -> list[PortfolioResponse]:
    client = get_admin_client()
    try:
        res = client.table("portfolios").select("*").eq("user_id", str(user_id)).execute()
        return [PortfolioResponse(**r) for r in res.data]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list portfolios")

def get_portfolio(user_id: UUID, portfolio_id: UUID) -> PortfolioResponse:
    client = get_admin_client()
    try:
        res = client.table("portfolios").select("*").eq("id", str(portfolio_id)).eq("user_id", str(user_id)).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return PortfolioResponse(**res.data[0])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio")

def update_portfolio(user_id: UUID, portfolio_id: UUID, portfolio: PortfolioUpdate) -> PortfolioResponse:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    data = portfolio.model_dump(exclude_unset=True)
    if not data:
        return get_portfolio(user_id, portfolio_id)
        
    if "slug" in data:
        # Check slug uniqueness excluding self
        existing = client.table("portfolios").select("id").eq("slug", data["slug"]).neq("id", str(portfolio_id)).execute()
        if existing.data:
            raise HTTPException(status_code=409, detail="Slug is already in use")
            
    try:
        res = client.table("portfolios").update(data).eq("id", str(portfolio_id)).eq("user_id", str(user_id)).execute()
        return PortfolioResponse(**res.data[0])
    except Exception as e:
        err = str(e).lower()
        if "23505" in err or "duplicate key" in err or "unique constraint" in err:
            raise HTTPException(status_code=409, detail="Slug is already in use")
        raise HTTPException(status_code=500, detail="Failed to update portfolio")

def delete_portfolio(user_id: UUID, portfolio_id: UUID) -> dict:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        client.table("portfolios").delete().eq("id", str(portfolio_id)).eq("user_id", str(user_id)).execute()
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete portfolio")


# ==============================================================================
# PORTFOLIO PROJECTS
# ==============================================================================
def add_portfolio_project(user_id: UUID, portfolio_id: UUID, item: PortfolioProjectCreate) -> PortfolioProjectResponse:
    # 1. Verify portfolio ownership
    get_portfolio(user_id, portfolio_id)
    
    # 2. Verify project ownership
    try:
        get_project(user_id, item.project_id)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Not authorized to attach this project")
        
    client = get_admin_client()
    
    # Check for duplicates safely
    res = client.table("portfolio_projects").select("*").eq("portfolio_id", str(portfolio_id)).eq("project_id", str(item.project_id)).execute()
    if res.data:
        raise HTTPException(status_code=400, detail="Project already in portfolio")
        
    insert_data = {
        "portfolio_id": str(portfolio_id),
        "project_id": str(item.project_id),
        "sort_order": item.sort_order if item.sort_order is not None else 0
    }
    
    try:
        inserted = client.table("portfolio_projects").insert(insert_data).execute()
        return PortfolioProjectResponse(**inserted.data[0])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to add project to portfolio")

def get_portfolio_projects(user_id: UUID, portfolio_id: UUID) -> list[PortfolioProjectResponse]:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        res = client.table("portfolio_projects").select("*").eq("portfolio_id", str(portfolio_id)).order("sort_order").execute()
        return [PortfolioProjectResponse(**r) for r in res.data]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list portfolio projects")

def remove_portfolio_project(user_id: UUID, portfolio_id: UUID, project_id: UUID) -> dict:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        client.table("portfolio_projects").delete().eq("portfolio_id", str(portfolio_id)).eq("project_id", str(project_id)).execute()
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to remove portfolio project")


# ==============================================================================
# PUBLIC PORTFOLIO
# ==============================================================================
def get_public_portfolio(slug: str) -> PublicPortfolioResponse:
    """Safe public endpoint. Enforces `is_published` implicitly."""
    client = get_admin_client()
    
    # 1. Fetch portfolio via admin client (bypasses RLS)
    port_res = client.table("portfolios").select("*").eq("slug", slug).execute()
    if not port_res.data:
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    portfolio = port_res.data[0]
    
    # 2. Enforce visibility explicitly
    if not portfolio.get("is_published"):
        # Act like it doesn't exist to prevent enumeration
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    # 3. Fetch linked projects
    portfolio_id = portfolio["id"]
    proj_res = client.table("portfolio_projects").select("project_id").eq("portfolio_id", portfolio_id).order("sort_order").execute()
    
    public_projects = []
    if proj_res.data:
        project_ids = [p["project_id"] for p in proj_res.data]
        # Fetch the actual projects
        # Note: `.in_` filter in Supabase:
        real_projs = client.table("projects").select("*").in_("id", project_ids).execute()
        
        # We need to preserve the sort order
        projs_dict = {p["id"]: p for p in real_projs.data}
        for p_id in project_ids:
            if p_id in projs_dict:
                rp = projs_dict[p_id]
                # Map only safe public fields
                public_projects.append(PublicPortfolioProject(
                    title=rp["title"],
                    short_description=rp["short_description"],
                    description=rp["description"],
                    technologies=rp.get("technologies") or [],
                    skills=rp.get("skills") or [],
                    github_url=rp.get("github_url"),
                    live_url=rp.get("live_url"),
                    image_url=rp.get("image_url")
                ))
                
    # Map portfolio data safely
    return PublicPortfolioResponse(
        slug=portfolio["slug"],
        display_name=portfolio["display_name"],
        headline=portfolio.get("headline"),
        about=portfolio.get("about"),
        profile_image_url=portfolio.get("profile_image_url"),
        theme=portfolio["theme"],
        github_url=portfolio.get("github_url") if portfolio.get("show_contact") else None,
        linkedin_url=portfolio.get("linkedin_url") if portfolio.get("show_contact") else None,
        website_url=portfolio.get("website_url") if portfolio.get("show_contact") else None,
        projects=public_projects
    )
