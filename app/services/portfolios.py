"""Service for managing portfolios, portfolio projects, and public serialization."""

from __future__ import annotations

from uuid import UUID
from fastapi import HTTPException

from app.core.supabase import get_admin_client
from app.models.portfolio import (
    PortfolioCreate, PortfolioUpdate, PortfolioResponse,
    PortfolioProjectCreate, PortfolioProjectResponse,
    PortfolioSkillCreate, PortfolioSkillResponse,
    PortfolioEducationCreate, PortfolioEducationResponse,
    PortfolioCertificateCreate, PortfolioCertificateResponse,
    PublicPortfolioResponse, PublicPortfolioProject,
    PublicPortfolioSkill, PublicPortfolioEducation, PublicPortfolioCertificate
)
from app.services.projects import get_project
from app.services.career import get_skill, get_education, get_certificate


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
# PORTFOLIO SKILLS
# ==============================================================================
def add_portfolio_skill(user_id: UUID, portfolio_id: UUID, item: PortfolioSkillCreate) -> PortfolioSkillResponse:
    get_portfolio(user_id, portfolio_id)
    try:
        get_skill(user_id, item.skill_id)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Not authorized to attach this skill")
        
    client = get_admin_client()
    res = client.table("portfolio_skills").select("*").eq("portfolio_id", str(portfolio_id)).eq("skill_id", str(item.skill_id)).execute()
    if res.data:
        raise HTTPException(status_code=400, detail="Skill already in portfolio")
        
    insert_data = {
        "portfolio_id": str(portfolio_id),
        "skill_id": str(item.skill_id),
        "sort_order": item.sort_order if item.sort_order is not None else 0
    }
    try:
        inserted = client.table("portfolio_skills").insert(insert_data).execute()
        return PortfolioSkillResponse(**inserted.data[0])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to add skill to portfolio")

def get_portfolio_skills(user_id: UUID, portfolio_id: UUID) -> list[PortfolioSkillResponse]:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        res = client.table("portfolio_skills").select("*").eq("portfolio_id", str(portfolio_id)).order("sort_order").execute()
        return [PortfolioSkillResponse(**r) for r in res.data]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list portfolio skills")

def remove_portfolio_skill(user_id: UUID, portfolio_id: UUID, skill_id: UUID) -> dict:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        client.table("portfolio_skills").delete().eq("portfolio_id", str(portfolio_id)).eq("skill_id", str(skill_id)).execute()
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to remove portfolio skill")


# ==============================================================================
# PORTFOLIO EDUCATION
# ==============================================================================
def add_portfolio_education(user_id: UUID, portfolio_id: UUID, item: PortfolioEducationCreate) -> PortfolioEducationResponse:
    get_portfolio(user_id, portfolio_id)
    try:
        get_education(user_id, item.education_id)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Not authorized to attach this education")
        
    client = get_admin_client()
    res = client.table("portfolio_education").select("*").eq("portfolio_id", str(portfolio_id)).eq("education_id", str(item.education_id)).execute()
    if res.data:
        raise HTTPException(status_code=400, detail="Education already in portfolio")
        
    insert_data = {
        "portfolio_id": str(portfolio_id),
        "education_id": str(item.education_id),
        "sort_order": item.sort_order if item.sort_order is not None else 0
    }
    try:
        inserted = client.table("portfolio_education").insert(insert_data).execute()
        return PortfolioEducationResponse(**inserted.data[0])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to add education to portfolio")

def get_portfolio_education(user_id: UUID, portfolio_id: UUID) -> list[PortfolioEducationResponse]:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        res = client.table("portfolio_education").select("*").eq("portfolio_id", str(portfolio_id)).order("sort_order").execute()
        return [PortfolioEducationResponse(**r) for r in res.data]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list portfolio education")

def remove_portfolio_education(user_id: UUID, portfolio_id: UUID, education_id: UUID) -> dict:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        client.table("portfolio_education").delete().eq("portfolio_id", str(portfolio_id)).eq("education_id", str(education_id)).execute()
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to remove portfolio education")


# ==============================================================================
# PORTFOLIO CERTIFICATES
# ==============================================================================
def add_portfolio_certificate(user_id: UUID, portfolio_id: UUID, item: PortfolioCertificateCreate) -> PortfolioCertificateResponse:
    get_portfolio(user_id, portfolio_id)
    try:
        get_certificate(user_id, item.certificate_id)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Not authorized to attach this certificate")
        
    client = get_admin_client()
    res = client.table("portfolio_certificates").select("*").eq("portfolio_id", str(portfolio_id)).eq("certificate_id", str(item.certificate_id)).execute()
    if res.data:
        raise HTTPException(status_code=400, detail="Certificate already in portfolio")
        
    insert_data = {
        "portfolio_id": str(portfolio_id),
        "certificate_id": str(item.certificate_id),
        "sort_order": item.sort_order if item.sort_order is not None else 0
    }
    try:
        inserted = client.table("portfolio_certificates").insert(insert_data).execute()
        return PortfolioCertificateResponse(**inserted.data[0])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to add certificate to portfolio")

def get_portfolio_certificates(user_id: UUID, portfolio_id: UUID) -> list[PortfolioCertificateResponse]:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        res = client.table("portfolio_certificates").select("*").eq("portfolio_id", str(portfolio_id)).order("sort_order").execute()
        return [PortfolioCertificateResponse(**r) for r in res.data]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list portfolio certificates")

def remove_portfolio_certificate(user_id: UUID, portfolio_id: UUID, certificate_id: UUID) -> dict:
    get_portfolio(user_id, portfolio_id)
    client = get_admin_client()
    try:
        client.table("portfolio_certificates").delete().eq("portfolio_id", str(portfolio_id)).eq("certificate_id", str(certificate_id)).execute()
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to remove portfolio certificate")


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
        real_projs = client.table("projects").select("*").in_("id", project_ids).execute()
        
        # Preserve sort order
        projs_dict = {p["id"]: p for p in real_projs.data}
        for p_id in project_ids:
            if p_id in projs_dict:
                rp = projs_dict[p_id]
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
                
    # 4. Fetch linked skills
    public_skills = []
    try:
        skill_res = client.table("portfolio_skills").select("skill_id").eq("portfolio_id", portfolio_id).order("sort_order").execute()
        if skill_res.data:
            skill_ids = [s["skill_id"] for s in skill_res.data]
            real_skills = client.table("skills").select("*").in_("id", skill_ids).execute()
            skills_dict = {s["id"]: s for s in real_skills.data}
            for s_id in skill_ids:
                if s_id in skills_dict:
                    rs = skills_dict[s_id]
                    public_skills.append(PublicPortfolioSkill(
                        name=rs["name"],
                        category=rs["category"],
                        proficiency=rs["proficiency"]
                    ))
    except Exception:
        public_skills = []

    # 5. Fetch linked education
    public_education = []
    try:
        edu_res = client.table("portfolio_education").select("education_id").eq("portfolio_id", portfolio_id).order("sort_order").execute()
        if edu_res.data:
            edu_ids = [e["education_id"] for e in edu_res.data]
            real_edu = client.table("education").select("*").in_("id", edu_ids).execute()
            edu_dict = {e["id"]: e for e in real_edu.data}
            for e_id in edu_ids:
                if e_id in edu_dict:
                    re = edu_dict[e_id]
                    public_education.append(PublicPortfolioEducation(
                        institution=re["institution"],
                        degree=re["degree"],
                        field_of_study=re["field_of_study"],
                        start_date=re["start_date"],
                        end_date=re.get("end_date"),
                        description=re.get("description")
                    ))
    except Exception:
        public_education = []

    # 6. Fetch linked certificates (strictly respecting show_certificates toggle)
    public_certificates = []
    if portfolio.get("show_certificates"):
        try:
            cert_res = client.table("portfolio_certificates").select("certificate_id").eq("portfolio_id", portfolio_id).order("sort_order").execute()
            if cert_res.data:
                cert_ids = [c["certificate_id"] for c in cert_res.data]
                real_certs = client.table("certificates").select("*").in_("id", cert_ids).execute()
                certs_dict = {c["id"]: c for c in real_certs.data}
                for c_id in cert_ids:
                    if c_id in certs_dict:
                        rc = certs_dict[c_id]
                        public_certificates.append(PublicPortfolioCertificate(
                            title=rc["title"],
                            issuer=rc["issuer"],
                            issue_date=rc["issue_date"],
                            expiry_date=rc.get("expiry_date"),
                            credential_id=rc.get("credential_id"),
                            credential_url=rc.get("credential_url"),
                            description=rc.get("description")
                        ))
        except Exception:
            public_certificates = []

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
        projects=public_projects,
        skills=public_skills,
        education=public_education,
        certificates=public_certificates
    )
