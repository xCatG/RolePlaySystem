"""Dependency injection factories for the Role Play System server."""

import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated

from ..common.auth import AuthManager
from ..common.storage import StorageBackend, FileStorage
from ..common.models import User
from ..common.exceptions import AuthenticationError, TokenExpiredError
from .config_loader import get_config


def get_storage_backend() -> StorageBackend:
    """
    Factory function to get the storage backend instance.
    
    Returns:
        StorageBackend: Configured storage backend based on config
    """
    config = get_config()
    
    if config.storage_type == "file":
        # Validate storage path exists
        if not os.path.exists(config.storage_path):
            raise FileNotFoundError(
                f"Storage path '{config.storage_path}' does not exist. "
                "Please create the directory before starting the server."
            )
        if not os.path.isdir(config.storage_path):
            raise NotADirectoryError(
                f"Storage path '{config.storage_path}' is not a directory."
            )
        if not os.access(config.storage_path, os.R_OK | os.W_OK):
            raise PermissionError(
                f"Storage path '{config.storage_path}' is not readable/writable."
            )
        
        return FileStorage(config.storage_path)
    else:
        raise ValueError(f"Unsupported storage type: {config.storage_type}")


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

