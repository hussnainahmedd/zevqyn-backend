"""Service for managing resumes, resume items, and PDF export."""

from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any
from uuid import UUID
from fastapi import HTTPException, status
from fastapi.responses import Response
from fpdf import FPDF

from app.core.supabase import get_admin_client
from app.models.resume import (
    ResumeCreate, ResumeUpdate, ResumeResponse,
    ResumeItemCreate, ResumeItemUpdate, ResumeItemResponse,
    ResumeItemsReorderRequest
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


def update_resume_item(user_id: UUID, resume_id: UUID, item_id: UUID, item: ResumeItemUpdate) -> ResumeItemResponse:
    """Update a single resume item (e.g. sort_order) after verifying resume and item ownership."""
    get_resume(user_id, resume_id)
    client = get_admin_client()

    try:
        item_res = client.table("resume_items").select("*").eq("id", str(item_id)).execute()
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch resume item")

    if not item_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume item not found")

    if item_res.data[0]["resume_id"] != str(resume_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item does not belong to this resume")

    update_data = item.model_dump(exclude_unset=True)
    if not update_data:
        return ResumeItemResponse(**item_res.data[0])

    try:
        res = client.table("resume_items").update(update_data).eq("id", str(item_id)).eq("resume_id", str(resume_id)).execute()
        if not res.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update resume item")
        return ResumeItemResponse(**res.data[0])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update resume item")


def reorder_resume_items(user_id: UUID, resume_id: UUID, reorder_in: ResumeItemsReorderRequest) -> list[ResumeItemResponse]:
    """Bulk update sort_order for resume items after validating all items belong to this resume."""
    get_resume(user_id, resume_id)
    client = get_admin_client()

    # 1. Check for duplicate IDs in payload
    supplied_ids = [str(entry.id) for entry in reorder_in.items]
    if len(supplied_ids) != len(set(supplied_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate item IDs in reorder request")

    # 2. Fetch existing items for this resume
    try:
        existing_res = client.table("resume_items").select("id, resume_id").eq("resume_id", str(resume_id)).execute()
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch existing resume items")

    existing_ids = {row["id"] for row in (existing_res.data or [])}

    # 3. Validate every item before writing anything
    for entry in reorder_in.items:
        eid = str(entry.id)
        if eid not in existing_ids:
            # Check if it belongs to another resume
            try:
                other_res = client.table("resume_items").select("id, resume_id").eq("id", eid).execute()
            except Exception:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to validate resume item")

            if other_res.data:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Item {eid} belongs to another resume")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Resume item {eid} not found")

    # 4. Perform updates
    try:
        for entry in reorder_in.items:
            client.table("resume_items").update({"sort_order": entry.sort_order}).eq("id", str(entry.id)).eq("resume_id", str(resume_id)).execute()
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update resume item orders")

    # 5. Return all items in effective sorted order
    return get_resume_items(user_id, resume_id)


# ==============================================================================
# PDF HELPERS & FORMATTING
# ==============================================================================
def _clean_text(text: str | None) -> str:
    """Safely convert unicode text to latin-1 compatible string for standard FPDF fonts."""
    if not text:
        return ""
    subs = {
        "\u2013": "-",       # en-dash
        "\u2014": " - ",     # em-dash
        "\u2018": "'",       # left single quote
        "\u2019": "'",       # right single quote
        "\u201c": '"',       # left double quote
        "\u201d": '"',       # right double quote
        "\u2022": "\u00b7",   # bullet -> middle dot
        "\u2026": "...",     # ellipsis
        "\u00a0": " ",       # non-breaking space
        "\u200b": "",        # zero-width space
        "\u2010": "-",       # hyphen
        "\u2011": "-",       # non-breaking hyphen
        "\u2012": "-",       # figure dash
    }
    s = str(text)
    for orig, repl in subs.items():
        s = s.replace(orig, repl)
    return s.encode("latin-1", "replace").decode("latin-1")


def _format_date(d: Any) -> str:
    """Convert date or date string into clean 'Mon YYYY' format (e.g., 'Sep 2024')."""
    if not d:
        return ""
    if isinstance(d, (date, datetime)):
        return d.strftime("%b %Y")
    s = str(d).strip()
    if not s:
        return ""
    if s.lower() in ("present", "current", "now"):
        return "Present"
    m = re.match(r"^(\d{4})-(\d{2})(?:-\d{2})?$", s)
    if m:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        year = m.group(1)
        month_idx = int(m.group(2)) - 1
        if 0 <= month_idx < 12:
            return f"{months[month_idx]} {year}"
    if re.match(r"^\d{4}$", s):
        return s
    return s


def _format_date_range(start: Any, end: Any = None) -> str:
    """Format start and end into a clean date range, avoiding awkward formatting."""
    if not start and not end:
        return ""
    if start and not end:
        s_str = str(start).strip()
        if re.search(r"\s+[-–—]\s+", s_str):
            parts = re.split(r"\s+[-–—]\s+", s_str, maxsplit=1)
            p0 = _format_date(parts[0])
            p1 = _format_date(parts[1]) if parts[1] else "Present"
            return f"{p0} - {p1}"
        return f"{_format_date(start)} - Present"
    f_start = _format_date(start)
    f_end = _format_date(end) if end else "Present"
    if f_start and f_end:
        return f"{f_start} - {f_end}"
    return f_start or f_end


def _format_degree(degree: str | None, field_of_study: str | None = None) -> str:
    """Format degree and field of study, avoiding redundancy like 'BS Computer Science in Computer Science'."""
    deg = (degree or "").strip()
    field = (field_of_study or "").strip()
    if deg and field:
        if field.lower() in deg.lower():
            return deg
        if deg.lower() in field.lower():
            return field
        return f"{deg} in {field}"
    if deg and not field:
        if " in " in deg:
            parts = deg.split(" in ", 1)
            p0 = parts[0].strip()
            p1 = parts[1].strip()
            if p1.lower() in p0.lower():
                return p0
        return deg
    return field


def _format_url_label(url: str | None, default_label: str = "Link") -> tuple[str, str] | None:
    """Return a tuple of (display_label, full_url) or None if url is empty or invalid."""
    if not url:
        return None
    s = str(url).strip()
    if not s or s.lower() in ("none", "null", "undefined"):
        return None
    full_url = s if s.startswith(("http://", "https://", "mailto:")) else f"https://{s}"
    return default_label, full_url


def _group_skills(items: list[Any]) -> dict[str, list[str]]:
    """Group skills by category and ignore numeric proficiency ratings."""
    groups: dict[str, list[str]] = {}
    for item in items:
        raw_cat = getattr(item, "subtitle", None) or "Other Skills"
        cat = raw_cat.strip()
        if not cat:
            cat = "Skills"
        elif cat.islower():
            cat = cat.title()
        
        name = getattr(item, "title", "").strip()
        if not name:
            continue
        
        if cat not in groups:
            groups[cat] = []
        if name not in groups[cat]:
            groups[cat].append(name)
    return groups


def _is_valid_summary(summary: str | None) -> bool:
    """Check if professional summary contains genuine content instead of placeholder text."""
    if not summary:
        return False
    cleaned = summary.strip().lower().rstrip(".")
    placeholders = {
        "professional summary",
        "add your professional summary",
        "summary",
        "professional summary text",
        "n/a",
        "none",
        "null",
        "your summary here",
    }
    return len(cleaned) > 0 and cleaned not in placeholders


def _render_section_heading(pdf: FPDF, title: str) -> None:
    """Render a consistent ATS section heading with a subtle horizontal rule."""
    if pdf.h - pdf.b_margin - pdf.get_y() < 25:
        pdf.add_page()
    
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_line_width(0.3)
    pdf.set_draw_color(160, 160, 160)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(2.5)


def _get_field_val(
    resume_obj: Any,
    profile_dict: dict[str, Any],
    key: str,
    fallback_profile_keys: list[str] | None = None,
    default: str | None = None,
) -> str | None:
    """Extract a field prioritizing resume data (dict or obj attribute), falling back to profile/default."""
    val = None
    if isinstance(resume_obj, dict):
        val = resume_obj.get(key)
    else:
        val = getattr(resume_obj, key, None)
        if val is None and hasattr(resume_obj, "__dict__"):
            val = resume_obj.__dict__.get(key)

    if isinstance(val, (str, int, float)):
        val_str = str(val).strip()
        if val_str and val_str.lower() not in ("none", "null", "undefined"):
            return val_str

    if isinstance(profile_dict, dict):
        keys_to_check = [key] + (fallback_profile_keys or [])
        for pk in keys_to_check:
            pval = profile_dict.get(pk)
            if isinstance(pval, (str, int, float)):
                pval_str = str(pval).strip()
                if pval_str and pval_str.lower() not in ("none", "null", "undefined"):
                    return pval_str

    if isinstance(default, (str, int, float)):
        def_str = str(default).strip()
        if def_str and def_str.lower() not in ("none", "null", "undefined"):
            return def_str

    return None


# ==============================================================================
# PDF GENERATION
# ==============================================================================
def export_resume_pdf(user_id: UUID, resume_id: UUID) -> Response:
    """Generate a clean ATS-friendly single-column PDF from trusted database records."""
    resume = get_resume(user_id, resume_id)
    items = get_resume_items(user_id, resume_id)
    
    # Fetch profile and auth data to get comprehensive fallback info (best effort)
    client = get_admin_client()
    profile_data: dict[str, Any] = {}
    auth_email: str | None = None
    try:
        profile_res = client.table("profiles").select("*").eq("id", str(user_id)).execute()
        if profile_res.data and isinstance(profile_res.data, list) and isinstance(profile_res.data[0], dict):
            profile_data = profile_res.data[0]
    except Exception:
        pass

    try:
        auth_user = client.auth.admin.get_user_by_id(str(user_id))
        raw_email = getattr(getattr(auth_user, "user", None), "email", None)
        if isinstance(raw_email, str) and raw_email.strip():
            auth_email = raw_email.strip()
    except Exception:
        pass
        
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    content_w = pdf.w - pdf.l_margin - pdf.r_margin

    # --------------------------------------------------------------------------
    # 1. HEADER
    # --------------------------------------------------------------------------
    # Full Name (most prominent, bold 18pt, centered)
    name_to_use = _get_field_val(
        resume, profile_data, "full_name", fallback_profile_keys=["username"], default="User Resume"
    )
    name_clean = _clean_text(name_to_use or "")
    if name_clean:
        pdf.set_font("helvetica", "B", 18)
        pdf.cell(0, 8, name_clean.upper(), align="C", new_x="LMARGIN", new_y="NEXT")

    # Professional Title (11pt, centered)
    prof_title = _get_field_val(resume, profile_data, "professional_title", fallback_profile_keys=["bio"])
    if prof_title:
        pdf.set_font("helvetica", "", 11)
        pdf.cell(0, 5, _clean_text(prof_title), align="C", new_x="LMARGIN", new_y="NEXT")

    # Contact line: location | email | phone
    loc_val = _get_field_val(resume, profile_data, "location")
    email_val = _get_field_val(resume, profile_data, "email", default=auth_email)
    phone_val = _get_field_val(resume, profile_data, "phone")
    contact_parts = []
    for val in [loc_val, email_val, phone_val]:
        if val:
            contact_parts.append(_clean_text(val))

    if contact_parts:
        pdf.set_font("helvetica", "", 9.5)
        pdf.cell(0, 5, " | ".join(contact_parts), align="C", new_x="LMARGIN", new_y="NEXT")

    # Professional Links: LinkedIn | GitHub | Portfolio
    linkedin_val = _get_field_val(resume, profile_data, "linkedin_url")
    github_val = _get_field_val(resume, profile_data, "github_url")
    portfolio_val = _get_field_val(resume, profile_data, "portfolio_url", fallback_profile_keys=["website"])
    link_entries = []
    for label, val in [
        ("LinkedIn", linkedin_val),
        ("GitHub", github_val),
        ("Portfolio", portfolio_val),
    ]:
        entry = _format_url_label(val, default_label=label)
        if entry:
            link_entries.append(entry)

    if link_entries:
        pdf.set_font("helvetica", "", 9.5)
        sep = " | "
        sep_w = pdf.get_string_width(sep)
        total_w = sum(pdf.get_string_width(lbl) for lbl, _ in link_entries) + sep_w * (len(link_entries) - 1)
        pdf.set_x((pdf.w - total_w) / 2)
        for i, (lbl, url) in enumerate(link_entries):
            if i > 0:
                pdf.set_text_color(100, 100, 100)
                pdf.write(5, sep)
            pdf.set_text_color(0, 0, 0)
            pdf.write(5, lbl, link=url)
        pdf.ln(5)

    pdf.ln(3)

    # --------------------------------------------------------------------------
    # 2. PROFESSIONAL SUMMARY
    # --------------------------------------------------------------------------
    summary_text = _get_field_val(resume, profile_data, "professional_summary")
    if _is_valid_summary(summary_text):
        _render_section_heading(pdf, "PROFESSIONAL SUMMARY")
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 4.8, _clean_text(summary_text or ""), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Group items by section_type
    sections: dict[str, list[Any]] = {}
    for item in items:
        sections.setdefault(item.section_type, []).append(item)

    # --------------------------------------------------------------------------
    # 3. EDUCATION
    # --------------------------------------------------------------------------
    if "education" in sections and sections["education"]:
        _render_section_heading(pdf, "EDUCATION")
        for item in sections["education"]:
            inst = getattr(item, "title", "") or ""
            degree_str = getattr(item, "subtitle", "") or ""
            date_str = ""
            desc_str = ""

            item_metadata = getattr(item, "metadata", None)
            source_id = item_metadata.get("source_id") if isinstance(item_metadata, dict) else None
            edu_rec = None
            if source_id:
                try:
                    edu_rec = get_education(user_id, UUID(str(source_id)))
                except Exception:
                    pass

            if edu_rec:
                inst = edu_rec.institution
                degree_str = _format_degree(edu_rec.degree, edu_rec.field_of_study)
                date_str = _format_date_range(edu_rec.start_date, edu_rec.end_date)
                desc_str = edu_rec.description or ""
            else:
                degree_str = _format_degree(degree_str)
                item_desc = getattr(item, "description", None)
                if item_desc:
                    parts = str(item_desc).split(" | ", 1)
                    date_str = _format_date_range(parts[0])
                    if len(parts) > 1:
                        desc_str = parts[1].strip()

            if pdf.h - pdf.b_margin - pdf.get_y() < 18:
                pdf.add_page()

            pdf.set_font("helvetica", "B", 10.5)
            date_display = _clean_text(date_str)
            date_w = pdf.get_string_width(date_display) + 4 if date_display else 0
            inst_w = content_w - date_w

            pdf.cell(inst_w, 5, _clean_text(inst), align="L")
            if date_display:
                pdf.set_font("helvetica", "", 9.5)
                pdf.cell(date_w, 5, date_display, align="R", new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.ln(5)

            if degree_str:
                pdf.set_font("helvetica", "I", 10)
                pdf.multi_cell(0, 4.5, _clean_text(degree_str), new_x="LMARGIN", new_y="NEXT")

            if desc_str:
                pdf.set_font("helvetica", "", 9.5)
                pdf.multi_cell(0, 4.2, _clean_text(desc_str), new_x="LMARGIN", new_y="NEXT")

            pdf.ln(2.5)

    # --------------------------------------------------------------------------
    # 4. PROJECTS
    # --------------------------------------------------------------------------
    if "project" in sections and sections["project"]:
        _render_section_heading(pdf, "PROJECTS")
        for item in sections["project"]:
            proj_title = getattr(item, "title", "") or ""
            tech_str = getattr(item, "subtitle", "") or ""
            desc_str = getattr(item, "description", "") or ""
            proj_links = []

            item_metadata = getattr(item, "metadata", None)
            source_id = item_metadata.get("source_id") if isinstance(item_metadata, dict) else None
            if source_id:
                try:
                    proj_rec = get_project(user_id, UUID(str(source_id)))
                    if proj_rec:
                        proj_title = proj_rec.title
                        if proj_rec.technologies:
                            tech_str = " \u00b7 ".join(proj_rec.technologies)
                        desc_str = proj_rec.short_description or proj_rec.description or desc_str
                        if proj_rec.github_url:
                            gh_entry = _format_url_label(proj_rec.github_url, default_label="GitHub")
                            if gh_entry:
                                proj_links.append(gh_entry)
                        if proj_rec.live_url:
                            live_entry = _format_url_label(proj_rec.live_url, default_label="Live Demo")
                            if live_entry:
                                proj_links.append(live_entry)
                except Exception:
                    pass

            if "," in tech_str and "\u00b7" not in tech_str:
                tech_str = " \u00b7 ".join([t.strip() for t in tech_str.split(",") if t.strip()])

            if pdf.h - pdf.b_margin - pdf.get_y() < 20:
                pdf.add_page()

            pdf.set_font("helvetica", "B", 10.5)
            if proj_links:
                pdf.set_font("helvetica", "", 9)
                link_w = sum(pdf.get_string_width(lbl) for lbl, _ in proj_links) + (len(proj_links) - 1) * pdf.get_string_width(" | ") + 4
                title_w = content_w - link_w
                pdf.set_font("helvetica", "B", 10.5)
                pdf.cell(title_w, 5, _clean_text(proj_title), align="L")
                pdf.set_font("helvetica", "", 9)
                for i, (lbl, url) in enumerate(proj_links):
                    if i > 0:
                        pdf.set_text_color(100, 100, 100)
                        pdf.write(5, " | ")
                    pdf.set_text_color(0, 0, 0)
                    pdf.write(5, lbl, link=url)
                pdf.ln(5)
            else:
                pdf.cell(0, 5, _clean_text(proj_title), new_x="LMARGIN", new_y="NEXT")

            if tech_str:
                pdf.set_font("helvetica", "I", 9.5)
                pdf.multi_cell(0, 4.5, _clean_text(tech_str), new_x="LMARGIN", new_y="NEXT")

            if desc_str:
                pdf.set_font("helvetica", "", 9.5)
                lines = [l.strip() for l in str(desc_str).split("\n") if l.strip()]
                for line in lines:
                    if not line.startswith(("\u00b7", "-", "*", "\u2022")):
                        line = f"\u00b7 {line}"
                    pdf.multi_cell(0, 4.2, _clean_text(line), new_x="LMARGIN", new_y="NEXT")

            pdf.ln(2.5)

    # --------------------------------------------------------------------------
    # 5. SKILLS
    # --------------------------------------------------------------------------
    if "skill" in sections and sections["skill"]:
        _render_section_heading(pdf, "SKILLS")
        grouped_skills = _group_skills(sections["skill"])
        for cat, skill_names in grouped_skills.items():
            if pdf.h - pdf.b_margin - pdf.get_y() < 10:
                pdf.add_page()
            prefix = f"{cat}: "
            names_str = ", ".join(skill_names)
            pdf.set_font("helvetica", "B", 9.5)
            pdf.write(4.8, _clean_text(prefix))
            pdf.set_font("helvetica", "", 9.5)
            pdf.write(4.8, _clean_text(names_str))
            pdf.ln(4.8)
        pdf.ln(2)

    # --------------------------------------------------------------------------
    # 6. CERTIFICATIONS
    # --------------------------------------------------------------------------
    if "certificate" in sections and sections["certificate"]:
        _render_section_heading(pdf, "CERTIFICATIONS")
        for item in sections["certificate"]:
            cert_title = getattr(item, "title", "") or ""
            issuer = getattr(item, "subtitle", "") or ""
            date_str = ""
            cred_id = None
            cred_url = None
            desc_str = ""

            item_metadata = getattr(item, "metadata", None)
            source_id = item_metadata.get("source_id") if isinstance(item_metadata, dict) else None
            if source_id:
                try:
                    cert_rec = get_certificate(user_id, UUID(str(source_id)))
                    if cert_rec:
                        cert_title = cert_rec.title
                        issuer = cert_rec.issuer
                        date_str = _format_date(cert_rec.issue_date)
                        cred_id = cert_rec.credential_id
                        cred_url = cert_rec.credential_url
                        desc_str = cert_rec.description or ""
                except Exception:
                    pass

            item_desc = getattr(item, "description", None)
            if item_desc and not date_str:
                parts = str(item_desc).split(" | ")
                for p in parts:
                    if p.startswith("Issued:"):
                        raw_d = p.replace("Issued:", "").strip()
                        date_str = _format_date(raw_d)

            if pdf.h - pdf.b_margin - pdf.get_y() < 15:
                pdf.add_page()

            date_display = _clean_text(date_str)
            pdf.set_font("helvetica", "", 9.5)
            date_w = pdf.get_string_width(date_display) + 4 if date_display else 0
            title_w = content_w - date_w

            title_issuer = f"{cert_title} - {issuer}" if issuer else cert_title
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(title_w, 5, _clean_text(title_issuer), align="L")
            if date_display:
                pdf.set_font("helvetica", "", 9.5)
                pdf.cell(date_w, 5, date_display, align="R", new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.ln(5)

            if cred_url:
                pdf.set_font("helvetica", "", 9)
                full_url = cred_url if cred_url.startswith(("http://", "https://")) else f"https://{cred_url}"
                pdf.write(4.5, "Verify Credential", link=full_url)
                pdf.ln(4.5)

            pdf.ln(2.5)

    # Output PDF
    pdf_bytes = bytes(pdf.output())
    
    # Return as safe Response (bytes)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="resume_{resume_id}.pdf"'
        }
    )

