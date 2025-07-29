"""Dependency injection factories for the Role Play System server."""

import os
from pathlib import Path
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated, Set
from google.adk.sessions import InMemorySessionService

from ..common.auth import AuthManager
from ..common.storage import StorageBackend, FileStorage, FileStorageConfig, LockConfig
from ..common.storage_factory import create_storage_backend
from ..common.models import User, UserRole, Environment
from ..common.exceptions import AuthenticationError, TokenExpiredError
from .config_loader import get_config, ServerConfig
from ..chat.chat_logger import ChatLogger
from ..common.resource_loader import ResourceLoader

import logging
logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def get_server_config() -> ServerConfig:
    """Provides the global server configuration."""
    return get_config()


@lru_cache(maxsize=None)
def get_storage_backend() -> StorageBackend:
    """
    Factory function to get the storage backend instance.
    This is a singleton, created once.
    """
    config = get_server_config()
    
    # Determine environment
    environment = os.getenv("ENVIRONMENT", "dev")
    try:
        env_enum = Environment(environment)
    except ValueError:
        # Default to dev for unknown environments
        env_enum = Environment.DEV
        logger.warning(f"Unknown environment '{environment}', defaulting to DEV")
    
    # Use storage configuration
    if config.storage:
        return create_storage_backend(config.storage, env_enum)
    else:
        raise ValueError("Storage configuration is required")


@lru_cache
def get_resource_loader() -> ResourceLoader:
    """
    Singleton factory for the ResourceLoader.
    Reads resource paths from the main config.
    """
    config = get_server_config()
    storage = get_storage_backend()
    # ResourceLoader expects base_prefix as a string, not a dict
    return ResourceLoader(storage, "resources/")


def get_auth_manager(
    storage: Annotated[StorageBackend, Depends(get_storage_backend)]
) -> AuthManager:
    """
    Factory function to get the auth manager instance.
    
    Args:
        storage: Storage backend injected by FastAPI
        
    Returns:
        AuthManager: Configured auth manager with JWT settings from config
    """
    config = get_config()
    return AuthManager(
        storage=storage,
        jwt_secret_key=config.jwt_secret_key,
        jwt_algorithm=config.jwt_algorithm,
        access_token_expire_minutes=config.jwt_expire_hours * 60
    )


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


class RoleChecker:
    """Dependency factory for checking user roles."""

    def __init__(self, required_roles: Set[UserRole]):
        self.required_roles = required_roles

    async def __call__(self, user: Annotated[User, Depends(get_current_user)]) -> User:
        """
        Checks if the current user has the required role(s).
        
        Args:
            user: Current authenticated user
            
        Returns:
            User: The user if they have required permissions
            
        Raises:
            HTTPException: 403 if roles are insufficient
        """
        has_permission = any(user.role.has_permission(req_role) for req_role in self.required_roles)
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Requires one of: {[r.value for r in self.required_roles]}"
            )
        return user


# Create specific dependency instances for common role checks
require_admin = RoleChecker({UserRole.ADMIN})
require_scripter_or_admin = RoleChecker({UserRole.SCRIPTER, UserRole.ADMIN})
require_user_or_higher = RoleChecker({UserRole.USER, UserRole.SCRIPTER, UserRole.ADMIN})


# --- Singleton Service Providers ---
# These use @lru_cache(maxsize=None) to ensure only one instance
# of each service is created and shared across requests.

def get_chat_logger(
    storage: Annotated[StorageBackend, Depends(get_storage_backend)]
) -> ChatLogger:
    """
    Provides a ChatLogger instance with injected storage backend.
    Note: This is NOT a singleton as it depends on the storage backend.
    """
    return ChatLogger(storage_backend=storage)


@lru_cache(maxsize=None)
def get_adk_session_service() -> InMemorySessionService:
    """
    Provides a singleton instance of ADK's InMemorySessionService.
    """
    return InMemorySessionService()
