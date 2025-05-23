"""Dependency injection factories for the Role Play System server."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated

from ..common.auth import AuthManager
from ..common.storage import StorageBackend, FileStorage
from ..common.models import User
from ..common.exceptions import AuthenticationError, TokenExpiredError


# Global instances (will be replaced with proper config-based initialization)
_storage_backend: StorageBackend = None
_auth_manager: AuthManager = None


def get_storage_backend() -> StorageBackend:
    """Get the storage backend instance."""
    global _storage_backend
    if _storage_backend is None:
        # Default to FileStorage for development
        _storage_backend = FileStorage("./data")
    return _storage_backend


def get_auth_manager(
    storage: Annotated[StorageBackend, Depends(get_storage_backend)]
) -> AuthManager:
    """Get the auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager(storage)
    return _auth_manager


# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_manager: Annotated[AuthManager, Depends(get_auth_manager)]
) -> User:
    """
    Get the current user from the JWT token.
    
    Args:
        credentials: HTTP Authorization header with Bearer token
        auth_manager: AuthManager instance
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        token_data = auth_manager.verify_token(credentials.credentials)
        user = await auth_manager.storage.get_user(token_data.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def set_storage_backend(storage: StorageBackend):
    """Set the global storage backend (for testing or configuration)."""
    global _storage_backend
    _storage_backend = storage


def set_auth_manager(auth_manager: AuthManager):
    """Set the global auth manager (for testing or configuration)."""
    global _auth_manager
    _auth_manager = auth_manager