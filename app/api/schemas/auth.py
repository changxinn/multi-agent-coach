"""
Authentication request/response schemas.
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    """User registration request schema."""

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)


class TokenResponse(BaseModel):
    """JWT token response schema."""

    access_token: str
    token_type: str = "bearer"
    user: dict  # Contains id, email, name, user_image


class UserResponse(BaseModel):
    """User information response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    enabled: bool
    user_image: Optional[str] = None


class UserWithProfileResponse(BaseModel):
    """User with fitness profile response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    enabled: bool
    fitness_profile: Optional[dict] = None


class RoleUpdateRequest(BaseModel):
    """Admin request to update user role."""

    role: str = Field(..., pattern="^(ADMIN|STAFF|USER)$")


class FitnessProfileUpdateRequest(BaseModel):
    """User request to update fitness profile."""

    fitness_goal: Optional[str] = Field(None, max_length=255)
    fitness_level: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced)$")
    weight_kg: Optional[float] = Field(None, gt=0, lt=500)
    height_cm: Optional[float] = Field(None, gt=0, lt=300)
    age: Optional[int] = Field(None, gt=0, lt=150)
