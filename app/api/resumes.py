"""API routes for Resumes."""

from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.resume import (
    ResumeCreate, ResumeUpdate, ResumeResponse,
    ResumeItemCreate, ResumeItemUpdate, ResumeItemResponse
)
from app.services import resumes as resume_service

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


@router.post("", response_model=ResumeResponse)
async def create_resume(resume: ResumeCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return resume_service.create_resume(user.id, resume)

@router.get("", response_model=list[ResumeResponse])
async def list_resumes(user: AuthenticatedUser = Depends(get_current_user)):
    return resume_service.get_resumes(user.id)

@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(resume_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return resume_service.get_resume(user.id, resume_id)

@router.patch("/{resume_id}", response_model=ResumeResponse)
async def update_resume(resume_id: UUID, resume: ResumeUpdate, user: AuthenticatedUser = Depends(get_current_user)):
    return resume_service.update_resume(user.id, resume_id, resume)

@router.delete("/{resume_id}")
async def delete_resume(resume_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return resume_service.delete_resume(user.id, resume_id)


# ==============================================================================
# RESUME ITEMS
# ==============================================================================
@router.post("/{resume_id}/items", response_model=ResumeItemResponse)
async def create_resume_item(resume_id: UUID, item: ResumeItemCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return resume_service.create_resume_item(user.id, resume_id, item)

@router.get("/{resume_id}/items", response_model=list[ResumeItemResponse])
async def list_resume_items(resume_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return resume_service.get_resume_items(user.id, resume_id)

@router.delete("/{resume_id}/items/{item_id}")
async def delete_resume_item(resume_id: UUID, item_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    return resume_service.delete_resume_item(user.id, resume_id, item_id)


# ==============================================================================
# PDF EXPORT
# ==============================================================================
@router.get("/{resume_id}/pdf")
async def export_resume_pdf(resume_id: UUID, user: AuthenticatedUser = Depends(get_current_user)):
    """Export the resume as a PDF."""
    return resume_service.export_resume_pdf(user.id, resume_id)
