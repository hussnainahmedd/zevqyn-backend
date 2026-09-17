"""Service for managing resumes, resume items, and PDF export."""

from __future__ import annotations

import io
from typing import Any
from uuid import UUID
from fastapi import HTTPException
from fastapi.responses import Response
from fpdf import FPDF

from app.core.supabase import get_admin_client
from app.models.resume import (
    ResumeCreate, ResumeUpdate, ResumeResponse,
    ResumeItemCreate, ResumeItemUpdate, ResumeItemResponse
)
from app.services.projects import get_project
from app.services.career import get_skill, get_education, get_certificate


# ==============================================================================
# RESUME CRUD
# ==============================================================================
def create_resume(user_id: UUID, resume: ResumeCreate) -> ResumeResponse:
    client = get_admin_client()
    data = resume.model_dump(exclude_unset=True)
    data["user_id"] = str(user_id)
    try:
        res = client.table("resumes").insert(data).execute()
        return ResumeResponse(**res.data[0])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create resume")

def get_resumes(user_id: UUID) -> list[ResumeResponse]:
    client = get_admin_client()
    try:
        res = client.table("resumes").select("*").eq("user_id", str(user_id)).execute()
        return [ResumeResponse(**r) for r in res.data]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list resumes")

def get_resume(user_id: UUID, resume_id: UUID) -> ResumeResponse:
    client = get_admin_client()
    try:
        res = client.table("resumes").select("*").eq("id", str(resume_id)).eq("user_id", str(user_id)).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Resume not found")
        return ResumeResponse(**res.data[0])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch resume")

def update_resume(user_id: UUID, resume_id: UUID, resume: ResumeUpdate) -> ResumeResponse:
    get_resume(user_id, resume_id)
    client = get_admin_client()
    data = resume.model_dump(exclude_unset=True)
    if not data:
        return get_resume(user_id, resume_id)
    try:
        res = client.table("resumes").update(data).eq("id", str(resume_id)).eq("user_id", str(user_id)).execute()
        return ResumeResponse(**res.data[0])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update resume")

def delete_resume(user_id: UUID, resume_id: UUID) -> dict:
    get_resume(user_id, resume_id)
    client = get_admin_client()
    try:
        client.table("resumes").delete().eq("id", str(resume_id)).eq("user_id", str(user_id)).execute()
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete resume")


# ==============================================================================
# RESUME ITEMS
# ==============================================================================
def create_resume_item(user_id: UUID, resume_id: UUID, item: ResumeItemCreate) -> ResumeItemResponse:
    # 1. Verify resume ownership
    get_resume(user_id, resume_id)
    
    # 2. Resolve source item and verify ownership
    title = ""
    subtitle = ""
    description = ""
    
    try:
        if item.section_type == "project":
            proj = get_project(user_id, item.source_id)
            title = proj.title
            subtitle = ", ".join(proj.technologies) if proj.technologies else ""
            description = proj.short_description
        elif item.section_type == "skill":
            skill = get_skill(user_id, item.source_id)
            title = skill.name
            subtitle = skill.category
            description = f"Proficiency: {skill.proficiency}/5"
        elif item.section_type == "education":
            edu = get_education(user_id, item.source_id)
            title = edu.institution
            subtitle = f"{edu.degree} in {edu.field_of_study}"
            description = f"{edu.start_date} - {edu.end_date if edu.end_date else 'Present'}"
            if edu.description:
                description += f" | {edu.description}"
        elif item.section_type == "certificate":
            cert = get_certificate(user_id, item.source_id)
            title = cert.title
            subtitle = cert.issuer
            description = f"Issued: {cert.issue_date}"
            if cert.credential_id:
                description += f" | ID: {cert.credential_id}"
    except HTTPException:
        # Re-raise ownership errors
        raise HTTPException(status_code=403, detail="Not authorized to attach this record")

    client = get_admin_client()
    
    # Check for duplicates safely
    res = client.table("resume_items").select("*").eq("resume_id", str(resume_id)).eq("metadata->>source_id", str(item.source_id)).execute()
    if res.data:
        raise HTTPException(status_code=400, detail="Item already attached to resume")
    
    insert_data = {
        "resume_id": str(resume_id),
        "section_type": item.section_type,
        "title": title,
        "subtitle": subtitle,
        "description": description,
        "metadata": {"source_id": str(item.source_id), "source_type": item.section_type},
        "sort_order": item.sort_order
    }
    
    try:
        inserted = client.table("resume_items").insert(insert_data).execute()
        return ResumeItemResponse(**inserted.data[0])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to add resume item")


def get_resume_items(user_id: UUID, resume_id: UUID) -> list[ResumeItemResponse]:
    get_resume(user_id, resume_id)
    client = get_admin_client()
    try:
        res = client.table("resume_items").select("*").eq("resume_id", str(resume_id)).order("sort_order").execute()
        return [ResumeItemResponse(**r) for r in res.data]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch resume items")

def delete_resume_item(user_id: UUID, resume_id: UUID, item_id: UUID) -> dict:
    get_resume(user_id, resume_id)
    client = get_admin_client()
    
    try:
        # Safely enforce that the item actually belongs to this resume
        res = client.table("resume_items").delete().eq("id", str(item_id)).eq("resume_id", str(resume_id)).execute()
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete resume item")


# ==============================================================================
# PDF GENERATION
# ==============================================================================
def export_resume_pdf(user_id: UUID, resume_id: UUID) -> Response:
    """Generate a clean ATS-friendly PDF from trusted database records."""
    resume = get_resume(user_id, resume_id)
    items = get_resume_items(user_id, resume_id)
    
    # Fetch profile to get real name (best effort)
    client = get_admin_client()
    profile_res = client.table("profiles").select("*").eq("id", str(user_id)).execute()
    full_name = "User Resume"
    if profile_res.data and profile_res.data[0].get("full_name"):
        full_name = profile_res.data[0]["full_name"]
    elif profile_res.data and profile_res.data[0].get("username"):
        full_name = profile_res.data[0]["username"]
        
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    def safe_text(text: str) -> str:
        if not text:
            return ""
        # FPDF2 with default fonts supports latin-1. Replace unsupported chars safely.
        return text.encode("latin-1", "replace").decode("latin-1")
    
    # Header
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, safe_text(full_name), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 10, safe_text(resume.name), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # Summary
    if resume.professional_summary:
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, "SUMMARY", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 11)
        pdf.multi_cell(0, 6, safe_text(resume.professional_summary), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
    
    # Group items by section_type
    sections = {}
    for item in items:
        sections.setdefault(item.section_type, []).append(item)
        
    # Render sections in standard order
    order = ["education", "project", "skill", "certificate"]
    titles = {
        "education": "EDUCATION",
        "project": "PROJECTS",
        "skill": "SKILLS",
        "certificate": "CERTIFICATES"
    }
    
    for section_type in order:
        if section_type in sections:
            pdf.set_font("helvetica", "B", 14)
            pdf.cell(0, 10, titles[section_type], new_x="LMARGIN", new_y="NEXT")
            
            for item in sections[section_type]:
                pdf.set_font("helvetica", "B", 12)
                pdf.multi_cell(0, 6, safe_text(item.title), new_x="LMARGIN", new_y="NEXT")
                
                if item.subtitle:
                    pdf.set_font("helvetica", "I", 11)
                    pdf.multi_cell(0, 6, safe_text(item.subtitle), new_x="LMARGIN", new_y="NEXT")
                    
                if item.description:
                    pdf.set_font("helvetica", "", 11)
                    pdf.multi_cell(0, 6, safe_text(item.description), new_x="LMARGIN", new_y="NEXT")
                    
                pdf.ln(3)
            pdf.ln(2)
            
    # Output PDF
    pdf_bytes = bytes(pdf.output())
    
    # Return as safe Response (bytes)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="resume_{resume.id}.pdf"'
        }
    )
