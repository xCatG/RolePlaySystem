"""Unit tests for common.storage module."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, mock_open

from role_play.common.storage import FileStorage, StorageBackend
from role_play.common.exceptions import StorageError
from role_play.common.models import User, UserAuthMethod, SessionData, UserRole, AuthProvider

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from fixtures.factories import UserFactory, UserAuthMethodFactory, SessionDataFactory
from fixtures.helpers import MockStorageBackend


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


class TestFileStorageInitialization:
    """Test FileStorage initialization and setup."""
    
    def test_file_storage_default_directory(self):
        """Test FileStorage with default directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            assert storage.storage_dir == Path(temp_dir)
            assert storage.users_dir == Path(temp_dir) / "users"
            assert storage.auth_methods_dir == Path(temp_dir) / "auth_methods"
            assert storage.sessions_dir == Path(temp_dir) / "sessions"
            assert storage.data_dir == Path(temp_dir) / "data"
    
    def test_file_storage_creates_directories(self):
        """Test that FileStorage creates required directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_storage"
            storage = FileStorage(str(storage_path))
            
            # Check all directories were created
            assert storage_path.exists()
            assert (storage_path / "users").exists()
            assert (storage_path / "auth_methods").exists()
            assert (storage_path / "sessions").exists()
            assert (storage_path / "data").exists()
    
    def test_file_storage_with_existing_directory(self):
        """Test FileStorage with existing directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "existing"
            storage_path.mkdir()
            (storage_path / "users").mkdir()
            
            # Should not raise error with existing directories
            storage = FileStorage(str(storage_path))
            assert storage.storage_dir == storage_path


class TestFileStorageJSONOperations:
    """Test FileStorage JSON file operations."""
    
    def test_read_json_file_success(self):
        """Test successful JSON file reading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            # Create test file
            test_data = {"key": "value", "number": 42}
            test_file = Path(temp_dir) / "test.json"
            with open(test_file, 'w') as f:
                json.dump(test_data, f)
            
            result = storage._read_json_file(test_file)
            assert result == test_data
    
    def test_read_json_file_not_exists(self):
        """Test reading non-existent JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            non_existent = Path(temp_dir) / "missing.json"
            result = storage._read_json_file(non_existent)
            assert result is None
    
    def test_read_json_file_invalid_json(self):
        """Test reading invalid JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            # Create invalid JSON file
            invalid_file = Path(temp_dir) / "invalid.json"
            with open(invalid_file, 'w') as f:
                f.write("{ invalid json }")
            
            with pytest.raises(StorageError) as exc_info:
                storage._read_json_file(invalid_file)
            
            assert "Failed to read file" in str(exc_info.value)
    
    def test_write_json_file_success(self):
        """Test successful JSON file writing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            test_data = {"key": "value", "list": [1, 2, 3]}
            test_file = Path(temp_dir) / "output.json"
            
            storage._write_json_file(test_file, test_data)
            
            # Verify file was written correctly
            assert test_file.exists()
            with open(test_file, 'r') as f:
                written_data = json.load(f)
            assert written_data == test_data
    
    def test_write_json_file_with_datetime(self):
        """Test JSON file writing with datetime objects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            user = UserFactory.create()
            test_file = Path(temp_dir) / "user.json"
            
            # Should handle datetime serialization via default=str
            storage._write_json_file(test_file, user.model_dump())
            
            assert test_file.exists()
            # File should contain serialized datetime strings
            with open(test_file, 'r') as f:
                content = f.read()
                assert user.username in content
    
    def test_write_json_file_permission_error(self):
        """Test JSON file writing with permission error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            # Create a directory where we try to write a file
            blocked_path = Path(temp_dir) / "blocked"
            blocked_path.mkdir()
            blocked_path.chmod(0o444)  # Read-only
            
            test_file = blocked_path / "test.json"
            
            with pytest.raises(StorageError) as exc_info:
                storage._write_json_file(test_file, {"data": "test"})
            
            assert "Failed to write file" in str(exc_info.value)


class TestFileStorageErrorHandling:
    """Test FileStorage error handling scenarios."""
    
    def test_io_error_on_read(self):
        """Test handling IO errors during file reading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            # Mock open to raise IOError
            with patch('builtins.open', side_effect=IOError("Disk error")):
                test_file = Path(temp_dir) / "test.json"
                test_file.touch()  # Create empty file
                
                with pytest.raises(StorageError) as exc_info:
                    storage._read_json_file(test_file)
                
                assert "Failed to read file" in str(exc_info.value)
                assert "Disk error" in str(exc_info.value)
    
    def test_io_error_on_write(self):
        """Test handling IO errors during file writing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            test_file = Path(temp_dir) / "test.json"
            
            # Mock open to raise IOError
            with patch('builtins.open', side_effect=IOError("No space left")):
                with pytest.raises(StorageError) as exc_info:
                    storage._write_json_file(test_file, {"data": "test"})
                
                assert "Failed to write file" in str(exc_info.value)
                assert "No space left" in str(exc_info.value)


class TestFileStorageUserOperations:
    """Test FileStorage user-related operations (unit level)."""
    
    @pytest.mark.asyncio
    async def test_create_user_file_structure(self):
        """Test that create_user creates the correct file structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            user = UserFactory.create(id="test-123", username="testuser")
            
            await storage.create_user(user)
            
            # Check file was created with correct name
            user_file = Path(temp_dir) / "users" / "test-123.json"
            assert user_file.exists()
            
            # Check file contains correct data
            with open(user_file, 'r') as f:
                data = json.load(f)
                assert data["id"] == "test-123"
                assert data["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_create_user_already_exists(self):
        """Test error when creating user that already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
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
            storage = FileStorage(temp_dir)
            
            result = await storage.get_user("non-existent-id")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_update_user_not_found(self):
        """Test error when updating non-existent user."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            user = UserFactory.create(id="missing-123")
            
            with pytest.raises(StorageError) as exc_info:
                await storage.update_user(user)
            
            assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_user_not_found(self):
        """Test deleting non-existent user returns False."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            result = await storage.delete_user("non-existent-id")
            assert result is False


class TestFileStorageAuthMethodOperations:
    """Test FileStorage auth method operations (unit level)."""
    
    @pytest.mark.asyncio
    async def test_create_auth_method_file_structure(self):
        """Test that create_user_auth_method creates correct file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            auth_method = UserAuthMethodFactory.create(id="auth-123")
            
            await storage.create_user_auth_method(auth_method)
            
            # Check file was created
            auth_file = Path(temp_dir) / "auth_methods" / "auth-123.json"
            assert auth_file.exists()
            
            # Check file contains correct data
            with open(auth_file, 'r') as f:
                data = json.load(f)
                assert data["id"] == "auth-123"
                assert data["provider"] == auth_method.provider
    
    @pytest.mark.asyncio
    async def test_get_user_auth_methods_empty(self):
        """Test getting auth methods for user with none."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            result = await storage.get_user_auth_methods("user-with-no-auth")
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_user_auth_method_not_found(self):
        """Test getting non-existent auth method returns None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            result = await storage.get_user_auth_method("google", "missing-user")
            assert result is None


class TestFileStorageSessionOperations:
    """Test FileStorage session operations (unit level)."""
    
    @pytest.mark.asyncio
    async def test_create_session_file_structure(self):
        """Test that create_session creates correct file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            session = SessionDataFactory.create(session_id="session-123")
            
            await storage.create_session(session)
            
            # Check file was created
            session_file = Path(temp_dir) / "sessions" / "session-123.json"
            assert session_file.exists()
            
            # Check file contains correct data
            with open(session_file, 'r') as f:
                data = json.load(f)
                assert data["session_id"] == "session-123"
                assert data["user_id"] == session.user_id
    
    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test getting non-existent session returns None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            result = await storage.get_session("missing-session")
            assert result is None


class TestFileStorageDataOperations:
    """Test FileStorage arbitrary data operations."""
    
    @pytest.mark.asyncio
    async def test_store_and_get_data(self):
        """Test storing and retrieving arbitrary data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            test_data = {"complex": {"nested": "data"}, "numbers": [1, 2, 3]}
            await storage.store_data("test_key", test_data)
            
            # Check file was created
            data_file = Path(temp_dir) / "data" / "test_key.json"
            assert data_file.exists()
            
            # Check data can be retrieved
            result = await storage.get_data("test_key")
            assert result == test_data
    
    @pytest.mark.asyncio
    async def test_get_data_not_found(self):
        """Test getting non-existent data returns None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            result = await storage.get_data("missing_key")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_data_success(self):
        """Test successful data deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            # Store some data first
            await storage.store_data("delete_me", {"data": "to_delete"})
            
            # Delete it
            result = await storage.delete_data("delete_me")
            assert result is True
            
            # Verify it's gone
            data_file = Path(temp_dir) / "data" / "delete_me.json"
            assert not data_file.exists()
    
    @pytest.mark.asyncio
    async def test_delete_data_not_found(self):
        """Test deleting non-existent data returns False."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            
            result = await storage.delete_data("never_existed")
            assert result is False