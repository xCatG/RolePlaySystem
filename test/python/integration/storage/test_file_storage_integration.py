"""Integration tests for FileStorage implementation."""

import pytest
import tempfile
import uuid
from pathlib import Path

from role_play.common.storage import FileStorage, FileStorageConfig
from role_play.common.models import User, UserAuthMethod, SessionData, UserRole, AuthProvider
from role_play.common.exceptions import StorageError
from role_play.common.time_utils import utc_now

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from fixtures.factories import UserFactory, UserAuthMethodFactory, SessionDataFactory, TestDataBuilder
from fixtures.helpers import assert_user_equal, assert_auth_method_equal, assert_session_equal


@pytest.mark.integration
class TestFileStorageUserIntegration:
    """Integration tests for user operations in FileStorage."""
    
    @pytest.mark.asyncio
    async def test_complete_user_lifecycle(self):
        """Test full user lifecycle: create, read, update, delete."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create user with unique ID to avoid conflicts between test runs
            unique_id = f"lifecycle-{uuid.uuid4().hex[:8]}"
            original_user = UserFactory.create(
                id=unique_id,
                username=f"lifecycle_user_{unique_id}",
                email=f"lifecycle_{unique_id}@example.com"
            )
            
            created_user = await storage.create_user(original_user)
            assert_user_equal(created_user, original_user)
            
            # Read user by ID
            retrieved_user = await storage.get_user(unique_id)
            assert retrieved_user is not None
            assert_user_equal(retrieved_user, original_user)
            
            # Read user by username
            retrieved_by_name = await storage.get_user_by_username(f"lifecycle_user_{unique_id}")
            assert retrieved_by_name is not None
            assert_user_equal(retrieved_by_name, original_user)
            
            # Update user
            retrieved_user.email = "updated@example.com"
            retrieved_user.role = UserRole.ADMIN
            updated_user = await storage.update_user(retrieved_user)
            
            assert updated_user.email == "updated@example.com"
            assert updated_user.role == UserRole.ADMIN
            assert updated_user.updated_at > original_user.updated_at
            
            # Verify update persisted
            final_user = await storage.get_user(unique_id)
            assert final_user.email == "updated@example.com"
            assert final_user.role == UserRole.ADMIN
            
            # Delete user
            deleted = await storage.delete_user(unique_id)
            assert deleted is True
            
            # Verify user is gone
            missing_user = await storage.get_user(unique_id)
            assert missing_user is None
    
    @pytest.mark.asyncio
    async def test_multiple_users_isolation(self):
        """Test that multiple users don't interfere with each other."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create multiple users
            user1 = UserFactory.create(id="user1", username="user_one")
            user2 = UserFactory.create(id="user2", username="user_two")
            user3 = UserFactory.create(id="user3", username="user_three")
            
            await storage.create_user(user1)
            await storage.create_user(user2)
            await storage.create_user(user3)
            
            # Verify all users exist independently
            retrieved1 = await storage.get_user("user1")
            retrieved2 = await storage.get_user("user2")
            retrieved3 = await storage.get_user("user3")
            
            assert retrieved1.username == "user_one"
            assert retrieved2.username == "user_two"
            assert retrieved3.username == "user_three"
            
            # Delete one user, others should remain
            await storage.delete_user("user2")
            
            assert await storage.get_user("user1") is not None
            assert await storage.get_user("user2") is None
            assert await storage.get_user("user3") is not None
    
    @pytest.mark.asyncio
    async def test_username_uniqueness_not_enforced(self):
        """Test that storage doesn't enforce username uniqueness (business logic responsibility)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create two users with same username but different IDs
            user1 = UserFactory.create(id="user1", username="duplicate")
            user2 = UserFactory.create(id="user2", username="duplicate")
            
            # Both should be created successfully
            await storage.create_user(user1)
            await storage.create_user(user2)
            
            # get_user_by_username should return the first one found
            retrieved = await storage.get_user_by_username("duplicate")
            assert retrieved is not None
            # It will return one of them (implementation dependent which one)
            assert retrieved.username == "duplicate"


@pytest.mark.integration
class TestFileStorageAuthMethodIntegration:
    """Integration tests for auth method operations in FileStorage."""
    
    @pytest.mark.asyncio
    async def test_complete_auth_method_lifecycle(self):
        """Test full auth method lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create user first with unique ID
            unique_user_id = f"auth-user-{uuid.uuid4().hex[:8]}"
            user = UserFactory.create(id=unique_user_id)
            await storage.create_user(user)
            
            # Create auth method
            auth_method = UserAuthMethodFactory.create_local_auth(
                user, password_hash="hashed_password_123"
            )
            
            created_auth = await storage.create_user_auth_method(auth_method)
            assert_auth_method_equal(created_auth, auth_method)
            
            # Retrieve auth method by provider
            retrieved_auth = await storage.get_user_auth_method(
                AuthProvider.LOCAL, user.username
            )
            assert retrieved_auth is not None
            assert_auth_method_equal(retrieved_auth, auth_method)
            
            # Get all auth methods for user
            user_auths = await storage.get_user_auth_methods(user.id)
            assert len(user_auths) == 1
            assert_auth_method_equal(user_auths[0], auth_method)
            
            # Update auth method
            retrieved_auth.credentials["password_hash"] = "new_hashed_password"
            updated_auth = await storage.update_user_auth_method(retrieved_auth)
            assert updated_auth.credentials["password_hash"] == "new_hashed_password"
            
            # Verify update persisted
            final_auth = await storage.get_user_auth_method(
                AuthProvider.LOCAL, user.username
            )
            assert final_auth.credentials["password_hash"] == "new_hashed_password"
            
            # Delete auth method
            deleted = await storage.delete_user_auth_method(auth_method.id)
            assert deleted is True
            
            # Verify auth method is gone
            missing_auth = await storage.get_user_auth_method(
                AuthProvider.LOCAL, user.username
            )
            assert missing_auth is None
    
    @pytest.mark.asyncio
    async def test_multiple_auth_methods_per_user(self):
        """Test user can have multiple auth methods."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create user
            user = UserFactory.create(id="multi-auth-user")
            await storage.create_user(user)
            
            # Create multiple auth methods
            local_auth = UserAuthMethodFactory.create_local_auth(user)
            google_auth = UserAuthMethodFactory.create_google_auth(
                user, google_user_id="google123"
            )
            
            await storage.create_user_auth_method(local_auth)
            await storage.create_user_auth_method(google_auth)
            
            # Retrieve all auth methods for user
            user_auths = await storage.get_user_auth_methods(user.id)
            assert len(user_auths) == 2
            
            # Should be able to find each by provider
            local_retrieved = await storage.get_user_auth_method(
                AuthProvider.LOCAL, user.username
            )
            google_retrieved = await storage.get_user_auth_method(
                AuthProvider.GOOGLE, "google123"
            )
            
            assert local_retrieved is not None
            assert google_retrieved is not None
            assert local_retrieved.provider == AuthProvider.LOCAL
            assert google_retrieved.provider == AuthProvider.GOOGLE
    
    @pytest.mark.asyncio
    async def test_auth_methods_isolated_by_user(self):
        """Test that auth methods are properly isolated by user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create two users
            user1 = UserFactory.create(id="user1", username="user_one")
            user2 = UserFactory.create(id="user2", username="user_two")
            await storage.create_user(user1)
            await storage.create_user(user2)
            
            # Create auth methods for each user
            auth1 = UserAuthMethodFactory.create_local_auth(user1)
            auth2 = UserAuthMethodFactory.create_local_auth(user2)
            
            await storage.create_user_auth_method(auth1)
            await storage.create_user_auth_method(auth2)
            
            # Each user should only see their own auth methods
            user1_auths = await storage.get_user_auth_methods(user1.id)
            user2_auths = await storage.get_user_auth_methods(user2.id)
            
            assert len(user1_auths) == 1
            assert len(user2_auths) == 1
            assert user1_auths[0].user_id == user1.id
            assert user2_auths[0].user_id == user2.id


@pytest.mark.integration
class TestFileStorageSessionIntegration:
    """Integration tests for session operations in FileStorage."""
    
    @pytest.mark.asyncio
    async def test_complete_session_lifecycle(self):
        """Test full session lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create user first with unique IDs
            unique_user_id = f"session-user-{uuid.uuid4().hex[:8]}"
            unique_session_id = f"session-{uuid.uuid4().hex[:8]}"
            user = UserFactory.create(id=unique_user_id)
            await storage.create_user(user)
            
            # Create session
            session = SessionDataFactory.create(
                session_id=unique_session_id,
                user_id=user.id,
                metadata={"ip": "192.168.1.100", "browser": "Chrome"}
            )
            
            created_session = await storage.create_session(session)
            assert_session_equal(created_session, session)
            
            # Retrieve session
            retrieved_session = await storage.get_session(unique_session_id)
            assert retrieved_session is not None
            assert_session_equal(retrieved_session, session)
            
            # Update session
            retrieved_session.last_activity = utc_now()
            retrieved_session.metadata["page"] = "/dashboard"
            updated_session = await storage.update_session(retrieved_session)
            
            assert updated_session.metadata["page"] == "/dashboard"
            assert updated_session.last_activity > session.last_activity
            
            # Verify update persisted
            final_session = await storage.get_session(unique_session_id)
            assert final_session.metadata["page"] == "/dashboard"
            
            # Delete session
            deleted = await storage.delete_session(unique_session_id)
            assert deleted is True
            
            # Verify session is gone
            missing_session = await storage.get_session(unique_session_id)
            assert missing_session is None


@pytest.mark.integration
class TestFileStorageCompleteWorkflows:
    """Integration tests for complete user workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_user_setup_workflow(self):
        """Test complete workflow: user + auth method + session."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Use test data builder for complete scenario
            user, auth_method, session = TestDataBuilder.create_complete_user_scenario(
                username="workflow_user"
            )
            
            # Create all components
            await storage.create_user(user)
            await storage.create_user_auth_method(auth_method)
            await storage.create_session(session)
            
            # Verify everything is connected
            retrieved_user = await storage.get_user(user.id)
            user_auths = await storage.get_user_auth_methods(user.id)
            user_session = await storage.get_session(session.session_id)
            
            assert retrieved_user.username == "workflow_user"
            assert len(user_auths) == 1
            assert user_auths[0].user_id == user.id
            assert user_session.user_id == user.id
            
            # Test cleanup workflow
            await storage.delete_session(session.session_id)
            await storage.delete_user_auth_method(auth_method.id)
            await storage.delete_user(user.id)
            
            # Verify everything is cleaned up
            assert await storage.get_user(user.id) is None
            assert await storage.get_session(session.session_id) is None
            assert len(await storage.get_user_auth_methods(user.id)) == 0
    
    @pytest.mark.asyncio
    async def test_data_persistence_across_storage_instances(self):
        """Test that data persists when creating new FileStorage instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create and use first storage instance
            config1 = FileStorageConfig(type="file", base_dir=temp_dir)
            storage1 = FileStorage(config1)
            user = UserFactory.create(id="persistent-user", username="persistent")
            await storage1.create_user(user)
            await storage1.store_data("test_key", {"persisted": "data"})
            
            # Create new storage instance pointing to same directory
            config2 = FileStorageConfig(type="file", base_dir=temp_dir)
            storage2 = FileStorage(config2)
            
            # Data should be accessible from new instance
            retrieved_user = await storage2.get_user("persistent-user")
            retrieved_data = await storage2.get_data("test_key")
            
            assert retrieved_user is not None
            assert retrieved_user.username == "persistent"
            assert retrieved_data == {"persisted": "data"}


@pytest.mark.integration
@pytest.mark.slow
class TestFileStoragePerformance:
    """Performance-related integration tests."""
    
    @pytest.mark.asyncio
    async def test_large_number_of_users(self):
        """Test storage with large number of users."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create many users
            user_count = 100
            users = []
            for i in range(user_count):
                user = UserFactory.create(id=f"user-{i:03d}", username=f"user_{i:03d}")
                users.append(user)
                await storage.create_user(user)
            
            # Verify all users can be retrieved
            for i in range(0, user_count, 10):  # Check every 10th user
                user = await storage.get_user(f"user-{i:03d}")
                assert user is not None
                assert user.username == f"user_{i:03d}"
            
            # Test get_user_by_username performance
            middle_user = await storage.get_user_by_username("user_050")
            assert middle_user is not None
            assert middle_user.id == "user-050"