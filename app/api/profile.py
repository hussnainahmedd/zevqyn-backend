"""API routes for user profile."""

from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, get_current_user
from app.models.profile import ProfileUpdate, ProfileResponse
from app.services import profile as profile_service

router = APIRouter(prefix="/api/v1", tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user: AuthenticatedUser = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return profile_service.get_profile(user.id)


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    profile: ProfileUpdate,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Update the authenticated user's profile."""
    return profile_service.update_profile(user.id, profile)
