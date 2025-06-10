"""Shared data models for the Role Play System."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User roles for authorization.
    
    Roles are ordered by privilege level (highest to lowest).
    Each role inherits permissions from lower privilege roles.
    """
    # Highest privilege - full system access
    ADMIN = "admin"  # Can manage users, scripts, system settings
    
    # Scripter role - can create and manage scripts
    SCRIPTER = "scripter"  # Can create/edit/delete scripts used by chat
    
    # Regular authenticated user
    USER = "user"  # Can use chat and evaluator features
    
    # Not authenticated - minimal access
    GUEST = "guest"  # Can only access public endpoints (health, docs)
    
    @classmethod
    def from_str(cls, role_str: Optional[str]) -> "UserRole":
        """Convert string to UserRole, defaulting to GUEST if invalid."""
        if not role_str:
            return cls.GUEST
        try:
            return cls(role_str.lower())
        except ValueError:
            return cls.GUEST
    
    def has_permission(self, required_role: "UserRole") -> bool:
        """Check if this role has permission for the required role.
        
        Uses a hierarchy where higher roles have all permissions of lower roles.
        ADMIN > SCRIPTER > USER > GUEST
        """
        role_hierarchy = {
            UserRole.ADMIN: 4,
            UserRole.SCRIPTER: 3,
            UserRole.USER: 2,
            UserRole.GUEST: 1,
        }
        return role_hierarchy.get(self, 0) >= role_hierarchy.get(required_role, 0)
    
    @property
    def is_authenticated(self) -> bool:
        """Check if role represents an authenticated user."""
        return self != UserRole.GUEST


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
    preferred_language: str = "en"
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
    
    @classmethod
    def guest(cls) -> "TokenData":
        """Create a guest token data (for unauthenticated requests)."""
        return cls(
            user_id="guest",
            username="guest",
            role=UserRole.GUEST,
            exp=0  # Guest tokens don't expire
        )


class SessionData(BaseModel):
    """User session data."""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseResponse(BaseModel):
    """Base fields for all API responses."""
    success: bool = True
    message: Optional[str] = None  # Human-readable message (useful for clients)


class UpdateLanguageRequest(BaseModel):
    """Request to update user's language preference."""
    language: str = Field(..., description="Language code (e.g., 'en', 'zh-TW')")


class UpdateLanguageResponse(BaseResponse):
    """Response for language preference update."""
    language: str = Field(..., description="Updated language preference")


class Environment(str, Enum):
    """Supported deployment environments."""
    DEV = "dev"
    BETA = "beta"
    PROD = "prod"
