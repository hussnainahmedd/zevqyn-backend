"""Pydantic models for ZEVQYN Career AI module."""

from __future__ import annotations

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# COMMON STATS
# ==============================================================================
class CareerProfileStats(BaseModel):
    projects: int = 0
    skills: int = 0
    education: int = 0
    certificates: int = 0
    resumes: int = 0
    portfolios: int = 0


# ==============================================================================
# A. CAREER PROFILE ANALYSIS
# ==============================================================================
class CareerAnalysisResponse(BaseModel):
    readiness_score: int = Field(..., ge=0, le=100, description="AI readiness score 0-100 based on ZEVQYN data")
    summary: str
    strengths: list[str]
    improvement_areas: list[str]
    next_actions: list[str]
    profile_stats: CareerProfileStats


class _GeminiCareerAnalysisOutput(BaseModel):
    """Internal model for strictly parsing Gemini analysis output."""
    readiness_score: int = Field(..., ge=0, le=100)
    summary: str
    strengths: list[str]
    improvement_areas: list[str]
    next_actions: list[str]


# ==============================================================================
# B. SKILL GAP ANALYSIS
# ==============================================================================
class SkillGapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_role: str = Field(..., min_length=2, max_length=150)


class SkillGapItem(BaseModel):
    skill: str
    reason: str
    priority: str = Field(..., description="High, Medium, or Low")
    suggested_action: str


class SkillGapResponse(BaseModel):
    target_role: str
    current_strengths: list[str]
    skill_gaps: list[SkillGapItem]
    recommended_learning: list[str]
    recommended_projects: list[str]


class _GeminiSkillGapOutput(BaseModel):
    """Internal model for Gemini skill-gap output."""
    current_strengths: list[str]
    skill_gaps: list[SkillGapItem]
    recommended_learning: list[str]
    recommended_projects: list[str]


# ==============================================================================
# C. PERSONALIZED PROJECT SUGGESTIONS
# ==============================================================================
class ProjectSuggestionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_role: Optional[str] = Field(None, min_length=1, max_length=150)
    count: int = Field(default=3, ge=1, le=5)


class ProjectSuggestionItem(BaseModel):
    title: str
    description: str
    why_it_fits: str
    suggested_features: list[str]
    technologies: list[str]
    skills_developed: list[str]
    difficulty: str = Field(..., description="Beginner, Intermediate, or Advanced")


class ProjectSuggestionsResponse(BaseModel):
    target_role: Optional[str] = None
    suggestions: list[ProjectSuggestionItem]


class _GeminiProjectSuggestionsOutput(BaseModel):
    """Internal model for Gemini project suggestions output."""
    suggestions: list[ProjectSuggestionItem]


# ==============================================================================
# D. RESUME REVIEW
# ==============================================================================
class ResumeReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resume_id: UUID


class ResumeReviewResponse(BaseModel):
    resume_id: UUID
    score: int = Field(..., ge=0, le=100)
    summary: str
    strengths: list[str]
    improvements: list[str]
    ats_suggestions: list[str]
    content_suggestions: list[str]
    missing_elements: list[str]


class _GeminiResumeReviewOutput(BaseModel):
    """Internal model for Gemini resume review output."""
    score: int = Field(..., ge=0, le=100)
    summary: str
    strengths: list[str]
    improvements: list[str]
    ats_suggestions: list[str]
    content_suggestions: list[str]
    missing_elements: list[str]


# ==============================================================================
# E. PORTFOLIO REVIEW
# ==============================================================================
class PortfolioReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    portfolio_id: UUID


class PortfolioReviewResponse(BaseModel):
    portfolio_id: UUID
    score: int = Field(..., ge=0, le=100)
    summary: str
    strengths: list[str]
    improvements: list[str]
    presentation_suggestions: list[str]
    missing_elements: list[str]


class _GeminiPortfolioReviewOutput(BaseModel):
    """Internal model for Gemini portfolio review output."""
    score: int = Field(..., ge=0, le=100)
    summary: str
    strengths: list[str]
    improvements: list[str]
    presentation_suggestions: list[str]
    missing_elements: list[str]


# ==============================================================================
# F. CAREER ACTION PLAN
# ==============================================================================
class ActionPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_role: str = Field(..., min_length=2, max_length=150)


class ActionPlanItem(BaseModel):
    title: str
    description: str
    category: str = Field(..., description="Skills, Projects, Networking, Certifications, or Resume")
    priority: str = Field(..., description="High, Medium, or Low")


class ActionPlanResponse(BaseModel):
    target_role: str
    summary: str
    days_30: list[ActionPlanItem]
    days_60: list[ActionPlanItem]
    days_90: list[ActionPlanItem]


class _GeminiActionPlanOutput(BaseModel):
    """Internal model for Gemini action plan output."""
    summary: str
    days_30: list[ActionPlanItem]
    days_60: list[ActionPlanItem]
    days_90: list[ActionPlanItem]
