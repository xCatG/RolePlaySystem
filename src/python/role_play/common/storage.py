"""Storage abstraction layer for the Role Play System."""

import json
import os
import signal
from abc import ABC, abstractmethod
from contextlib import contextmanager, asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator, Union, Literal, AsyncGenerator
from pydantic import BaseModel, Field
import asyncio
import aiofiles
import aiofiles.os

from .exceptions import StorageError
from .models import User, UserAuthMethod, SessionData
from .time_utils import utc_now


class LockAcquisitionError(StorageError):
    """Raised when a lock cannot be acquired."""
    pass


# Configuration models for locking strategies
class LockConfig(BaseModel):
    """Configuration for locking strategies."""
    strategy: Literal["object", "redis", "file"] = Field(
        default="file",
        description="Locking strategy: 'object' for cloud storage object locks, "
                    "'redis' for Redis-based locks, 'file' for local file locks."
    )
    lease_duration_seconds: int = Field(
        default=60,
        description="Lock lease duration in seconds (critical for 'object' and 'redis' strategies)"
    )
    retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for lock acquisition"
    )
    retry_delay_seconds: float = Field(
        default=1.0,
        description="Delay between retry attempts in seconds"
    )
    
    # Redis-specific settings (used if strategy is 'redis')
    redis_host: Optional[str] = Field(
        default=None,
        description="Redis host (required for redis strategy)"
    )
    redis_port: Optional[int] = Field(
        default=6379,
        description="Redis port"
    )
    redis_password: Optional[str] = Field(
        default=None,
        description="Redis password"
    )
    redis_db: Optional[int] = Field(
        default=0,
        description="Redis database number"
    )
    
    # File-lock specific (used by FileStorage)
    file_lock_dir: Optional[str] = Field(
        default=None,
        description="Directory for file locks (defaults to storage_dir/.locks)"
    )


# Base storage configuration
class BaseStorageConfig(BaseModel):
    """Base configuration for all storage backends."""
    type: str
    lock: LockConfig = Field(default_factory=LockConfig)


class FileStorageConfig(BaseStorageConfig):
    """Configuration for file-based storage."""
    type: Literal["file"] = "file"
    base_dir: str = Field(description="Base directory for file storage")
    lock: LockConfig = Field(
        default_factory=lambda: LockConfig(strategy="file"),
        description="Lock configuration (defaults to file-based locking)"
    )


class GCSStorageConfig(BaseStorageConfig):
    """Configuration for Google Cloud Storage."""
    type: Literal["gcs"] = "gcs"
    bucket: str = Field(description="GCS bucket name")
    prefix: str = Field(default="", description="Key prefix for all objects")
    project_id: Optional[str] = Field(default=None, description="GCP project ID")
    credentials_file: Optional[str] = Field(
        default=None,
        description="Path to service account credentials JSON file"
    )
    lock: LockConfig = Field(
        default_factory=lambda: LockConfig(strategy="object"),
        description="Lock configuration (defaults to object-based locking)"
    )


class S3StorageConfig(BaseStorageConfig):
    """Configuration for AWS S3 storage."""
    type: Literal["s3"] = "s3"
    bucket: str = Field(description="S3 bucket name")
    prefix: str = Field(default="", description="Key prefix for all objects")
    region_name: Optional[str] = Field(default=None, description="AWS region")
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key")
    endpoint_url: Optional[str] = Field(
        default=None,
        description="Custom S3-compatible endpoint URL"
    )
    lock: LockConfig = Field(
        default_factory=lambda: LockConfig(strategy="object"),
        description="Lock configuration (defaults to object-based locking)"
    )


# Union type for all storage configs
StorageConfigUnion = Union[FileStorageConfig, GCSStorageConfig, S3StorageConfig]


class StorageBackend(ABC):
    """
    Abstract base class for storage backends with locking support.
    
    All implementations must be thread-safe and support distributed locking
    for production use. The locking mechanism is configurable per implementation.
    
    This uses a string-first approach since most data is JSON/text, with
    optional bytes methods for binary data when needed.
    """

    @abstractmethod
    @asynccontextmanager
    async def lock(self, resource_path: str, timeout: float = 5.0) -> AsyncGenerator[None, None]:
        """
        Acquire an exclusive lock for a resource.
        
        Args:
            resource_path: The resource path to lock
            timeout: Maximum time to wait for lock acquisition
            
        Yields:
            None
            
        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        pass  # pragma: no cover

    @abstractmethod
    async def read(self, path: str) -> str:
        """Read text data from storage."""
        pass  # pragma: no cover

    @abstractmethod
    async def write(self, path: str, data: str) -> None:
        """Write text data to storage."""
        pass  # pragma: no cover

    @abstractmethod
    async def append(self, path: str, data: str) -> None:
        """Append text data to storage."""
        pass  # pragma: no cover

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a path exists in storage."""
        pass  # pragma: no cover

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a path from storage."""
        pass  # pragma: no cover

    @abstractmethod
    async def list_keys(self, prefix: str) -> List[str]:
        """List all keys with the given prefix."""
        pass  # pragma: no cover

    # Optional bytes methods for binary data (can be overridden for efficiency)
    async def read_bytes(self, path: str) -> bytes:
        """Read binary data. Default implementation converts from string."""
        return (await self.read(path)).encode('utf-8')

    async def write_bytes(self, path: str, data: bytes) -> None:
        """Write binary data. Default implementation converts to string."""
        await self.write(path, data.decode('utf-8'))

    async def append_bytes(self, path: str, data: bytes) -> None:
        """Append binary data. Default implementation converts to string."""
        await self.append(path, data.decode('utf-8'))

    # High-level user management methods
    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        pass  # pragma: no cover

    @abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        pass  # pragma: no cover

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        pass  # pragma: no cover

    @abstractmethod
    async def create_user(self, user: User) -> User:
        """Create a new user."""
        pass  # pragma: no cover

    @abstractmethod
    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        pass  # pragma: no cover

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        pass  # pragma: no cover

    @abstractmethod
    async def get_user_auth_methods(self, user_id: str) -> List[UserAuthMethod]:
        """Get all auth methods for a user."""
        pass  # pragma: no cover

    @abstractmethod
    async def get_user_auth_method(
        self, provider: str, provider_user_id: str
    ) -> Optional[UserAuthMethod]:
        """Get auth method by provider and provider user ID."""
        pass  # pragma: no cover

    @abstractmethod
    async def create_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Create a new auth method for a user."""
        pass  # pragma: no cover

    @abstractmethod
    async def update_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Update an existing auth method."""
        pass  # pragma: no cover

    @abstractmethod
    async def delete_user_auth_method(self, auth_method_id: str) -> bool:
        """Delete an auth method."""
        pass  # pragma: no cover

    @abstractmethod
    async def create_session(self, session: SessionData) -> SessionData:
        """Create a new session."""
        pass  # pragma: no cover

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        pass  # pragma: no cover

    @abstractmethod
    async def update_session(self, session: SessionData) -> SessionData:
        """Update an existing session."""
        pass  # pragma: no cover

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        pass  # pragma: no cover

    @abstractmethod
    async def store_data(self, key: str, data: Any) -> None:
        """Store arbitrary data."""
        pass  # pragma: no cover

    @abstractmethod
    async def get_data(self, key: str) -> Optional[Any]:
        """Get arbitrary data."""
        pass  # pragma: no cover

    @abstractmethod
    async def delete_data(self, key: str) -> bool:
        """Delete arbitrary data."""
        pass  # pragma: no cover


class FileStorage(StorageBackend):
    """
    File-based storage backend with file locking support.
    
    Uses filelock for thread-safe operations and implements per-user
    data segmentation. Suitable for development and single-server deployments.
    """

    def __init__(self, config: FileStorageConfig):
        self.config = config
        self.storage_dir = Path(config.base_dir).resolve()
        self.storage_dir.mkdir(exist_ok=True)
        
        # Create lock directory
        self.locks_dir = self.storage_dir / ".locks"
        self.locks_dir.mkdir(exist_ok=True)

    def _get_lock_path(self, resource_path: str) -> Path:
        """Get the lock file path for a resource."""
        # Replace path separators with underscores for flat lock directory
        lock_name = resource_path.replace('/', '_') + '.lock'
        return self.locks_dir / lock_name

    @asynccontextmanager
    async def lock(self, resource_path: str, timeout: float = 5.0) -> AsyncGenerator[None, None]:
        """
        Acquire a file-based lock for a resource.
        
        Args:
            resource_path: The resource path to lock
            timeout: Maximum time to wait for lock acquisition
            
        Yields:
            None
            
        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        lock_path = self._get_lock_path(resource_path)
        
        # Use a simpler file-based locking approach that works better with asyncio
        start_time = asyncio.get_event_loop().time()
        acquired = False
        
        while not acquired and (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                # Try to create lock file exclusively (atomic operation)
                await aiofiles.os.makedirs(lock_path.parent, exist_ok=True)
                
                # Create lock data with PID and timestamp for stale lock detection
                lock_data = {
                    "pid": os.getpid(),
                    "timestamp": asyncio.get_event_loop().time(),
                    "resource": resource_path
                }
                lock_content = json.dumps(lock_data)
                
                # Use exclusive creation to implement the lock
                fd = await asyncio.to_thread(
                    os.open, str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                await asyncio.to_thread(os.write, fd, lock_content.encode('utf-8'))
                await asyncio.to_thread(os.close, fd)
                acquired = True
                
            except FileExistsError:
                # Lock file already exists, check if it's stale
                if await self._is_stale_lock(lock_path, self.config.lock.lease_duration_seconds):
                    # Try to remove stale lock and retry immediately
                    try:
                        await aiofiles.os.remove(str(lock_path))
                        continue  # Retry immediately without sleeping
                    except FileNotFoundError:
                        continue  # Already removed, retry immediately
                    except Exception:
                        pass  # Could not remove, treat as active lock
                
                # Lock is active, wait and retry
                await asyncio.sleep(0.1)
            except Exception as e:
                raise StorageError(f"Error acquiring lock: {e}")
        
        if not acquired:
            raise LockAcquisitionError(
                f"Failed to acquire lock for {resource_path} within {timeout} seconds"
            )
        
        try:
            yield
        finally:
            # Always try to release the lock by removing the lock file
            try:
                await aiofiles.os.remove(str(lock_path))
            except FileNotFoundError:
                # Lock file already removed, ignore
                pass
            except Exception:
                # Ignore other release errors to prevent masking original exceptions
                pass

    async def _is_stale_lock(self, lock_path: Path, lease_duration_seconds: float) -> bool:
        """
        Check if a lock file is stale (from a dead process or too old).
        
        Args:
            lock_path: Path to the lock file
            lease_duration_seconds: Maximum lease duration for a lock before considering it stale
            
        Returns:
            True if the lock appears to be stale and should be removed
        """
        try:
            # Read lock file content
            async with aiofiles.open(lock_path, 'r') as f:
                content = await f.read()
            
            lock_data = json.loads(content)
            lock_pid = lock_data.get("pid")
            lock_timestamp = lock_data.get("timestamp", 0)
            
            # Check age-based staleness first (simpler and cross-platform)
            current_time = asyncio.get_event_loop().time()
            if current_time - lock_timestamp > lease_duration_seconds:
                return True
            
            # Check if process is still running (if PID is available)
            if lock_pid:
                try:
                    # Send signal 0 to check if process exists (doesn't actually send signal)
                    await asyncio.to_thread(os.kill, lock_pid, 0)
                    # Process exists, lock is not stale
                    return False
                except ProcessLookupError:
                    # Process doesn't exist, lock is stale
                    return True
                except PermissionError:
                    # Process exists but we can't signal it, assume it's active
                    return False
                except Exception:
                    # Unknown error, err on the side of caution
                    return False
            
            # No PID info, rely on age check only
            return False
            
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # Lock file is malformed or missing, consider it stale
            return True
        except Exception:
            # Any other error, err on the side of caution
            return False

    def _get_storage_path(self, key: str) -> Path:
        """Convert a storage key to an actual file path."""
        # Ensure key doesn't escape storage directory
        if '..' in key:
            raise StorageError(f"Invalid key: {key}")
        
        return self.storage_dir / key

    async def read(self, path: str) -> str:
        """Read text data from a file."""
        file_path = self._get_storage_path(path)
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
        except FileNotFoundError:
            raise StorageError(f"Path not found: {path}")
        except IOError as e:
            raise StorageError(f"Failed to read {path}: {e}")

    async def write(self, path: str, data: str) -> None:
        """Write text data to a file."""
        file_path = self._get_storage_path(path)
        
        # Create parent directories if needed
        await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)
        
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(data)
        except IOError as e:
            raise StorageError(f"Failed to write {path}: {e}")

    async def append(self, path: str, data: str) -> None:
        """Append text data to a file."""
        file_path = self._get_storage_path(path)
        
        # Create parent directories if needed
        await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)
        
        try:
            async with aiofiles.open(file_path, 'a', encoding='utf-8') as f:
                await f.write(data)
        except IOError as e:
            raise StorageError(f"Failed to append to {path}: {e}")

    # Override bytes methods for better efficiency with actual file operations
    async def read_bytes(self, path: str) -> bytes:
        """Read binary data from a file."""
        file_path = self._get_storage_path(path)
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except FileNotFoundError:
            raise StorageError(f"Path not found: {path}")
        except IOError as e:
            raise StorageError(f"Failed to read {path}: {e}")

    async def write_bytes(self, path: str, data: bytes) -> None:
        """Write binary data to a file."""
        file_path = self._get_storage_path(path)
        
        # Create parent directories if needed
        await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)
        
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(data)
        except IOError as e:
            raise StorageError(f"Failed to write {path}: {e}")

    async def append_bytes(self, path: str, data: bytes) -> None:
        """Append binary data to a file."""
        file_path = self._get_storage_path(path)
        
        # Create parent directories if needed
        await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)
        
        try:
            async with aiofiles.open(file_path, 'ab') as f:
                await f.write(data)
        except IOError as e:
            raise StorageError(f"Failed to append to {path}: {e}")

    async def exists(self, path: str) -> bool:
        """Check if a file exists."""
        file_path = self._get_storage_path(path)
        return await asyncio.to_thread(file_path.exists)

    async def delete(self, path: str) -> bool:
        """Delete a file."""
        file_path = self._get_storage_path(path)
        if await asyncio.to_thread(file_path.exists):
            await asyncio.to_thread(file_path.unlink)
            return True
        return False

    async def list_keys(self, prefix: str) -> List[str]:
        """List all keys with the given prefix."""
        prefix_path = self._get_storage_path(prefix)
        keys = []
        
        if await asyncio.to_thread(prefix_path.exists):
            # Run the blocking rglob operation in a thread
            def _list_files():
                result = []
                for file_path in prefix_path.rglob('*'):
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        # Convert back to storage key format
                        relative_path = file_path.relative_to(self.storage_dir)
                        result.append(str(relative_path))
                return result
            
            keys = await asyncio.to_thread(_list_files)
        
        return keys

    # Helper methods for JSON data
    async def _read_json(self, path: str) -> Optional[Dict[str, Any]]:
        """Read and parse JSON data."""
        try:
            data = await self.read(path)
            return json.loads(data)
        except StorageError:
            return None
        except json.JSONDecodeError as e:
            raise StorageError(f"Failed to parse JSON from {path}: {e}")

    async def _write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write data as JSON."""
        json_str = json.dumps(data, indent=2, default=str)
        await self.write(path, json_str)

    # User management implementation
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        user_path = f"users/{user_id}/profile"
        user_data = await self._read_json(user_path)
        if user_data:
            return User(**user_data)
        return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        # This is inefficient for file storage, but works for development
        user_keys = await self.list_keys("users/")
        
        for key in user_keys:
            if key.endswith("/profile"):
                user_data = await self._read_json(key)
                if user_data and user_data.get("username") == username:
                    return User(**user_data)
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        # This is inefficient for file storage, but works for development
        user_keys = await self.list_keys("users/")
        
        for key in user_keys:
            if key.endswith("/profile"):
                user_data = await self._read_json(key)
                if user_data and user_data.get("email") == email:
                    return User(**user_data)
        return None

    async def create_user(self, user: User) -> User:
        """Create a new user."""
        user_path = f"users/{user.id}/profile"
        
        if await self.exists(user_path):
            raise StorageError(f"User {user.id} already exists")
        
        async with self.lock(user_path):
            await self._write_json(user_path, user.model_dump())
        
        return user

    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        user_path = f"users/{user.id}/profile"
        
        if not await self.exists(user_path):
            raise StorageError(f"User {user.id} not found")
        
        user.updated_at = utc_now()
        
        async with self.lock(user_path):
            await self._write_json(user_path, user.model_dump())
        
        return user

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user and all their data."""
        user_dir = f"users/{user_id}"
        
        # Delete all user data
        user_keys = await self.list_keys(user_dir)
        for key in user_keys:
            await self.delete(key)
        
        return True

    async def get_user_auth_methods(self, user_id: str) -> List[UserAuthMethod]:
        """Get all auth methods for a user."""
        auth_methods = []
        auth_keys = await self.list_keys(f"users/{user_id}/auth_methods/")
        
        for key in auth_keys:
            auth_data = await self._read_json(key)
            if auth_data:
                auth_methods.append(UserAuthMethod(**auth_data))
        
        return auth_methods

    async def get_user_auth_method(
        self, provider: str, provider_user_id: str
    ) -> Optional[UserAuthMethod]:
        """Get auth method by provider and provider user ID."""
        # This requires scanning all users - inefficient but works for development
        user_keys = await self.list_keys("users/")
        
        for key in user_keys:
            if "/auth_methods/" in key:
                auth_data = await self._read_json(key)
                if (auth_data and 
                    auth_data.get("provider") == provider and 
                    auth_data.get("provider_user_id") == provider_user_id):
                    return UserAuthMethod(**auth_data)
        return None

    async def create_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Create a new auth method for a user."""
        auth_path = f"users/{auth_method.user_id}/auth_methods/{auth_method.id}"
        
        if await self.exists(auth_path):
            raise StorageError(f"Auth method {auth_method.id} already exists")
        
        async with self.lock(auth_path):
            await self._write_json(auth_path, auth_method.model_dump())
        
        return auth_method

    async def update_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Update an existing auth method."""
        auth_path = f"users/{auth_method.user_id}/auth_methods/{auth_method.id}"
        
        if not await self.exists(auth_path):
            raise StorageError(f"Auth method {auth_method.id} not found")
        
        async with self.lock(auth_path):
            await self._write_json(auth_path, auth_method.model_dump())
        
        return auth_method

    async def delete_user_auth_method(self, auth_method_id: str) -> bool:
        """Delete an auth method."""
        # Need to find the auth method first to get user_id
        user_keys = await self.list_keys("users/")
        
        for key in user_keys:
            if key.endswith(f"/auth_methods/{auth_method_id}"):
                return await self.delete(key)
        
        return False

    async def create_session(self, session: SessionData) -> SessionData:
        """Create a new session."""
        session_path = f"sessions/{session.session_id}"
        
        if await self.exists(session_path):
            raise StorageError(f"Session {session.session_id} already exists")
        
        async with self.lock(session_path):
            await self._write_json(session_path, session.model_dump())
        
        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        session_path = f"sessions/{session_id}"
        session_data = await self._read_json(session_path)
        if session_data:
            return SessionData(**session_data)
        return None

    async def update_session(self, session: SessionData) -> SessionData:
        """Update an existing session."""
        session_path = f"sessions/{session.session_id}"
        
        if not await self.exists(session_path):
            raise StorageError(f"Session {session.session_id} not found")
        
        async with self.lock(session_path):
            await self._write_json(session_path, session.model_dump())
        
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_path = f"sessions/{session_id}"
        return await self.delete(session_path)

    async def store_data(self, key: str, data: Any) -> None:
        """Store arbitrary data."""
        data_path = f"data/{key}"
        
        async with self.lock(data_path):
            await self._write_json(data_path, {"data": data})

    async def get_data(self, key: str) -> Optional[Any]:
        """Get arbitrary data."""
        data_path = f"data/{key}"
        file_data = await self._read_json(data_path)
        if file_data:
            return file_data.get("data")
        return None

    async def delete_data(self, key: str) -> bool:
        """Delete arbitrary data."""
        data_path = f"data/{key}"
        return await self.delete(data_path)