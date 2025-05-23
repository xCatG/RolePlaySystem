"""Unit tests for common.exceptions module."""

import pytest

from role_play.common.exceptions import (
    RolePlayError,
    AuthenticationError,
    AuthorizationError,
    UserNotFoundError,
    InvalidTokenError,
    TokenExpiredError,
    StorageError,
    ConfigurationError,
    ValidationError,
    ResourceNotFoundError,
    PermissionDeniedError
)


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""
    
    def test_base_exception(self):
        """Test RolePlayError as base exception."""
        error = RolePlayError("Base error")
        assert isinstance(error, Exception)
        assert str(error) == "Base error"
    
    def test_authentication_error_inheritance(self):
        """Test AuthenticationError inherits from RolePlayError."""
        error = AuthenticationError("Auth failed")
        assert isinstance(error, RolePlayError)
        assert isinstance(error, Exception)
        assert str(error) == "Auth failed"
    
    def test_authorization_error_inheritance(self):
        """Test AuthorizationError inherits from RolePlayError."""
        error = AuthorizationError("Not authorized")
        assert isinstance(error, RolePlayError)
        assert isinstance(error, Exception)
    
    def test_token_errors_inherit_from_authentication_error(self):
        """Test token-related errors inherit from AuthenticationError."""
        invalid_error = InvalidTokenError("Invalid token")
        expired_error = TokenExpiredError("Token expired")
        
        assert isinstance(invalid_error, AuthenticationError)
        assert isinstance(invalid_error, RolePlayError)
        
        assert isinstance(expired_error, AuthenticationError)
        assert isinstance(expired_error, RolePlayError)
    
    def test_permission_denied_inherits_from_authorization_error(self):
        """Test PermissionDeniedError inherits from AuthorizationError."""
        error = PermissionDeniedError("Access denied")
        assert isinstance(error, AuthorizationError)
        assert isinstance(error, RolePlayError)
    
    def test_all_errors_inherit_from_base(self):
        """Test all custom exceptions inherit from RolePlayError."""
        exceptions_to_test = [
            UserNotFoundError("User not found"),
            StorageError("Storage failed"),
            ConfigurationError("Config invalid"),
            ValidationError("Validation failed"),
            ResourceNotFoundError("Resource missing")
        ]
        
        for exception in exceptions_to_test:
            assert isinstance(exception, RolePlayError)
            assert isinstance(exception, Exception)


class TestExceptionMessages:
    """Test exception message handling."""
    
    def test_exception_with_message(self):
        """Test exceptions can be created with custom messages."""
        message = "Custom error message"
        error = AuthenticationError(message)
        assert str(error) == message
    
    def test_exception_without_message(self):
        """Test exceptions can be created without messages."""
        error = StorageError()
        # Should not raise an error when converting to string
        str(error)
    
    def test_exception_with_empty_message(self):
        """Test exceptions with empty messages."""
        error = ValidationError("")
        assert str(error) == ""


class TestExceptionUsagePatterms:
    """Test typical usage patterns for exceptions."""
    
    def test_raising_and_catching_authentication_error(self):
        """Test raising and catching AuthenticationError."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError("Login failed")
        
        assert "Login failed" in str(exc_info.value)
    
    def test_raising_and_catching_base_error(self):
        """Test catching specific errors as base RolePlayError."""
        with pytest.raises(RolePlayError):
            raise UserNotFoundError("User does not exist")
    
    def test_multiple_exception_types(self):
        """Test catching multiple related exception types."""
        def risky_auth_operation(operation_type: str):
            if operation_type == "invalid_token":
                raise InvalidTokenError("Token is invalid")
            elif operation_type == "expired_token":
                raise TokenExpiredError("Token has expired")
            elif operation_type == "user_not_found":
                raise UserNotFoundError("User does not exist")
        
        # Test catching specific token errors
        with pytest.raises(AuthenticationError):
            risky_auth_operation("invalid_token")
        
        with pytest.raises(AuthenticationError):
            risky_auth_operation("expired_token")
        
        # Test catching any authentication-related error
        with pytest.raises(RolePlayError):
            risky_auth_operation("user_not_found")
    
    def test_exception_chaining(self):
        """Test exception chaining for debugging."""
        def inner_function():
            raise StorageError("Database connection failed")
        
        def outer_function():
            try:
                inner_function()
            except StorageError as e:
                raise AuthenticationError("Auth failed due to storage issue") from e
        
        with pytest.raises(AuthenticationError) as exc_info:
            outer_function()
        
        # Check that the original exception is preserved
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, StorageError)


class TestSpecificExceptions:
    """Test specific exception types for their intended use cases."""
    
    def test_authentication_error_scenarios(self):
        """Test AuthenticationError for various auth scenarios."""
        scenarios = [
            "Invalid username or password",
            "Account is locked",
            "Two-factor authentication required",
            "OAuth provider rejected request"
        ]
        
        for scenario in scenarios:
            error = AuthenticationError(scenario)
            assert str(error) == scenario
            assert isinstance(error, RolePlayError)
    
    def test_authorization_error_scenarios(self):
        """Test AuthorizationError for various authorization scenarios."""
        scenarios = [
            "Insufficient privileges",
            "Resource access denied",
            "Admin role required",
            "Rate limit exceeded"
        ]
        
        for scenario in scenarios:
            error = AuthorizationError(scenario)
            assert str(error) == scenario
            assert isinstance(error, RolePlayError)
    
    def test_storage_error_scenarios(self):
        """Test StorageError for various storage scenarios."""
        scenarios = [
            "Database connection timeout",
            "File system permission denied",
            "Disk space full",
            "Corrupted data detected"
        ]
        
        for scenario in scenarios:
            error = StorageError(scenario)
            assert str(error) == scenario
            assert isinstance(error, RolePlayError)
    
    def test_configuration_error_scenarios(self):
        """Test ConfigurationError for various config scenarios."""
        scenarios = [
            "Missing required environment variable",
            "Invalid configuration format",
            "Configuration file not found",
            "Conflicting configuration values"
        ]
        
        for scenario in scenarios:
            error = ConfigurationError(scenario)
            assert str(error) == scenario
            assert isinstance(error, RolePlayError)