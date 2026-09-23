"""v1 API router — workspace and document endpoints."""

from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Response

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.supabase import get_admin_client
from app.models.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse
from app.models.document import DocumentResponse, DocumentDownloadResponse
from app.services import workspaces as workspace_service
from app.services import documents as document_service
from app.services import extraction as extraction_service
from app.services import indexing as indexing_service
from app.services import retrieval as retrieval_service
from app.services import rag as rag_service
from app.models.extraction import ExtractedDocument
from app.models.chunking import IndexingResponse, RetrievedChunk
from app.models.rag import ChatRequest, ChatResponse, ConversationResponse, MessageResponse

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_in: WorkspaceCreate,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Create a new workspace."""
    return workspace_service.create_workspace(user.id, workspace_in)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(user: AuthenticatedUser = Depends(get_current_user)):
    """List all workspaces owned by the user."""
    return workspace_service.get_workspaces(user.id)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a specific workspace."""
    return workspace_service.get_workspace(user.id, workspace_id)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    workspace_in: WorkspaceUpdate,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Update a specific workspace."""
    return workspace_service.update_workspace(user.id, workspace_id, workspace_in)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Delete a workspace (must be empty)."""
    workspace_service.delete_workspace(user.id, workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.post("/{workspace_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: UUID,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Upload a document to a workspace."""
    return document_service.upload_document(user.id, workspace_id, file)


@router.get("/{workspace_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    workspace_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """List all documents in a workspace."""
    return document_service.get_documents(user.id, workspace_id)


@router.get("/{workspace_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    workspace_id: UUID,
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a specific document's metadata."""
    return document_service.get_document(user.id, workspace_id, document_id)


@router.delete("/{workspace_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    workspace_id: UUID,
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Delete a document."""
    document_service.delete_document(user.id, workspace_id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/documents/{document_id}/download", response_model=DocumentDownloadResponse)
async def download_document(
    workspace_id: UUID,
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a short-lived signed URL to download a document."""
    return document_service.generate_download_url(user.id, workspace_id, document_id)


@router.post("/{workspace_id}/documents/{document_id}/extract", response_model=ExtractedDocument)
async def extract_document(
    workspace_id: UUID,
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Extract text from a private document."""
    return extraction_service.process_document(user.id, workspace_id, document_id)


@router.post("/{workspace_id}/documents/{document_id}/index", response_model=IndexingResponse)
async def index_document(
    workspace_id: UUID,
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Run the complete document indexing pipeline (extract, chunk, embed, persist)."""
    return indexing_service.index_document(user.id, workspace_id, document_id)


from pydantic import BaseModel
class SearchRequest(BaseModel):
    query: str
    match_count: int = 5


@router.post("/{workspace_id}/search", response_model=list[RetrievedChunk])
async def search_workspace(
    workspace_id: UUID,
    request: SearchRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Retrieve semantically relevant document chunks within a workspace."""
    # Verify workspace ownership first
    workspace_service.get_workspace(user.id, workspace_id)
    return retrieval_service.search_workspace(user.id, workspace_id, request.query, request.match_count)


@router.post("/{workspace_id}/chat", response_model=ChatResponse)
async def chat_workspace(
    workspace_id: UUID,
    request: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Ask a question and get a grounded answer based on workspace documents."""
    # Verify workspace ownership first
    workspace_service.get_workspace(user.id, workspace_id)
    return rag_service.process_chat_message(
        user_id=user.id,
        workspace_id=workspace_id,
        message=request.message,
        conversation_id=request.conversation_id,
        document_id=request.document_id
    )

@router.get("/{workspace_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    workspace_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """List all conversations in a workspace."""
    workspace_service.get_workspace(user.id, workspace_id)
    client = get_admin_client()
    res = client.table("conversations").select("*").eq("workspace_id", str(workspace_id)).eq("user_id", str(user.id)).order("updated_at", desc=True).execute()
    return res.data


@router.get("/{workspace_id}/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    workspace_id: UUID,
    conversation_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """List all messages in a conversation."""
    workspace_service.get_workspace(user.id, workspace_id)
    rag_service.get_conversation(user.id, workspace_id, conversation_id)
    client = get_admin_client()
    res = client.table("messages").select("*").eq("conversation_id", str(conversation_id)).eq("user_id", str(user.id)).order("created_at", desc=False).execute()
    return res.data


@router.delete("/{workspace_id}/conversations/{conversation_id}")
async def delete_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Delete a research conversation and its messages."""
    workspace_service.get_workspace(user.id, workspace_id)
    return rag_service.delete_conversation(user.id, workspace_id, conversation_id)



