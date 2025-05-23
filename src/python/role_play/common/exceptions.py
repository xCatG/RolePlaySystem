"""Custom exceptions for the Role Play System."""


class RolePlayError(Exception):
    """Base exception for Role Play System."""
    pass


class AuthenticationError(RolePlayError):
    """Authentication related errors."""
    pass


class AuthorizationError(RolePlayError):
    """Authorization related errors."""
    pass


class UserNotFoundError(RolePlayError):
    """User not found error."""
    pass


class InvalidTokenError(AuthenticationError):
    """Invalid token error."""
    pass


class TokenExpiredError(AuthenticationError):
    """Token expired error."""
    pass


class StorageError(RolePlayError):
    """Storage backend errors."""
    pass


class ConfigurationError(RolePlayError):
    """Configuration related errors."""
    pass


class ValidationError(RolePlayError):
    """Data validation errors."""
    pass


class ResourceNotFoundError(RolePlayError):
    """Resource not found error."""
    pass


class PermissionDeniedError(AuthorizationError):
    """Permission denied error."""
    pass