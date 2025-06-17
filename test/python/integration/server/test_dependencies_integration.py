"""Integration tests for server dependencies with storage backend."""

import pytest
import tempfile
from pathlib import Path

from role_play.server.dependencies import get_storage_backend, get_chat_logger, get_auth_manager, get_content_loader
from role_play.common.storage import FileStorage, FileStorageConfig
from role_play.chat.chat_logger import ChatLogger
from role_play.common.auth import AuthManager

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))


@pytest.mark.integration
class TestDependencyInjectionIntegration:
    """Integration tests for FastAPI dependency injection with storage backend."""

    def test_storage_backend_dependency(self):
        """Test that storage backend dependency returns FileStorage instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the environment variable that get_storage_backend reads
            import os
            original_storage_path = os.environ.get('STORAGE_PATH')
            os.environ['STORAGE_PATH'] = temp_dir
            
            try:
                storage = get_storage_backend()
                
                # Verify it's a FileStorage instance
                assert isinstance(storage, FileStorage)
                assert storage.storage_dir == Path(temp_dir)
                assert storage.locks_dir.exists()
            finally:
                # Restore original environment
                if original_storage_path:
                    os.environ['STORAGE_PATH'] = original_storage_path
                elif 'STORAGE_PATH' in os.environ:
                    del os.environ['STORAGE_PATH']

    def test_chat_logger_dependency_integration(self):
        """Test that chat logger dependency uses injected storage backend."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a storage backend
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Create a content loader
            content_loader = get_content_loader()
            
            # Get chat logger with this storage and content loader
            chat_logger = get_chat_logger(storage, content_loader)
            
            # Verify it's properly configured
            assert isinstance(chat_logger, ChatLogger)
            assert chat_logger.storage == storage
            assert chat_logger.content_loader == content_loader

    def test_auth_manager_dependency_integration(self):
        """Test that auth manager dependency uses injected storage backend."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a storage backend
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Mock environment variables for auth manager
            import os
            original_jwt_secret = os.environ.get('JWT_SECRET_KEY')
            os.environ['JWT_SECRET_KEY'] = 'test_secret_key_for_integration'
            
            try:
                # Get auth manager with this storage
                auth_manager = get_auth_manager(storage)
                
                # Verify it's properly configured
                assert isinstance(auth_manager, AuthManager)
                assert auth_manager.storage == storage
                # JWT secret comes from config - just verify it's set
                assert auth_manager.jwt_secret_key is not None
            finally:
                # Restore original environment
                if original_jwt_secret:
                    os.environ['JWT_SECRET_KEY'] = original_jwt_secret
                elif 'JWT_SECRET_KEY' in os.environ:
                    del os.environ['JWT_SECRET_KEY']

    @pytest.mark.asyncio
    async def test_full_dependency_chain_integration(self):
        """Test full dependency chain with real storage operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create storage backend
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Get dependencies
            content_loader = get_content_loader()
            chat_logger = get_chat_logger(storage, content_loader)
            
            # Mock auth manager setup
            import os
            original_jwt_secret = os.environ.get('JWT_SECRET_KEY')
            os.environ['JWT_SECRET_KEY'] = 'integration_test_secret'
            
            try:
                auth_manager = get_auth_manager(storage)
                
                # Test the full workflow
                # 1. Create a user via auth manager
                user, token = await auth_manager.register_user(
                    username="integration_user",
                    email="integration@test.com",
                    password="test_password_123"
                )
                
                # 2. Use chat logger with that user
                session_id, storage_path = await chat_logger.start_session(
                    user_id=user.id,
                    participant_name=user.username,
                    scenario_id="integration_test",
                    scenario_name="Integration Test Scenario",
                    character_id="test_char",
                    character_name="Test Character"
                )
                
                # 3. Log a message
                await chat_logger.log_message(
                    user_id=user.id,
                    session_id=session_id,
                    role="participant",
                    content="Integration test message",
                    message_number=1
                )
                
                # 4. Verify the data is properly stored
                # Check user exists in storage
                stored_user = await storage.get_user(user.id)
                assert stored_user is not None
                assert stored_user.username == "integration_user"
                
                # Check chat session exists
                assert await storage.exists(storage_path)
                
                # Check session can be listed
                sessions = await chat_logger.list_user_sessions(user.id)
                assert len(sessions) == 1
                assert sessions[0]["session_id"] == session_id
                
                # 5. Verify auth token works
                token_user = await auth_manager.get_user_by_token(token)
                assert token_user.id == user.id
                
            finally:
                # Restore environment
                if original_jwt_secret:
                    os.environ['JWT_SECRET_KEY'] = original_jwt_secret
                elif 'JWT_SECRET_KEY' in os.environ:
                    del os.environ['JWT_SECRET_KEY']


@pytest.mark.integration
class TestStorageBackendSingleton:
    """Test that storage backend dependency maintains singleton behavior."""
    
    def test_storage_backend_singleton_behavior(self):
        """Test that multiple calls to get_storage_backend return same instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            import os
            original_storage_path = os.environ.get('STORAGE_PATH')
            os.environ['STORAGE_PATH'] = temp_dir
            
            try:
                # Get storage backend multiple times
                storage1 = get_storage_backend()
                storage2 = get_storage_backend()
                
                # Should be the same instance (due to @lru_cache)
                assert storage1 is storage2
                
            finally:
                # Clear the cache to avoid affecting other tests
                get_storage_backend.cache_clear()
                if original_storage_path:
                    os.environ['STORAGE_PATH'] = original_storage_path
                elif 'STORAGE_PATH' in os.environ:
                    del os.environ['STORAGE_PATH']

    def test_dependency_behavior_verification(self):
        """Test that dependencies work correctly with storage backend."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            # Get chat logger multiple times - should work fine
            content_loader = get_content_loader()
            chat_logger1 = get_chat_logger(storage, content_loader)
            chat_logger2 = get_chat_logger(storage, content_loader)
            
            # Both should use the same storage
            assert chat_logger1.storage is chat_logger2.storage
            
            # Get auth manager multiple times - should work fine  
            auth_manager1 = get_auth_manager(storage)
            auth_manager2 = get_auth_manager(storage)
            
            # Both should use the same storage and have same config
            assert auth_manager1.storage is auth_manager2.storage
            assert auth_manager1.jwt_secret_key == auth_manager2.jwt_secret_key


@pytest.mark.integration 
class TestConcurrentDependencyAccess:
    """Test concurrent access to dependencies."""
    
    @pytest.mark.asyncio
    async def test_concurrent_chat_logger_access(self):
        """Test concurrent access to chat logger dependency."""
        import asyncio
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            async def get_and_use_chat_logger(user_num):
                content_loader = get_content_loader()
                chat_logger = get_chat_logger(storage, content_loader)
                
                # Start a session
                session_id, _ = await chat_logger.start_session(
                    user_id=f"concurrent_user_{user_num}",
                    participant_name=f"User {user_num}",
                    scenario_id="concurrent_test",
                    scenario_name="Concurrent Test",
                    character_id="test_char",
                    character_name="Test Character"
                )
                
                # Log a message
                await chat_logger.log_message(
                    user_id=f"concurrent_user_{user_num}",
                    session_id=session_id,
                    role="participant",
                    content=f"Message from user {user_num}",
                    message_number=1
                )
                
                return f"concurrent_user_{user_num}", session_id
            
            # Run 5 concurrent operations
            tasks = [get_and_use_chat_logger(i) for i in range(5)]
            results = await asyncio.gather(*tasks)
            
            # Verify all operations completed successfully
            assert len(results) == 5
            
            # Verify each user has their session
            for user_id, session_id in results:
                content_loader = get_content_loader()
                chat_logger = get_chat_logger(storage, content_loader)
                sessions = await chat_logger.list_user_sessions(user_id)
                assert len(sessions) == 1
                assert sessions[0]["session_id"] == session_id
            
            # Note: ChatLogger is not cached, so no cleanup needed

    @pytest.mark.asyncio
    async def test_concurrent_auth_operations(self):
        """Test concurrent auth manager operations."""
        import asyncio
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            
            import os
            original_jwt_secret = os.environ.get('JWT_SECRET_KEY')
            os.environ['JWT_SECRET_KEY'] = 'concurrent_test_secret'
            
            try:
                async def register_user(user_num):
                    auth_manager = get_auth_manager(storage)
                    
                    user, token = await auth_manager.register_user(
                        username=f"concurrent_user_{user_num}",
                        email=f"user{user_num}@test.com",
                        password=f"password_{user_num}"
                    )
                    
                    return user.id, token
                
                # Register 5 users concurrently
                tasks = [register_user(i) for i in range(5)]
                results = await asyncio.gather(*tasks)
                
                # Verify all users were created
                assert len(results) == 5
                
                # Verify each user can be retrieved
                auth_manager = get_auth_manager(storage)
                for user_id, token in results:
                    # Test token authentication
                    user = await auth_manager.get_user_by_token(token)
                    assert user.id == user_id
                    
                    # Test direct user retrieval
                    stored_user = await storage.get_user(user_id)
                    assert stored_user is not None
                    assert stored_user.id == user_id
                
            finally:
                # Restore environment (AuthManager is not cached)
                if original_jwt_secret:
                    os.environ['JWT_SECRET_KEY'] = original_jwt_secret
                elif 'JWT_SECRET_KEY' in os.environ:
                    del os.environ['JWT_SECRET_KEY']