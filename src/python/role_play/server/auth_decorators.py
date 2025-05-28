"""Authentication and authorization decorators for handlers."""

from functools import wraps
from typing import Callable, Optional, Set, Union

from fastapi import HTTPException, status

from ..common.models import UserRole


class AuthRequired:
    """Decorator for methods that require authentication with specific roles.
    
    Usage:
        @auth_required  # Requires any authenticated user (USER, SCRIPTER, or ADMIN)
        @auth_required(UserRole.ADMIN)  # Requires ADMIN role
        @auth_required([UserRole.ADMIN, UserRole.SCRIPTER])  # Requires ADMIN or SCRIPTER
    """
    
    def __init__(self, roles: Optional[Union[UserRole, Set[UserRole], list[UserRole]]] = None):
        if roles is None:
            # Default: any authenticated user
            self.required_roles = {UserRole.USER, UserRole.SCRIPTER, UserRole.ADMIN}
        elif isinstance(roles, UserRole):
            # Single role
            self.required_roles = {roles}
        else:
            # Set or list of roles
            self.required_roles = set(roles)
    
    def __call__(self, func: Callable) -> Callable:
        """Mark the function as requiring authentication."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Add metadata to the function
        wrapper._auth_required = True
        wrapper._required_roles = self.required_roles
        wrapper._auth_decorator = self
        
        return wrapper


# Convenience decorators
auth_required = AuthRequired()  # Any authenticated user
admin_only = AuthRequired(UserRole.ADMIN)  # Admin only
scripter_only = AuthRequired(UserRole.SCRIPTER)  # Scripter only
scripter_or_admin = AuthRequired([UserRole.ADMIN, UserRole.SCRIPTER])  # Scripter or Admin


def public(func: Callable) -> Callable:
    """Decorator for public endpoints that don't require authentication.
    
    This is explicit documentation that the endpoint is intentionally public.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    
    # Mark as explicitly public
    wrapper._auth_required = False
    wrapper._is_public = True
    
    return wrapper


def check_permissions(user_role: UserRole, required_roles: Set[UserRole]) -> bool:
    """Check if a user role has permission to access an endpoint.
    
    Uses the role hierarchy defined in UserRole.has_permission().
    """
    # Check if user has any of the required roles
    for required_role in required_roles:
        if user_role.has_permission(required_role):
            return True
    return False


def require_role(user_role: UserRole, required_roles: Set[UserRole]) -> None:
    """Enforce role requirements, raising HTTPException if not authorized.
    
    Args:
        user_role: The user's current role
        required_roles: Set of roles that are allowed
        
    Raises:
        HTTPException: 401 if not authenticated, 403 if authenticated but not authorized
    """
    if user_role == UserRole.GUEST:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not check_permissions(user_role, required_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {', '.join(r.value for r in required_roles)}",
        )
