"""Unit tests for common.models module."""

import pytest
from pydantic import ValidationError

from role_play.common.models import (
    User, UserAuthMethod, TokenData, SessionData,
    UserRole, AuthProvider
)
from role_play.common.time_utils import utc_now
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from fixtures.factories import UserFactory, UserAuthMethodFactory, SessionDataFactory


class TestUserRole:
    """Test UserRole enum."""
    
    def test_user_role_values(self):
        """Test UserRole enum values."""
        assert UserRole.ADMIN == "admin"
        assert UserRole.USER == "user"
    
    def test_user_role_serialization(self):
        """Test UserRole serialization in models."""
        user = UserFactory.create(role=UserRole.ADMIN)
        assert user.role == UserRole.ADMIN
        assert user.model_dump()["role"] == "admin"


class TestAuthProvider:
    """Test AuthProvider enum."""
    
    def test_auth_provider_values(self):
        """Test AuthProvider enum values."""
        assert AuthProvider.LOCAL == "local"
        assert AuthProvider.GOOGLE == "google"
    
    def test_auth_provider_serialization(self):
        """Test AuthProvider serialization in models."""
        auth_method = UserAuthMethodFactory.create(provider=AuthProvider.GOOGLE)
        assert auth_method.provider == AuthProvider.GOOGLE
        assert auth_method.model_dump()["provider"] == "google"


class TestUser:
    """Test User model."""
    
    def test_user_creation_with_defaults(self):
        """Test User creation with default values."""
        now = utc_now()
        user = User(
            id="test-123",
            username="testuser",
            created_at=now,
            updated_at=now
        )
        
        assert user.id == "test-123"
        assert user.username == "testuser"
        assert user.email is None
        assert user.role == UserRole.USER
        assert user.preferred_language == "en"  # Default language
        assert user.is_active is True
        assert user.created_at == now
        assert user.updated_at == now
    
    def test_user_creation_with_all_fields(self):
        """Test User creation with all fields specified."""
        now = utc_now()
        user = User(
            id="test-456",
            username="adminuser",
            email="admin@example.com",
            role=UserRole.ADMIN,
            preferred_language="zh-TW",
            created_at=now,
            updated_at=now,
            is_active=False
        )
        
        assert user.id == "test-456"
        assert user.username == "adminuser"
        assert user.email == "admin@example.com"
        assert user.role == UserRole.ADMIN
        assert user.preferred_language == "zh-TW"
        assert user.is_active is False
    
    def test_user_validation_required_fields(self):
        """Test User validation for required fields."""
        with pytest.raises(ValidationError) as exc_info:
            User()
        
        errors = exc_info.value.errors()
        required_fields = {"id", "username", "created_at", "updated_at"}
        error_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        assert required_fields.issubset(error_fields)
    
    def test_user_serialization(self):
        """Test User model serialization."""
        user = UserFactory.create(
            id="test-789",
            username="serialtest",
            email="serial@example.com"
        )
        
        data = user.model_dump()
        assert data["id"] == "test-789"
        assert data["username"] == "serialtest"
        assert data["email"] == "serial@example.com"
        assert data["role"] == "user"
        assert data["preferred_language"] == "en"
        assert data["is_active"] is True


class TestUserAuthMethod:
    """Test UserAuthMethod model."""
    
    def test_auth_method_creation_with_defaults(self):
        """Test UserAuthMethod creation with default values."""
        now = utc_now()
        auth_method = UserAuthMethod(
            id="auth-123",
            user_id="user-123",
            provider=AuthProvider.LOCAL,
            provider_user_id="testuser",
            created_at=now
        )
        
        assert auth_method.id == "auth-123"
        assert auth_method.user_id == "user-123"
        assert auth_method.provider == AuthProvider.LOCAL
        assert auth_method.provider_user_id == "testuser"
        assert auth_method.credentials == {}
        assert auth_method.is_active is True
        assert auth_method.created_at == now
    
    def test_auth_method_with_credentials(self):
        """Test UserAuthMethod with credentials."""
        credentials = {"password_hash": "hashed_pw", "salt": "random_salt"}
        auth_method = UserAuthMethodFactory.create(credentials=credentials)
        
        assert auth_method.credentials == credentials
    
    def test_auth_method_validation_required_fields(self):
        """Test UserAuthMethod validation for required fields."""
        with pytest.raises(ValidationError) as exc_info:
            UserAuthMethod()
        
        errors = exc_info.value.errors()
        required_fields = {"id", "user_id", "provider", "provider_user_id", "created_at"}
        error_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        assert required_fields.issubset(error_fields)
    
    def test_auth_method_serialization(self):
        """Test UserAuthMethod model serialization."""
        auth_method = UserAuthMethodFactory.create(
            id="auth-456",
            provider=AuthProvider.GOOGLE,
            credentials={"email": "test@google.com"}
        )
        
        data = auth_method.model_dump()
        assert data["id"] == "auth-456"
        assert data["provider"] == "google"
        assert data["credentials"] == {"email": "test@google.com"}
        assert data["is_active"] is True


class TestTokenData:
    """Test TokenData model."""
    
    def test_token_data_creation(self):
        """Test TokenData creation."""
        token_data = TokenData(
            user_id="user-123",
            username="testuser",
            role=UserRole.ADMIN,
            exp=1234567890
        )
        
        assert token_data.user_id == "user-123"
        assert token_data.username == "testuser"
        assert token_data.role == UserRole.ADMIN
        assert token_data.exp == 1234567890
    
    def test_token_data_validation_required_fields(self):
        """Test TokenData validation for required fields."""
        with pytest.raises(ValidationError) as exc_info:
            TokenData()
        
        errors = exc_info.value.errors()
        required_fields = {"user_id", "username", "role", "exp"}
        error_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        assert required_fields.issubset(error_fields)
    
    def test_token_data_serialization(self):
        """Test TokenData model serialization."""
        token_data = TokenData(
            user_id="user-456",
            username="tokentest",
            role=UserRole.USER,
            exp=9876543210
        )
        
        data = token_data.model_dump()
        assert data["user_id"] == "user-456"
        assert data["username"] == "tokentest"
        assert data["role"] == "user"
        assert data["exp"] == 9876543210


class TestSessionData:
    """Test SessionData model."""
    
    def test_session_data_creation_with_defaults(self):
        """Test SessionData creation with default values."""
        now = utc_now()
        session = SessionData(
            session_id="session-123",
            user_id="user-123",
            created_at=now,
            last_activity=now
        )
        
        assert session.session_id == "session-123"
        assert session.user_id == "user-123"
        assert session.metadata == {}
        assert session.created_at == now
        assert session.last_activity == now
    
    def test_session_data_with_metadata(self):
        """Test SessionData with metadata."""
        metadata = {"ip": "192.168.1.1", "user_agent": "Mozilla/5.0"}
        session = SessionDataFactory.create(metadata=metadata)
        
        assert session.metadata == metadata
    
    def test_session_data_validation_required_fields(self):
        """Test SessionData validation for required fields."""
        with pytest.raises(ValidationError) as exc_info:
            SessionData()
        
        errors = exc_info.value.errors()
        required_fields = {"session_id", "user_id", "created_at", "last_activity"}
        error_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        assert required_fields.issubset(error_fields)
    
    def test_session_data_serialization(self):
        """Test SessionData model serialization."""
        session = SessionDataFactory.create(
            session_id="session-789",
            metadata={"device": "mobile"}
        )
        
        data = session.model_dump()
        assert data["session_id"] == "session-789"
        assert data["metadata"] == {"device": "mobile"}


class TestModelFactories:
    """Test our factory functions."""
    
    def test_user_factory_creates_unique_users(self):
        """Test that UserFactory creates unique users."""
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        
        assert user1.id != user2.id
        assert user1.username != user2.username
        assert user1.email != user2.email
    
    def test_user_factory_admin_creation(self):
        """Test that UserFactory can create admin users."""
        admin = UserFactory.create_admin(username="admin_test")
        
        assert admin.role == UserRole.ADMIN
        assert admin.username == "admin_test"
    
    def test_auth_method_factory_local_auth(self):
        """Test UserAuthMethodFactory for local auth."""
        user = UserFactory.create()
        auth_method = UserAuthMethodFactory.create_local_auth(user, "custom_hash")
        
        assert auth_method.user_id == user.id
        assert auth_method.provider == AuthProvider.LOCAL
        assert auth_method.provider_user_id == user.username
        assert auth_method.credentials["password_hash"] == "custom_hash"
    
    def test_auth_method_factory_google_auth(self):
        """Test UserAuthMethodFactory for Google OAuth."""
        user = UserFactory.create(email="test@example.com")
        auth_method = UserAuthMethodFactory.create_google_auth(
            user, 
            google_user_id="google_123",
            name="Test User"
        )
        
        assert auth_method.user_id == user.id
        assert auth_method.provider == AuthProvider.GOOGLE
        assert auth_method.provider_user_id == "google_123"
        assert auth_method.credentials["email"] == "test@example.com"
        assert auth_method.credentials["name"] == "Test User"


class TestLanguageModels:
    """Test language-related models."""
    
    def test_user_with_language_preference(self):
        """Test User model with language preference."""
        now = utc_now()
        user = User(
            id="test-lang-123",
            username="multilang_user",
            email="multilang@example.com",
            role=UserRole.USER,
            preferred_language="zh-TW",
            created_at=now,
            updated_at=now
        )
        
        assert user.preferred_language == "zh-TW"
        
        # Test serialization includes language
        data = user.model_dump()
        assert data["preferred_language"] == "zh-TW"
    
    def test_update_language_request_validation(self):
        """Test UpdateLanguageRequest model."""
        from role_play.common.models import UpdateLanguageRequest
        
        # Valid language request
        request = UpdateLanguageRequest(language="zh-TW")
        assert request.language == "zh-TW"
        
        # Test serialization
        data = request.model_dump()
        assert data["language"] == "zh-TW"
        
        # Test validation of required field
        with pytest.raises(ValidationError) as exc_info:
            UpdateLanguageRequest()
        
        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        assert "language" in error_fields
    
    def test_update_language_response(self):
        """Test UpdateLanguageResponse model."""
        from role_play.common.models import UpdateLanguageResponse
        
        # Create response
        response = UpdateLanguageResponse(
            success=True,
            language="zh-TW",
            message="Language updated successfully"
        )
        
        assert response.success is True
        assert response.language == "zh-TW"
        assert response.message == "Language updated successfully"
        
        # Test serialization
        data = response.model_dump()
        assert data["success"] is True
        assert data["language"] == "zh-TW"
        assert data["message"] == "Language updated successfully"
    
    def test_user_factory_with_language(self):
        """Test UserFactory can create users with specific languages."""
        # Test creating user with Chinese preference
        user = UserFactory.create(preferred_language="zh-TW")
        assert user.preferred_language == "zh-TW"
        
        # Test creating admin with Japanese preference
        admin = UserFactory.create_admin(preferred_language="ja")
        assert admin.role == UserRole.ADMIN
        assert admin.preferred_language == "ja"