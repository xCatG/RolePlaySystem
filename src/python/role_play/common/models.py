"""Shared data models for the Role Play System."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User roles for authorization."""
    ADMIN = "admin"
    USER = "user"


class AuthProvider(str, Enum):
    """Authentication providers."""
    LOCAL = "local"
    GOOGLE = "google"


class User(BaseModel):
    """User model."""
    id: str
    username: str
    email: Optional[str] = None
    role: UserRole = UserRole.USER
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


class UserAuthMethod(BaseModel):
    """User authentication method."""
    id: str
    user_id: str
    provider: AuthProvider
    provider_user_id: str
    credentials: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    is_active: bool = True


class TokenData(BaseModel):
    """JWT token payload data."""
    user_id: str
    username: str
    role: UserRole
    exp: int


class SessionData(BaseModel):
    """User session data."""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)