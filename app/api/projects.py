"""API routes for projects."""

from uuid import UUID
from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.project import ProjectCreate, ProjectUpdate, ProjectResponse, ResearchProjectRequest, ProjectProposalPreview
from app.services import projects as project_service
from app.services import workspaces as workspace_service

router = APIRouter(prefix="/api/v1", tags=["projects"])

@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Create a new project."""
    return project_service.create_project(user.id, project)

@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    user: AuthenticatedUser = Depends(get_current_user)
):
    """List user's projects."""
    return project_service.get_projects(user.id)

@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a specific project."""
    return project_service.get_project(user.id, project_id)

@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project: ProjectUpdate,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Update a specific project."""
    return project_service.update_project(user.id, project_id, project)

@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Delete a specific project."""
    return project_service.delete_project(user.id, project_id)

@router.post("/workspaces/{workspace_id}/research/create-project", response_model=ProjectProposalPreview)
async def create_project_preview(
    workspace_id: UUID,
    request: ResearchProjectRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate a project proposal preview from workspace research."""
    workspace_service.get_workspace(user.id, workspace_id)
    return project_service.generate_project_proposal(
        user_id=user.id,
        workspace_id=workspace_id,
        document_id=request.document_id,
        instructions=request.instructions
    )
