"""Unit tests for common.storage module."""

import pytest
import tempfile
import json
import uuid
import os
from pathlib import Path
from unittest.mock import patch, mock_open, AsyncMock
import asyncio
import aiofiles

from role_play.common.storage import FileStorage, StorageBackend, LockAcquisitionError, FileStorageConfig
from role_play.common.exceptions import StorageError
from role_play.common.models import User, UserAuthMethod, SessionData, UserRole, AuthProvider
from role_play.common.storage_monitoring import StorageMonitor

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from fixtures.factories import UserFactory, UserAuthMethodFactory, SessionDataFactory
from fixtures.helpers import MockStorageBackend


def create_file_storage(temp_dir: str) -> FileStorage:
    """Helper function to create FileStorage with proper config."""
    config = FileStorageConfig(
        type="file",
        base_dir=temp_dir
    )
    return FileStorage(config)


class TestStorageBackend:
    """Test StorageBackend abstract base class."""
    
    def test_storage_backend_is_abstract(self):
        """Test that StorageBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            StorageBackend()
    
    def test_storage_backend_methods_are_abstract(self):
        """Test that all methods are abstract."""
        # This is more of a design verification
        backend = MockStorageBackend()
        
        # These should be callable (implemented in mock)
        assert hasattr(backend, 'get_user')
        assert hasattr(backend, 'create_user')
        assert hasattr(backend, 'get_user_auth_methods')
        assert hasattr(backend, 'store_data')
        assert hasattr(backend, 'read')
        assert hasattr(backend, 'write')
        assert hasattr(backend, 'lock')


class TestFileStorageInitialization:
    """Test FileStorage initialization and setup."""
    
    def test_file_storage_default_directory(self):
        """Test FileStorage with default directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            assert storage.storage_dir == Path(temp_dir)
            assert storage.locks_dir == Path(temp_dir) / ".locks"
    
    def test_file_storage_creates_directories(self):
        """Test that FileStorage creates required directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_storage"
            storage = create_file_storage(str(storage_path))
            
            # Check directories were created
            assert storage_path.exists()
            assert (storage_path / ".locks").exists()
    
    def test_file_storage_with_existing_directory(self):
        """Test FileStorage with existing directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "existing"
            storage_path.mkdir()
            
            # Should not raise error with existing directories
            storage = create_file_storage(str(storage_path))
            assert storage.storage_dir == storage_path


class TestFileStorageLocking:
    """Test FileStorage locking mechanism."""
    
    @pytest.mark.asyncio
    async def test_lock_context_manager(self):
        """Test the lock context manager works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Should not raise any exceptions
            async with storage.lock("test/path"):
                pass
    
    @pytest.mark.asyncio
    async def test_lock_creates_lock_file(self):
        """Test that locking creates appropriate lock file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            async with storage.lock("users/123/profile"):
                # Lock file should exist during lock
                lock_path = storage.locks_dir / "users_123_profile.lock"
                assert lock_path.exists()
                
                # Verify lock file contains PID and metadata
                async with aiofiles.open(lock_path, 'r') as f:
                    content = await f.read()
                lock_data = json.loads(content)
                assert "pid" in lock_data
                assert "timestamp" in lock_data
                assert "resource" in lock_data
                assert lock_data["pid"] == os.getpid()
                assert lock_data["resource"] == "users/123/profile"
            
            # Lock file should be removed after context
            assert not lock_path.exists()
    
    @pytest.mark.asyncio
    async def test_stale_lock_detection(self):
        """Test that stale locks can be detected and removed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            lock_path = storage._get_lock_path("test/resource")
            
            # Create a stale lock file (very old timestamp, non-existent PID)
            stale_lock_data = {
                "pid": 999999,  # Extremely unlikely to exist
                "timestamp": 0,  # Very old timestamp
                "resource": "test/resource"
            }
            
            await aiofiles.os.makedirs(lock_path.parent, exist_ok=True)
            async with aiofiles.open(lock_path, 'w') as f:
                await f.write(json.dumps(stale_lock_data))
            
            # Verify the lock is detected as stale
            is_stale = await storage._is_stale_lock(lock_path, lease_duration_seconds=1.0)
            assert is_stale is True
            
            # Should be able to acquire lock despite existing lock file (stale lock gets removed)
            async with storage.lock("test/resource", timeout=1.0):
                pass  # Should succeed by removing stale lock


class TestFileStorageBasicOperations:
    """Test FileStorage basic file operations."""
    
    @pytest.mark.asyncio
    async def test_write_and_read_text(self):
        """Test writing and reading text data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            test_data = "Hello, World!"
            path = "test/file.txt"
            
            await storage.write(path, test_data)
            result = await storage.read(path)
            
            assert result == test_data
    
    @pytest.mark.asyncio
    async def test_append_text(self):
        """Test appending text data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            path = "test/append.txt"
            
            await storage.write(path, "Line 1\n")
            await storage.append(path, "Line 2\n")
            await storage.append(path, "Line 3\n")
            
            result = await storage.read(path)
            assert result == "Line 1\nLine 2\nLine 3\n"
    
    @pytest.mark.asyncio
    async def test_exists(self):
        """Test checking file existence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            path = "test/exists.txt"
            
            assert not await storage.exists(path)
            
            await storage.write(path, "content")
            assert await storage.exists(path)
    
    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            path = "test/delete.txt"
            
            await storage.write(path, "content")
            assert await storage.exists(path)
            
            result = await storage.delete(path)
            assert result is True
            assert not await storage.exists(path)
            
            # Deleting non-existent file should return False
            result = await storage.delete(path)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_list_keys(self):
        """Test listing keys with prefix."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Create some files
            await storage.write("users/123/profile", "user data")
            await storage.write("users/123/settings", "settings data")
            await storage.write("users/456/profile", "other user")
            await storage.write("sessions/abc", "session data")
            
            # Test prefix matching
            user_keys = await storage.list_keys("users/123/")
            assert len(user_keys) == 2
            assert "users/123/profile" in user_keys
            assert "users/123/settings" in user_keys
            
            all_user_keys = await storage.list_keys("users/")
            assert len(all_user_keys) == 3
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading non-existent file raises error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            with pytest.raises(StorageError) as exc_info:
                await storage.read("nonexistent/file.txt")
            
            assert "Path not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_invalid_key_security(self):
        """Test that invalid keys (with ..) are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            with pytest.raises(StorageError) as exc_info:
                await storage.write("../../../etc/passwd", "hacker data")
            
            assert "Invalid key" in str(exc_info.value)


class TestFileStorageJSONOperations:
    """Test FileStorage JSON helper methods."""
    
    @pytest.mark.asyncio
    async def test_read_write_json(self):
        """Test JSON read/write operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
            path = "test/data"
            
            await storage._write_json(path, test_data)
            result = await storage._read_json(path)
            
            assert result == test_data
    
    @pytest.mark.asyncio
    async def test_read_json_nonexistent(self):
        """Test reading non-existent JSON returns None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            result = await storage._read_json("nonexistent/file")
            assert result is None


class TestFileStorageUserOperations:
    """Test FileStorage user-related operations."""
    
    @pytest.mark.asyncio
    async def test_create_user_file_structure(self):
        """Test that create_user creates the correct file structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            user = UserFactory.create(id="test-123", username="testuser")
            
            await storage.create_user(user)
            
            # Check file was created with correct path
            user_path = "users/test-123/profile"
            assert await storage.exists(user_path)
            
            # Check file contains correct data
            result = await storage._read_json(user_path)
            assert result["id"] == "test-123"
            assert result["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_create_user_already_exists(self):
        """Test error when creating user that already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            user = UserFactory.create(id="duplicate-123")
            
            # Create user first time
            await storage.create_user(user)
            
            # Try to create same user again
            with pytest.raises(StorageError) as exc_info:
                await storage.create_user(user)
            
            assert "already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_user_not_found(self):
        """Test getting non-existent user returns None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            result = await storage.get_user("non-existent-id")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_update_user_not_found(self):
        """Test error when updating non-existent user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            user = UserFactory.create(id="missing-123")
            
            with pytest.raises(StorageError) as exc_info:
                await storage.update_user(user)
            
            assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_user_not_found(self):
        """Test deleting non-existent user returns True (no-op)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            result = await storage.delete_user("non-existent-id")
            assert result is True  # Always returns True for delete operations


class TestFileStorageAuthMethodOperations:
    """Test FileStorage auth method operations."""
    
    @pytest.mark.asyncio
    async def test_create_auth_method_file_structure(self):
        """Test that create_user_auth_method creates correct file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            auth_method = UserAuthMethodFactory.create(id="auth-123", user_id="user-456")
            
            await storage.create_user_auth_method(auth_method)
            
            # Check file was created with correct path
            auth_path = f"users/{auth_method.user_id}/auth_methods/{auth_method.id}"
            assert await storage.exists(auth_path)
            
            # Check file contains correct data
            result = await storage._read_json(auth_path)
            assert result["id"] == "auth-123"
            assert result["user_id"] == "user-456"
            assert result["provider"] == auth_method.provider


class TestFileStorageSessionOperations:
    """Test FileStorage session operations."""
    
    @pytest.mark.asyncio
    async def test_create_session_file_structure(self):
        """Test that create_session creates correct file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            session = SessionDataFactory.create(session_id="session-123")
            
            await storage.create_session(session)
            
            # Check file was created with correct path
            session_path = f"sessions/{session.session_id}"
            assert await storage.exists(session_path)
            
            # Check file contains correct data
            result = await storage._read_json(session_path)
            assert result["session_id"] == "session-123"


class TestFileStorageDataOperations:
    """Test FileStorage arbitrary data operations."""
    
    @pytest.mark.asyncio
    async def test_store_and_get_data(self):
        """Test storing and retrieving arbitrary data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            test_data = {"complex": {"nested": "data"}, "list": [1, 2, 3]}
            key = "test/config"
            
            await storage.store_data(key, test_data)
            result = await storage.get_data(key)
            
            assert result == test_data


class TestFileStorageErrorHandling:
    """Test FileStorage error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_io_error_on_read(self):
        """Test handling IO errors during file reading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Create a file first
            await storage.write("test/file", "content")
            
            # Mock aiofiles.open to raise IOError
            with patch('aiofiles.open', side_effect=IOError("Disk error")):
                with pytest.raises(StorageError) as exc_info:
                    await storage.read("test/file")
                
                assert "Failed to read" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_io_error_on_write(self):
        """Test handling IO errors during file writing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Mock aiofiles.open to raise IOError
            with patch('aiofiles.open', side_effect=IOError("No space left")):
                with pytest.raises(StorageError) as exc_info:
                    await storage.write("test/file", "content")
                
                assert "Failed to write" in str(exc_info.value)


class TestFileStorageBytesOperations:
    """Test FileStorage bytes methods."""
    
    @pytest.mark.asyncio
    async def test_write_read_bytes(self):
        """Test writing and reading binary data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            test_data = b"Binary data \x00\x01\x02"
            path = "test/binary"
            
            await storage.write_bytes(path, test_data)
            result = await storage.read_bytes(path)
            
            assert result == test_data
    
    @pytest.mark.asyncio
    async def test_append_bytes(self):
        """Test appending binary data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            path = "test/binary_append"
            
            await storage.write_bytes(path, b"Part 1")
            await storage.append_bytes(path, b"Part 2")
            
            result = await storage.read_bytes(path)
            assert result == b"Part 1Part 2"


class TestFileStorageComplexOperations:
    """Test FileStorage in complex scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_file_operations(self):
        """Test concurrent file operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            async def write_file(file_num):
                path = f"concurrent/file_{file_num}"
                content = f"Content for file {file_num}"
                await storage.write(path, content)
                return path, content
            
            # Write 10 files concurrently
            tasks = [write_file(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            # Verify all files were written correctly
            for path, expected_content in results:
                actual_content = await storage.read(path)
                assert actual_content == expected_content
    
    @pytest.mark.asyncio
    async def test_user_search_operations(self):
        """Test user search by username and email."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Create multiple users
            user1 = UserFactory.create(id="user1", username="alice", email="alice@example.com")
            user2 = UserFactory.create(id="user2", username="bob", email="bob@example.com")
            
            await storage.create_user(user1)
            await storage.create_user(user2)
            
            # Test search by username
            found_alice = await storage.get_user_by_username("alice")
            assert found_alice is not None
            assert found_alice.id == "user1"
            
            found_none = await storage.get_user_by_username("charlie")
            assert found_none is None
            
            # Test search by email
            found_bob = await storage.get_user_by_email("bob@example.com")
            assert found_bob is not None
            assert found_bob.id == "user2"
            
            found_none = await storage.get_user_by_email("charlie@example.com")
            assert found_none is None
    
    @pytest.mark.asyncio
    async def test_auth_method_search_operations(self):
        """Test auth method search and retrieval."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Create auth methods for different users
            auth1 = UserAuthMethodFactory.create(
                id="auth1", user_id="user1", provider="google", provider_user_id="google123"
            )
            auth2 = UserAuthMethodFactory.create(
                id="auth2", user_id="user1", provider="local", provider_user_id="alice"
            )
            auth3 = UserAuthMethodFactory.create(
                id="auth3", user_id="user2", provider="google", provider_user_id="google456"
            )
            
            await storage.create_user_auth_method(auth1)
            await storage.create_user_auth_method(auth2)
            await storage.create_user_auth_method(auth3)
            
            # Test get by provider and provider_user_id
            found_google = await storage.get_user_auth_method("google", "google123")
            assert found_google is not None
            assert found_google.id == "auth1"
            
            found_none = await storage.get_user_auth_method("google", "notfound")
            assert found_none is None
            
            # Test get all auth methods for user
            user1_methods = await storage.get_user_auth_methods("user1")
            assert len(user1_methods) == 2
            
            user2_methods = await storage.get_user_auth_methods("user2")
            assert len(user2_methods) == 1
            
            # Test delete auth method
            deleted = await storage.delete_user_auth_method("auth1")
            assert deleted is True
            
            # Verify it was deleted
            remaining_methods = await storage.get_user_auth_methods("user1")
            assert len(remaining_methods) == 1
            
            # Test delete non-existent
            deleted_none = await storage.delete_user_auth_method("nonexistent")
            assert deleted_none is False
    
    @pytest.mark.asyncio
    async def test_json_decode_error_handling(self):
        """Test JSON decode error handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Write invalid JSON manually
            file_path = storage._get_storage_path("invalid.json")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("{ invalid json ")
            
            # Should raise StorageError
            with pytest.raises(StorageError) as exc_info:
                await storage._read_json("invalid.json")
            
            assert "Failed to parse JSON" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_lock_timeout_simulation(self):
        """Test lock acquisition timeout (simulated)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # This is hard to test without real contention, but we can at least
            # verify the timeout parameter is accepted
            async with storage.lock("test/resource", timeout=0.1):
                pass  # Should work fine
    
    @pytest.mark.asyncio
    async def test_lock_timeout_error(self):
        """Test lock timeout error by mocking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Mock os.open to always fail (simulate lock file always exists)
            from unittest.mock import patch
            
            with patch('os.open', side_effect=FileExistsError("Lock file exists")):
                with pytest.raises(LockAcquisitionError) as exc_info:
                    async with storage.lock("test/resource", timeout=0.1):
                        pass
                
                assert "Failed to acquire lock" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_string_bytes_conversion(self):
        """Test the default string/bytes conversion methods."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Test that base class default conversions would work
            # (FileStorage overrides these, but let's test the defaults)
            text_data = "Hello, 世界!"
            
            # Write as string, read as bytes
            await storage.write("test/text", text_data)
            bytes_result = await storage.read_bytes("test/text")
            assert bytes_result == text_data.encode('utf-8')
            
            # Write as bytes, read as string  
            bytes_data = "Binary: \x00\x01\x02".encode('utf-8')
            await storage.write_bytes("test/binary", bytes_data)
            text_result = await storage.read("test/binary")
            assert text_result == bytes_data.decode('utf-8')
    
    @pytest.mark.asyncio
    async def test_full_user_workflow(self):
        """Test a complete user creation and management workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Create a user with unique ID to avoid conflicts
            unique_id = f"workflow-{uuid.uuid4().hex[:8]}"
            user = UserFactory.create(id=unique_id, username=f"testuser_{unique_id}")
            await storage.create_user(user)
            
            # Create auth methods
            auth1 = UserAuthMethodFactory.create(
                user_id=user.id,
                provider="local",
                provider_user_id="testuser"
            )
            auth2 = UserAuthMethodFactory.create(
                user_id=user.id,
                provider="google",
                provider_user_id="google-123"
            )
            
            await storage.create_user_auth_method(auth1)
            await storage.create_user_auth_method(auth2)
            
            # Create a session
            session = SessionDataFactory.create(
                user_id=user.id,
                metadata={"test": "data"}
            )
            await storage.create_session(session)
            
            # Verify everything exists
            retrieved_user = await storage.get_user(user.id)
            assert retrieved_user.username == f"testuser_{unique_id}"
            
            auth_methods = await storage.get_user_auth_methods(user.id)
            assert len(auth_methods) == 2
            
            retrieved_session = await storage.get_session(session.session_id)
            assert retrieved_session.user_id == user.id
            
            # Update user
            user.email = "updated@example.com"
            await storage.update_user(user)
            
            updated_user = await storage.get_user(user.id)
            assert updated_user.email == "updated@example.com"
            
            # Clean up
            await storage.delete_user(user.id)
            await storage.delete_session(session.session_id)
            
            assert await storage.get_user(user.id) is None
            assert await storage.get_session(session.session_id) is None


class TestStorageBackendDefaultMethods:
    """Test StorageBackend default method implementations."""
    
    @pytest.mark.asyncio
    async def test_bytes_methods_default_implementation(self):
        """Test that default bytes methods work via string conversion."""
        backend = MockStorageBackend()
        
        # Test write_bytes -> write conversion
        test_bytes = b"Hello, bytes!"
        await backend.write_bytes("test/bytes", test_bytes)
        
        # Should be stored as string
        stored = await backend.read("test/bytes")
        assert stored == test_bytes.decode('utf-8')
        
        # Test read_bytes -> read conversion
        result_bytes = await backend.read_bytes("test/bytes")
        assert result_bytes == test_bytes
        
        # Test append_bytes -> append conversion
        more_bytes = b" More data!"
        await backend.append_bytes("test/bytes", more_bytes)
        
        final_result = await backend.read_bytes("test/bytes")
        assert final_result == test_bytes + more_bytes
    
    @pytest.mark.asyncio
    async def test_empty_prefix_list_keys(self):
        """Test list_keys with empty results."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # List keys for non-existent prefix
            keys = await storage.list_keys("nonexistent/")
            assert keys == []
    
    @pytest.mark.asyncio
    async def test_hidden_files_ignored(self):
        """Test that hidden files are ignored in list_keys."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            # Create regular and hidden files
            await storage.write("test/regular.txt", "content")
            
            # Create hidden file manually
            hidden_path = storage._get_storage_path("test/.hidden")
            hidden_path.parent.mkdir(parents=True, exist_ok=True)
            with open(hidden_path, 'w') as f:
                f.write("hidden content")
            
            # List keys should not include hidden files
            keys = await storage.list_keys("test/")
            assert len(keys) == 1
            assert "test/regular.txt" in keys
            assert "test/.hidden" not in keys


@patch('role_play.common.storage.get_storage_monitor')
class TestFileStorageMonitoring:
    """Test the integration of StorageMonitor with FileStorage."""

    @pytest.mark.asyncio
    async def test_read_operation_is_monitored(self, mock_get_monitor):
        """Verify that the 'read' operation is monitored."""
        mock_monitor = AsyncMock(spec=StorageMonitor)
        mock_monitor.monitor_storage_operation.return_value.__aenter__.return_value = None
        mock_get_monitor.return_value = mock_monitor

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            await storage.write("test.txt", "data")
            
            # Reset mock after setup
            mock_monitor.reset_mock()

            await storage.read("test.txt")

            mock_monitor.monitor_storage_operation.assert_called_once_with("read")

    @pytest.mark.asyncio
    async def test_write_operation_is_monitored(self, mock_get_monitor):
        """Verify that the 'write' operation is monitored."""
        mock_monitor = AsyncMock(spec=StorageMonitor)
        mock_monitor.monitor_storage_operation.return_value.__aenter__.return_value = None
        mock_get_monitor.return_value = mock_monitor

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            await storage.write("test.txt", "data")

            mock_monitor.monitor_storage_operation.assert_called_once_with("write")

    @pytest.mark.asyncio
    async def test_delete_operation_is_monitored(self, mock_get_monitor):
        """Verify that the 'delete' operation is monitored."""
        mock_monitor = AsyncMock(spec=StorageMonitor)
        mock_monitor.monitor_storage_operation.return_value.__aenter__.return_value = None
        mock_get_monitor.return_value = mock_monitor

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            await storage.write("test.txt", "data")
            
            # Reset mock after setup
            mock_monitor.reset_mock()

            await storage.delete("test.txt")

            mock_monitor.monitor_storage_operation.assert_called_once_with("delete")

    @pytest.mark.asyncio
    async def test_lock_operation_is_monitored(self, mock_get_monitor):
        """Verify that the 'lock' operation is monitored."""
        mock_monitor = AsyncMock(spec=StorageMonitor)
        mock_monitor.monitor_lock_acquisition.return_value.__aenter__.return_value = None
        mock_get_monitor.return_value = mock_monitor

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            
            async with storage.lock("resource/path"):
                pass

            mock_monitor.monitor_lock_acquisition.assert_called_once_with("resource/path", "file")

    @pytest.mark.asyncio
    async def test_stale_lock_expiry_is_recorded(self, mock_get_monitor):
        """Verify that stale lock expiry is recorded by the monitor."""
        mock_monitor = AsyncMock(spec=StorageMonitor)
        mock_monitor.monitor_lock_acquisition.return_value.__aenter__.return_value = None
        mock_get_monitor.return_value = mock_monitor

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = create_file_storage(temp_dir)
            lock_path = storage._get_lock_path("stale/resource")
            
            # Create a stale lock file
            stale_lock_data = {"pid": 99999, "timestamp": 0}
            await aiofiles.os.makedirs(lock_path.parent, exist_ok=True)
            async with aiofiles.open(lock_path, 'w') as f:
                await f.write(json.dumps(stale_lock_data))

            # Acquiring the lock should remove the stale one and record the event
            async with storage.lock("stale/resource", timeout=1.0):
                pass
            
            mock_monitor.record_lock_expiry.assert_called_once_with("stale/resource", "file")