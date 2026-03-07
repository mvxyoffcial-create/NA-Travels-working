from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
import re


# ─── Auth / User Schemas ────────────────────────────────────────────────────

class UserSignup(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)

    @validator("username")
    def username_alphanumeric(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username must contain only letters, numbers, and underscores.")
        return v.lower()

    @validator("password")
    def password_strength(cls, v):
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @validator("new_password")
    def password_strength(cls, v):
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserPublic(BaseModel):
    id: str
    email: str
    username: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    is_verified: bool
    role: str
    created_at: datetime


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    username: Optional[str] = Field(None, min_length=3, max_length=30)


# ─── Destination Schemas ─────────────────────────────────────────────────────

class DestinationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=200)
    country: str = Field(..., min_length=2, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    description: str = Field(..., min_length=10)
    short_description: Optional[str] = Field(None, max_length=300)
    category: str = Field(..., description="e.g. beach, mountain, city, historical")
    tags: Optional[List[str]] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    best_time_to_visit: Optional[str] = None
    entry_fee: Optional[str] = None
    website: Optional[str] = None


class DestinationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    best_time_to_visit: Optional[str] = None
    entry_fee: Optional[str] = None
    website: Optional[str] = None


# ─── Review Schemas ───────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    rating:    int           = Field(..., ge=1, le=5)
    title:     str           = Field(..., min_length=3, max_length=200)
    body:      str           = Field(..., min_length=10, max_length=5000)
    trip_date: Optional[str] = Field(None, max_length=100, description="e.g. 'March 2026'")
    trip_type: Optional[str] = Field(None, max_length=100, description="e.g. 'Airport Transfer'")


class ReviewUpdate(BaseModel):
    rating:    Optional[int] = Field(None, ge=1, le=5)
    title:     Optional[str] = Field(None, min_length=3, max_length=200)
    body:      Optional[str] = Field(None, min_length=10, max_length=5000)
    trip_date: Optional[str] = None
    trip_type: Optional[str] = None
