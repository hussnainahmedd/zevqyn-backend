"""API endpoints for Research AI capabilities."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.research import (
    ResearchRequest,
    QuestionRequest,
    FlashcardRequest,
    KeyPointRequest,
    SummaryResponse,
    KeyPointsResponse,
    QuestionsResponse,
    FlashcardsResponse,
)
from app.services import workspaces as workspace_service
from app.services import research_ai

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/research", tags=["research"])


@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(
    workspace_id: UUID,
    request: ResearchRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate a comprehensive research summary for a workspace or document."""
    workspace_service.get_workspace(user.id, workspace_id)
    return research_ai.generate_research_summary(
        user_id=user.id,
        workspace_id=workspace_id,
        document_id=request.document_id
    )


@router.post("/key-points", response_model=KeyPointsResponse)
async def generate_key_points(
    workspace_id: UUID,
    request: KeyPointRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate key points/insights from research material."""
    workspace_service.get_workspace(user.id, workspace_id)
    return research_ai.generate_research_key_points(
        user_id=user.id,
        workspace_id=workspace_id,
        document_id=request.document_id,
        count=request.count
    )


@router.post("/questions", response_model=QuestionsResponse)
async def generate_questions(
    workspace_id: UUID,
    request: QuestionRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate study/research questions from research material."""
    workspace_service.get_workspace(user.id, workspace_id)
    return research_ai.generate_research_questions(
        user_id=user.id,
        workspace_id=workspace_id,
        document_id=request.document_id,
        count=request.count
    )


@router.post("/flashcards", response_model=FlashcardsResponse)
async def generate_flashcards(
    workspace_id: UUID,
    request: FlashcardRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Generate flashcards from research material."""
    workspace_service.get_workspace(user.id, workspace_id)
    return research_ai.generate_research_flashcards(
        user_id=user.id,
        workspace_id=workspace_id,
        document_id=request.document_id,
        count=request.count
    )
