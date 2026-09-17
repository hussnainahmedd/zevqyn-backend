"""Workspace service logic."""

from __future__ import annotations

from uuid import UUID
from fastapi import HTTPException, status
from app.core.supabase import get_admin_client
from app.models.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse


def create_workspace(user_id: UUID, workspace_in: WorkspaceCreate) -> WorkspaceResponse:
    """Create a new workspace for the user."""
    client = get_admin_client()
    
    data = {
        "user_id": str(user_id),
        "name": workspace_in.name,
        "description": workspace_in.description,
    }
    
    response = client.table("workspaces").insert(data).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace",
        )
        
    return WorkspaceResponse(**response.data[0])


def get_workspaces(user_id: UUID) -> list[WorkspaceResponse]:
    """Get all workspaces owned by the user."""
    client = get_admin_client()
    
    response = client.table("workspaces").select("*").eq("user_id", str(user_id)).execute()
    
    return [WorkspaceResponse(**w) for w in response.data]


def get_workspace(user_id: UUID, workspace_id: UUID) -> WorkspaceResponse:
    """Get a specific workspace if owned by the user."""
    client = get_admin_client()
    
    response = client.table("workspaces").select("*").eq("id", str(workspace_id)).eq("user_id", str(user_id)).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
        
    return WorkspaceResponse(**response.data[0])


def update_workspace(user_id: UUID, workspace_id: UUID, workspace_in: WorkspaceUpdate) -> WorkspaceResponse:
    """Update a specific workspace if owned by the user."""
    # Verify existence and ownership first
    get_workspace(user_id, workspace_id)
    
    update_data = {}
    if workspace_in.name is not None:
        update_data["name"] = workspace_in.name
    if workspace_in.description is not None:
        update_data["description"] = workspace_in.description
        
    if not update_data:
        return get_workspace(user_id, workspace_id)
        
    client = get_admin_client()
    response = client.table("workspaces").update(update_data).eq("id", str(workspace_id)).eq("user_id", str(user_id)).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workspace",
        )
        
    return WorkspaceResponse(**response.data[0])


def delete_workspace(user_id: UUID, workspace_id: UUID) -> None:
    """Delete a specific workspace if owned by the user and empty."""
    # Verify existence and ownership first
    get_workspace(user_id, workspace_id)
    
    client = get_admin_client()
    
    # Check if there are any documents in this workspace
    # If yes, reject deletion to prevent orphaned data in Phase 4A
    docs = client.table("documents").select("id").eq("workspace_id", str(workspace_id)).limit(1).execute()
    if docs.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete workspace because it contains documents. Delete all documents first.",
        )
        
    response = client.table("workspaces").delete().eq("id", str(workspace_id)).eq("user_id", str(user_id)).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workspace",
        )
