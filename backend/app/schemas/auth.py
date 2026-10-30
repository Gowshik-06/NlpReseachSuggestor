"""
Pydantic schemas for authentication, user registration, login, and profile.
"""
from datetime import datetime
from typing import Optional
import re
from pydantic import BaseModel, Field, ConfigDict, field_validator


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Alphanumeric username")
    email: str = Field(..., max_length=255, description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password (min 8 characters)")
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        clean = v.strip()
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", clean):
            raise ValueError("Username can only contain letters, numbers, dots, hyphens, and underscores")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean):
            raise ValueError("Invalid email format")
        return clean


class UserLoginRequest(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Plaintext password")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    firebase_uid: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class FirebaseLoginRequest(BaseModel):
    id_token: str = Field(..., description="Firebase ID token (Bearer)")


class LinkFirebaseAccountRequest(BaseModel):
    firebase_token: str = Field(..., description="Firebase ID token proving ownership of Firebase identity")
    local_password: str = Field(..., description="Current local password proving ownership of local account")
    username_or_email: Optional[str] = Field(
        default=None,
        description="Local username or email to link (optional if calling with an existing session)"
    )


class LinkFirebaseAccountResponse(BaseModel):
    status: str
    message: str
    user: UserResponse
