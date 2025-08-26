"""Pytest configuration and shared fixtures for Role Play System tests."""

import asyncio
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Add src/python to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "python"))

from role_play.common.storage import FileStorage, FileStorageConfig, StorageBackend
from role_play.common.auth import AuthManager
from role_play.chat.chat_logger import ChatLogger


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture(scope="class")
def class_temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for class-scoped tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
async def file_storage(temp_dir: Path) -> FileStorage:
    """Create a FileStorage instance for testing."""
    config = FileStorageConfig(type="file", base_dir=str(temp_dir))
    return FileStorage(config)


@pytest.fixture(scope="class")
async def class_file_storage(class_temp_dir: Path) -> FileStorage:
    """Create a class-scoped FileStorage instance for integration tests."""
    config = FileStorageConfig(type="file", base_dir=str(class_temp_dir))
    return FileStorage(config)


@pytest.fixture
async def auth_manager(file_storage: FileStorage) -> AuthManager:
    """Create an AuthManager instance for testing."""
    return AuthManager(
        storage=file_storage,
        jwt_secret_key="test_secret_key_for_testing_only",
        access_token_expire_minutes=30
    )


@pytest.fixture(scope="class")
async def class_auth_manager(class_file_storage: FileStorage) -> AuthManager:
    """Create a class-scoped AuthManager instance for integration tests."""
    return AuthManager(
        storage=class_file_storage,
        jwt_secret_key="test_secret_key_for_testing_only",
        access_token_expire_minutes=30
    )


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "created_at": datetime(2024, 1, 1, 12, 0, 0),
        "updated_at": datetime(2024, 1, 1, 12, 0, 0)
    }


@pytest.fixture
def sample_auth_method_data():
    """Sample auth method data for testing."""
    return {
        "id": "auth-123",
        "user_id": "test-user-123",
        "provider": "local",
        "provider_user_id": "testuser",
        "credentials": {"password_hash": "hashed_password"},
        "created_at": datetime(2024, 1, 1, 12, 0, 0)
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        "session_id": "session-123",
        "user_id": "test-user-123",
        "created_at": datetime(2024, 1, 1, 12, 0, 0),
        "last_activity": datetime(2024, 1, 1, 13, 0, 0),
        "metadata": {"ip": "127.0.0.1", "user_agent": "test"}
    }


@pytest.fixture
def mock_storage() -> AsyncMock:
    """Creates a mock storage backend for testing."""
    mock = AsyncMock(spec=StorageBackend)
    mock.exists = AsyncMock(return_value=True)
    mock.append = AsyncMock()
    mock.write_bytes = AsyncMock()
    # Mock the lock method to return an async context manager
    async_context_manager = AsyncMock()
    async_context_manager.__aenter__ = AsyncMock(return_value=None)
    async_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock.lock = MagicMock(return_value=async_context_manager)
    return mock


@pytest.fixture
def chat_logger(mock_storage: AsyncMock) -> ChatLogger:
    """Creates a ChatLogger instance with a mock storage backend."""
    return ChatLogger(storage_backend=mock_storage)


