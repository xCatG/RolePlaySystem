"""Test data factories for creating test objects."""

import uuid
from typing import Dict, Any, Optional

from role_play.common.models import User, UserAuthMethod, SessionData, UserRole, AuthProvider
from role_play.common.time_utils import utc_now


class UserFactory:
    """Factory for creating User test objects."""
    
    @staticmethod
    def create(
        id: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        role: UserRole = UserRole.USER,
        preferred_language: str = "en",
        is_active: bool = True,
        **kwargs
    ) -> User:
        """Create a User instance with sensible defaults."""
        now = utc_now()
        return User(
            id=id or str(uuid.uuid4()),
            username=username or f"user_{uuid.uuid4().hex[:8]}",
            email=email or f"test_{uuid.uuid4().hex[:8]}@example.com",
            role=role,
            preferred_language=preferred_language,
            created_at=kwargs.get("created_at", now),
            updated_at=kwargs.get("updated_at", now),
            is_active=is_active
        )
    
    @staticmethod
    def create_admin(**kwargs) -> User:
        """Create an admin User instance."""
        return UserFactory.create(role=UserRole.ADMIN, **kwargs)


class UserAuthMethodFactory:
    """Factory for creating UserAuthMethod test objects."""
    
    @staticmethod
    def create(
        id: Optional[str] = None,
        user_id: Optional[str] = None,
        provider: AuthProvider = AuthProvider.LOCAL,
        provider_user_id: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
        **kwargs
    ) -> UserAuthMethod:
        """Create a UserAuthMethod instance with sensible defaults."""
        return UserAuthMethod(
            id=id or str(uuid.uuid4()),
            user_id=user_id or str(uuid.uuid4()),
            provider=provider,
            provider_user_id=provider_user_id or f"provider_user_{uuid.uuid4().hex[:8]}",
            credentials=credentials or {"password_hash": "hashed_password"},
            created_at=kwargs.get("created_at", utc_now()),
            is_active=is_active
        )
    
    @staticmethod
    def create_local_auth(user: User, password_hash: str = "hashed_password") -> UserAuthMethod:
        """Create a local auth method for a user."""
        return UserAuthMethodFactory.create(
            user_id=user.id,
            provider=AuthProvider.LOCAL,
            provider_user_id=user.username,
            credentials={"password_hash": password_hash}
        )
    
    @staticmethod
    def create_google_auth(user: User, google_user_id: str = None, **oauth_data) -> UserAuthMethod:
        """Create a Google OAuth auth method for a user."""
        credentials = {
            "email": oauth_data.get("email", user.email),
            "name": oauth_data.get("name", user.username),
            "picture": oauth_data.get("picture", "https://example.com/avatar.jpg"),
            **oauth_data
        }
        return UserAuthMethodFactory.create(
            user_id=user.id,
            provider=AuthProvider.GOOGLE,
            provider_user_id=google_user_id or f"google_{uuid.uuid4().hex}",
            credentials=credentials
        )


class SessionDataFactory:
    """Factory for creating SessionData test objects."""
    
    @staticmethod
    def create(
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> SessionData:
        """Create a SessionData instance with sensible defaults."""
        now = utc_now()
        return SessionData(
            session_id=session_id or str(uuid.uuid4()),
            user_id=user_id or str(uuid.uuid4()),
            created_at=kwargs.get("created_at", now),
            last_activity=kwargs.get("last_activity", now),
            metadata=metadata or {"ip": "127.0.0.1", "user_agent": "test"}
        )


class TestDataBuilder:
    """Builder for creating complete test scenarios."""
    
    @staticmethod
    def create_user_with_local_auth(username: str = None, password_hash: str = "hashed_password"):
        """Create a user with local authentication method."""
        user = UserFactory.create(username=username)
        auth_method = UserAuthMethodFactory.create_local_auth(user, password_hash)
        return user, auth_method
    
    @staticmethod
    def create_user_with_session(username: str = None):
        """Create a user with an active session."""
        user = UserFactory.create(username=username)
        session = SessionDataFactory.create(user_id=user.id)
        return user, session
    
    @staticmethod
    def create_complete_user_scenario(username: str = None):
        """Create a user with both auth method and session."""
        user = UserFactory.create(username=username)
        auth_method = UserAuthMethodFactory.create_local_auth(user)
        session = SessionDataFactory.create(user_id=user.id)
        return user, auth_method, session