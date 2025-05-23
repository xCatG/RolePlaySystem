"""Integration tests for AuthManager."""

import pytest
import tempfile
import jwt
from datetime import datetime, timedelta
from pathlib import Path

from role_play.common.auth import AuthManager
from role_play.common.storage import FileStorage
from role_play.common.models import User, UserAuthMethod, UserRole, AuthProvider
from role_play.common.exceptions import (
    AuthenticationError, UserNotFoundError, InvalidTokenError, TokenExpiredError
)

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from fixtures.factories import UserFactory, TestDataBuilder


@pytest.mark.integration
class TestAuthManagerUserRegistration:
    """Integration tests for user registration workflows."""
    
    @pytest.mark.asyncio
    async def test_register_user_with_password_complete_flow(self):
        """Test complete user registration with password."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(
                storage=storage,
                jwt_secret_key="test_secret_for_integration",
                access_token_expire_minutes=30
            )
            
            # Register user
            user, token = await auth_manager.register_user(
                username="integration_user",
                email="integration@example.com",
                password="secure_password_123"
            )
            
            # Verify user was created correctly
            assert user.username == "integration_user"
            assert user.email == "integration@example.com"
            assert user.role == UserRole.USER
            assert user.is_active is True
            assert token is not None
            
            # Verify user persisted in storage
            stored_user = await storage.get_user(user.id)
            assert stored_user is not None
            assert stored_user.username == "integration_user"
            
            # Verify auth method was created
            auth_methods = await storage.get_user_auth_methods(user.id)
            assert len(auth_methods) == 1
            assert auth_methods[0].provider == AuthProvider.LOCAL
            assert auth_methods[0].provider_user_id == "integration_user"
            assert "password_hash" in auth_methods[0].credentials
            
            # Verify token is valid
            token_data = auth_manager.verify_token(token)
            assert token_data.user_id == user.id
            assert token_data.username == user.username
            assert token_data.role == UserRole.USER
    
    @pytest.mark.asyncio
    async def test_register_user_without_password(self):
        """Test user registration without password (OAuth preparation)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register user without password
            user, token = await auth_manager.register_user(
                username="oauth_user",
                email="oauth@example.com"
            )
            
            # User should be created
            assert user.username == "oauth_user"
            assert token is not None
            
            # No auth method should be created without password
            auth_methods = await storage.get_user_auth_methods(user.id)
            assert len(auth_methods) == 0
    
    @pytest.mark.asyncio
    async def test_register_duplicate_username(self):
        """Test registration with duplicate username fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register first user
            await auth_manager.register_user(
                username="duplicate_user",
                password="password1"
            )
            
            # Try to register with same username
            with pytest.raises(AuthenticationError) as exc_info:
                await auth_manager.register_user(
                    username="duplicate_user",
                    password="password2"
                )
            
            assert "User already exists" in str(exc_info.value)


@pytest.mark.integration
class TestAuthManagerAuthentication:
    """Integration tests for user authentication workflows."""
    
    @pytest.mark.asyncio
    async def test_authenticate_user_complete_flow(self):
        """Test complete user authentication flow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register user first
            original_user, _ = await auth_manager.register_user(
                username="auth_test_user",
                email="auth@example.com",
                password="my_secure_password"
            )
            
            # Authenticate user
            auth_user, auth_token = await auth_manager.authenticate_user(
                username="auth_test_user",
                password="my_secure_password"
            )
            
            # Verify authenticated user
            assert auth_user.id == original_user.id
            assert auth_user.username == "auth_test_user"
            assert auth_user.email == "auth@example.com"
            
            # Verify token
            assert auth_token is not None
            token_data = auth_manager.verify_token(auth_token)
            assert token_data.user_id == original_user.id
            assert token_data.username == "auth_test_user"
    
    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self):
        """Test authentication with wrong password fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register user
            await auth_manager.register_user(
                username="wrong_pass_user",
                password="correct_password"
            )
            
            # Try to authenticate with wrong password
            with pytest.raises(AuthenticationError) as exc_info:
                await auth_manager.authenticate_user(
                    username="wrong_pass_user",
                    password="wrong_password"
                )
            
            assert "Invalid credentials" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self):
        """Test authentication with non-existent user fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Try to authenticate non-existent user
            with pytest.raises(UserNotFoundError) as exc_info:
                await auth_manager.authenticate_user(
                    username="nonexistent_user",
                    password="any_password"
                )
            
            assert "User not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self):
        """Test authentication with inactive user fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register and then deactivate user
            user, _ = await auth_manager.register_user(
                username="inactive_user",
                password="password"
            )
            
            # Deactivate user
            user.is_active = False
            await storage.update_user(user)
            
            # Try to authenticate
            with pytest.raises(UserNotFoundError) as exc_info:
                await auth_manager.authenticate_user(
                    username="inactive_user",
                    password="password"
                )
            
            assert "User not found or inactive" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_authenticate_user_without_local_auth(self):
        """Test authentication fails for user without local auth method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register user without password (no local auth method)
            await auth_manager.register_user(
                username="oauth_only_user",
                email="oauth@example.com"
            )
            
            # Try to authenticate with password
            with pytest.raises(AuthenticationError) as exc_info:
                await auth_manager.authenticate_user(
                    username="oauth_only_user",
                    password="any_password"
                )
            
            assert "Local authentication not configured" in str(exc_info.value)


@pytest.mark.integration
class TestAuthManagerTokenOperations:
    """Integration tests for token operations."""
    
    @pytest.mark.asyncio
    async def test_get_user_by_token_complete_flow(self):
        """Test getting user by token."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register user
            original_user, token = await auth_manager.register_user(
                username="token_user",
                password="password"
            )
            
            # Get user by token
            token_user = await auth_manager.get_user_by_token(token)
            
            assert token_user.id == original_user.id
            assert token_user.username == "token_user"
    
    @pytest.mark.asyncio
    async def test_verify_token_invalid_token(self):
        """Test token verification with invalid token."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Try to verify invalid token
            with pytest.raises(InvalidTokenError):
                auth_manager.verify_token("invalid.token.here")
    
    @pytest.mark.asyncio
    async def test_verify_token_wrong_secret(self):
        """Test token verification with wrong secret."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager1 = AuthManager(storage, "secret1")
            auth_manager2 = AuthManager(storage, "secret2")
            
            # Create token with first auth manager
            user, token = await auth_manager1.register_user(
                username="token_test",
                password="password"
            )
            
            # Try to verify with second auth manager (different secret)
            with pytest.raises(InvalidTokenError):
                auth_manager2.verify_token(token)
    
    @pytest.mark.asyncio
    async def test_verify_token_expired(self):
        """Test token verification with expired token."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            # Create auth manager with very short token expiry
            auth_manager = AuthManager(
                storage, 
                "test_secret",
                access_token_expire_minutes=-1  # Already expired
            )
            
            # Register user (this will create an expired token)
            user, token = await auth_manager.register_user(
                username="expired_user",
                password="password"
            )
            
            # Try to verify expired token
            with pytest.raises(TokenExpiredError):
                auth_manager.verify_token(token)
    
    @pytest.mark.asyncio
    async def test_get_user_by_token_inactive_user(self):
        """Test get_user_by_token with inactive user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register user
            user, token = await auth_manager.register_user(
                username="inactive_token_user",
                password="password"
            )
            
            # Deactivate user
            user.is_active = False
            await storage.update_user(user)
            
            # Try to get user by token
            with pytest.raises(UserNotFoundError):
                await auth_manager.get_user_by_token(token)


@pytest.mark.integration
class TestAuthManagerOAuthIntegration:
    """Integration tests for OAuth authentication."""
    
    @pytest.mark.asyncio
    async def test_authenticate_oauth_user_new_user(self):
        """Test OAuth authentication for new user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Simulate OAuth user info
            oauth_user_info = {
                "email": "oauth@google.com",
                "username": "oauth_user",
                "name": "OAuth User",
                "picture": "https://example.com/avatar.jpg"
            }
            
            # Authenticate OAuth user
            user, token = await auth_manager.authenticate_oauth_user(
                provider=AuthProvider.GOOGLE,
                provider_user_id="google_123456",
                user_info=oauth_user_info
            )
            
            # Verify user was created
            assert user.username == "oauth_user"
            assert user.email == "oauth@google.com"
            assert token is not None
            
            # Verify OAuth auth method was created
            auth_methods = await storage.get_user_auth_methods(user.id)
            assert len(auth_methods) == 1
            assert auth_methods[0].provider == AuthProvider.GOOGLE
            assert auth_methods[0].provider_user_id == "google_123456"
            assert auth_methods[0].credentials["email"] == "oauth@google.com"
            assert auth_methods[0].credentials["name"] == "OAuth User"
    
    @pytest.mark.asyncio
    async def test_authenticate_oauth_user_existing_user(self):
        """Test OAuth authentication for existing user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # First OAuth login - creates user
            oauth_user_info = {
                "email": "returning@google.com",
                "username": "returning_user",
                "name": "Returning User"
            }
            
            user1, token1 = await auth_manager.authenticate_oauth_user(
                provider=AuthProvider.GOOGLE,
                provider_user_id="google_existing",
                user_info=oauth_user_info
            )
            
            # Second OAuth login - should return same user
            updated_oauth_info = {
                "email": "returning@google.com",
                "username": "returning_user",
                "name": "Updated Name",  # Name changed
                "picture": "new_avatar.jpg"  # New field
            }
            
            user2, token2 = await auth_manager.authenticate_oauth_user(
                provider=AuthProvider.GOOGLE,
                provider_user_id="google_existing",
                user_info=updated_oauth_info
            )
            
            # Should be same user
            assert user1.id == user2.id
            assert user1.username == user2.username
            
            # Credentials should be updated
            auth_method = await storage.get_user_auth_method(
                AuthProvider.GOOGLE, "google_existing"
            )
            assert auth_method.credentials["name"] == "Updated Name"
            assert auth_method.credentials["picture"] == "new_avatar.jpg"
    
    @pytest.mark.asyncio
    async def test_authenticate_oauth_user_username_collision(self):
        """Test OAuth authentication with username collision."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Create regular user first
            await auth_manager.register_user(
                username="collision_user",
                password="password"
            )
            
            # OAuth user with same preferred username
            oauth_user_info = {
                "email": "oauth_collision@google.com",
                "username": "collision_user"  # Same as existing user
            }
            
            user, token = await auth_manager.authenticate_oauth_user(
                provider=AuthProvider.GOOGLE,
                provider_user_id="google_collision",
                user_info=oauth_user_info
            )
            
            # Username should be modified to avoid collision
            assert user.username == "collision_user_1"
            assert user.email == "oauth_collision@google.com"


@pytest.mark.integration
class TestAuthManagerPasswordManagement:
    """Integration tests for password management."""
    
    @pytest.mark.asyncio
    async def test_change_password_complete_flow(self):
        """Test complete password change workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Register user
            user, _ = await auth_manager.register_user(
                username="password_change_user",
                password="old_password"
            )
            
            # Change password
            await auth_manager.change_password(
                user_id=user.id,
                old_password="old_password",
                new_password="new_password"
            )
            
            # Verify old password no longer works
            with pytest.raises(AuthenticationError):
                await auth_manager.authenticate_user(
                    username="password_change_user",
                    password="old_password"
                )
            
            # Verify new password works
            auth_user, token = await auth_manager.authenticate_user(
                username="password_change_user",
                password="new_password"
            )
            assert auth_user.id == user.id
    
    @pytest.mark.asyncio
    async def test_change_password_wrong_old_password(self):
        """Test password change with wrong old password."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            user, _ = await auth_manager.register_user(
                username="wrong_old_pass",
                password="correct_password"
            )
            
            # Try to change with wrong old password
            with pytest.raises(AuthenticationError) as exc_info:
                await auth_manager.change_password(
                    user_id=user.id,
                    old_password="wrong_old_password",
                    new_password="new_password"
                )
            
            assert "Invalid current password" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_change_password_user_not_found(self):
        """Test password change for non-existent user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            with pytest.raises(UserNotFoundError):
                await auth_manager.change_password(
                    user_id="nonexistent_user",
                    old_password="old_pass",
                    new_password="new_pass"
                )
    
    @pytest.mark.asyncio
    async def test_change_password_no_local_auth(self):
        """Test password change for user without local auth."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # Create OAuth-only user
            user, _ = await auth_manager.authenticate_oauth_user(
                provider=AuthProvider.GOOGLE,
                provider_user_id="google_oauth_only",
                user_info={"email": "oauth@google.com", "username": "oauth_user"}
            )
            
            # Try to change password
            with pytest.raises(AuthenticationError) as exc_info:
                await auth_manager.change_password(
                    user_id=user.id,
                    old_password="any_password",
                    new_password="new_password"
                )
            
            assert "Local authentication not configured" in str(exc_info.value)


@pytest.mark.integration
@pytest.mark.slow
class TestAuthManagerCompleteScenarios:
    """Integration tests for complete authentication scenarios."""
    
    @pytest.mark.asyncio
    async def test_multi_user_multi_auth_scenario(self):
        """Test complex scenario with multiple users and auth methods."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_manager = AuthManager(storage, "test_secret")
            
            # User 1: Local auth only
            user1, token1 = await auth_manager.register_user(
                username="local_user",
                password="local_password"
            )
            
            # User 2: OAuth only
            user2, token2 = await auth_manager.authenticate_oauth_user(
                provider=AuthProvider.GOOGLE,
                provider_user_id="google_oauth",
                user_info={"email": "oauth@google.com", "username": "oauth_user"}
            )
            
            # User 3: Both local and OAuth (register then add OAuth)
            user3, token3 = await auth_manager.register_user(
                username="hybrid_user",
                password="hybrid_password"
            )
            
            # Add OAuth to user3 by creating another OAuth user with same email
            # This simulates linking accounts (would need additional business logic)
            
            # Verify all users can authenticate with their respective methods
            local_auth = await auth_manager.authenticate_user("local_user", "local_password")
            assert local_auth[0].id == user1.id
            
            oauth_auth = await auth_manager.authenticate_oauth_user(
                provider=AuthProvider.GOOGLE,
                provider_user_id="google_oauth",
                user_info={"email": "oauth@google.com", "username": "oauth_user"}
            )
            assert oauth_auth[0].id == user2.id
            
            hybrid_auth = await auth_manager.authenticate_user("hybrid_user", "hybrid_password")
            assert hybrid_auth[0].id == user3.id
            
            # Verify tokens work for all users
            token_user1 = await auth_manager.get_user_by_token(token1)
            token_user2 = await auth_manager.get_user_by_token(token2)
            token_user3 = await auth_manager.get_user_by_token(token3)
            
            assert token_user1.id == user1.id
            assert token_user2.id == user2.id
            assert token_user3.id == user3.id