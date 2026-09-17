"""Pydantic models for career profile (skills, education, certificates) and AI."""

from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import date, datetime

from pydantic import BaseModel, Field


# Skills
class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., max_length=50)
    proficiency: int = Field(..., ge=1, le=5)

class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    proficiency: Optional[int] = Field(None, ge=1, le=5)

class SkillResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    category: str
    proficiency: int
    created_at: datetime


# Education
class EducationCreate(BaseModel):
    institution: str = Field(..., min_length=1, max_length=200)
    degree: str = Field(..., min_length=1, max_length=200)
    field_of_study: str = Field(..., min_length=1, max_length=200)
    start_date: date
    end_date: Optional[date] = None
    description: Optional[str] = Field(None, max_length=2000)

class EducationUpdate(BaseModel):
    institution: Optional[str] = Field(None, min_length=1, max_length=200)
    degree: Optional[str] = Field(None, min_length=1, max_length=200)
    field_of_study: Optional[str] = Field(None, min_length=1, max_length=200)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = Field(None, max_length=2000)

class EducationResponse(BaseModel):
    id: UUID
    user_id: UUID
    institution: str
    degree: str
    field_of_study: str
    start_date: date
    end_date: Optional[date] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Certificates
class CertificateCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    issuer: str = Field(..., min_length=1, max_length=200)
    issue_date: date
    expiry_date: Optional[date] = None
    credential_id: Optional[str] = Field(None, max_length=200)
    credential_url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)

class CertificateUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    issuer: Optional[str] = Field(None, min_length=1, max_length=200)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    credential_id: Optional[str] = Field(None, max_length=200)
    credential_url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)

class CertificateResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    issuer: str
    issue_date: date
    expiry_date: Optional[date] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# AI Career Assistant
class CareerAssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)

class ProfileStats(BaseModel):
    projects: int
    skills: int
    education: int
    certificates: int

class CareerAssistantResponse(BaseModel):
    answer: str
    profile_used: ProfileStats

class _GeminiCareerAssistantOutput(BaseModel):
    """Internal strictly typed model for parsing Career AI output."""
    answer: str
