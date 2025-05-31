"""Google Cloud Storage backend implementation."""

import json
import time
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, AsyncGenerator

from .storage import StorageBackend, LockAcquisitionError, GCSStorageConfig
from .exceptions import StorageError
from .models import User, UserAuthMethod, SessionData
from .time_utils import utc_now

try:
    from google.cloud import storage as gcs
    from google.cloud.exceptions import NotFound, Conflict
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

logger = logging.getLogger(__name__)


class GCSStorageBackend(StorageBackend):
    """
    Google Cloud Storage backend with object-based locking.
    
    Implements the StorageBackend interface using GCS objects for data storage
    and GCS object operations for distributed locking. Uses GCS's strong
    consistency guarantees for reliable locking.
    
    Locking Strategy:
    - object: Uses GCS conditional operations (if_generation_match=0) for atomic lock creation
    - redis: Falls back to Redis-based locking (requires Redis configuration)
    - file: Not supported for GCS backend
    """

    def __init__(self, config: GCSStorageConfig):
        if not GCS_AVAILABLE:
            raise StorageError("google-cloud-storage package not installed")
        
        self.config = config
        self.bucket_name = config.bucket
        self.prefix = config.prefix.rstrip('/') + '/' if config.prefix else ''
        
        # Initialize GCS client
        if config.credentials_file:
            self.client = gcs.Client.from_service_account_json(
                config.credentials_file,
                project=config.project_id
            )
        else:
            self.client = gcs.Client(project=config.project_id)
        
        self.bucket = self.client.bucket(self.bucket_name)
        
        # Validate locking strategy
        if config.lock.strategy == "file":
            raise StorageError("File-based locking not supported for GCS backend")
        
        # Generate unique instance ID for lock ownership
        self.instance_id = str(uuid.uuid4())

    def _get_key(self, path: str) -> str:
        """Convert a storage path to a GCS object key."""
        return f"{self.prefix}{path}"

    def _get_lock_key(self, resource_path: str) -> str:
        """Get the lock object key for a resource."""
        return f"{self.prefix}.locks/{resource_path.replace('/', '_')}"

    @asynccontextmanager
    async def lock(self, resource_path: str, timeout: float = 5.0) -> AsyncGenerator[None, None]:
        """
        Acquire a GCS object-based lock for a resource.
        
        Uses GCS conditional operations for atomic lock acquisition.
        Creates a lock object with if_generation_match=0 to ensure atomicity.
        
        Args:
            resource_path: The resource path to lock
            timeout: Maximum time to wait for lock acquisition
            
        Yields:
            None
            
        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        if self.config.lock.strategy == "redis":
            # TODO: Implement Redis-based locking
            raise NotImplementedError("Redis-based locking not yet implemented")
        
        # Use object-based locking
        lock_key = self._get_lock_key(resource_path)
        lock_blob = self.bucket.blob(lock_key)
        
        # Lock metadata
        lock_data = {
            "owner": self.instance_id,
            "resource": resource_path,
            "acquired_at": utc_now().isoformat(),
            "expires_at": (utc_now().timestamp() + self.config.lock.lease_duration_seconds)
        }
        
        acquired = False
        start_time = time.time()
        
        lock_data_str = json.dumps(lock_data)
        
        for attempt in range(self.config.lock.retry_attempts):
            # Check overall timeout before each attempt
            if time.time() - start_time >= timeout:
                break
                
            try:
                # Try to create lock object atomically (if_generation_match=0 means object must not exist)
                await asyncio.to_thread(
                    lock_blob.upload_from_string,
                    lock_data_str,
                    content_type='application/json',
                    if_generation_match=0
                )
                acquired = True
                logger.debug(f"GCS lock acquired for {resource_path} on attempt {attempt + 1}")
                break
                
            except Conflict:
                # Lock object already exists, check if it's expired
                try:
                    existing_lock_text = await asyncio.to_thread(lock_blob.download_as_text)
                    existing_lock_data = json.loads(existing_lock_text)
                    
                    if existing_lock_data.get("expires_at", 0) < time.time():
                        # Lock is expired, try to delete it and retry
                        logger.info(
                            f"Stale GCS lock detected for {resource_path}. "
                            f"Owner: {existing_lock_data.get('owner')}. Attempting to delete."
                        )
                        try:
                            await asyncio.to_thread(lock_blob.delete)
                            logger.info(f"Stale GCS lock for {resource_path} deleted. Retrying acquisition.")
                            # Continue to next attempt to re-acquire immediately
                        except NotFound:
                            logger.info(
                                f"Stale GCS lock for {resource_path} already deleted by another process. "
                                f"Retrying acquisition."
                            )
                        except Exception as e_del:
                            logger.warning(
                                f"Failed to delete stale GCS lock for {resource_path}: {e_del}. "
                                f"Will retry acquisition."
                            )
                    else:
                        # Lock exists and is not expired
                        logger.debug(
                            f"GCS lock for {resource_path} is held by {existing_lock_data.get('owner')}. "
                            f"Waiting before retry (attempt {attempt + 1}/{self.config.lock.retry_attempts})"
                        )
                        if time.time() - start_time >= timeout:
                            break
                        await asyncio.sleep(self.config.lock.retry_delay_seconds)
                        
                except NotFound:
                    # Lock was deleted between Conflict and download_as_text, good to retry
                    logger.info(f"GCS lock for {resource_path} disappeared during conflict check. Retrying acquisition.")
                except json.JSONDecodeError:
                    logger.warning(f"GCS lock file for {resource_path} is corrupted. Attempting to delete and retry.")
                    try:
                        await asyncio.to_thread(lock_blob.delete)
                    except Exception:
                        pass  # Best effort
                except Exception as e_conflict_check:
                    logger.error(f"Error checking existing GCS lock for {resource_path}: {e_conflict_check}")
                    if time.time() - start_time >= timeout:
                        break
                    await asyncio.sleep(self.config.lock.retry_delay_seconds)
            
            except Exception as e:
                logger.error(f"Unexpected error acquiring GCS lock for {resource_path}: {e}")
                raise LockAcquisitionError(f"Failed to acquire lock for {resource_path}: {e}")
        
        if not acquired:
            raise LockAcquisitionError(
                f"Failed to acquire lock for {resource_path} within {timeout} seconds"
            )
        
        try:
            yield
        finally:
            # Release the lock
            # Note: We delete without checking ownership since if_generation_match=0 during
            # acquisition ensures only one process should believe it holds this lock
            try:
                await asyncio.to_thread(lock_blob.delete)
                logger.debug(f"GCS lock released for {resource_path}")
            except NotFound:
                logger.debug(f"GCS lock for {resource_path} was already released or expired")
            except Exception as e:
                logger.warning(f"Error releasing GCS lock for {resource_path}: {e}")

    async def read(self, path: str) -> str:
        """Read text data from GCS."""
        key = self._get_key(path)
        blob = self.bucket.blob(key)
        
        try:
            return await asyncio.to_thread(blob.download_as_text, encoding='utf-8')
        except NotFound:
            raise StorageError(f"Path not found: {path}")
        except Exception as e:
            raise StorageError(f"Failed to read {path}: {e}")

    async def write(self, path: str, data: str) -> None:
        """Write text data to GCS."""
        key = self._get_key(path)
        blob = self.bucket.blob(key)
        
        try:
            await asyncio.to_thread(blob.upload_from_string, data, content_type='text/plain; charset=utf-8')
        except Exception as e:
            raise StorageError(f"Failed to write {path}: {e}")

    async def append(self, path: str, data: str) -> None:
        """Append text data to GCS object."""
        # GCS doesn't support native append, so we read, concatenate, and write
        try:
            existing_data = await self.read(path)
            new_data = existing_data + data
        except StorageError:
            # File doesn't exist, create it
            new_data = data
        
        await self.write(path, new_data)

    async def read_bytes(self, path: str) -> bytes:
        """Read binary data from GCS."""
        key = self._get_key(path)
        blob = self.bucket.blob(key)
        
        try:
            return await asyncio.to_thread(blob.download_as_bytes)
        except NotFound:
            raise StorageError(f"Path not found: {path}")
        except Exception as e:
            raise StorageError(f"Failed to read {path}: {e}")

    async def write_bytes(self, path: str, data: bytes) -> None:
        """Write binary data to GCS."""
        key = self._get_key(path)
        blob = self.bucket.blob(key)
        
        try:
            await asyncio.to_thread(blob.upload_from_string, data, content_type='application/octet-stream')
        except Exception as e:
            raise StorageError(f"Failed to write {path}: {e}")

    async def append_bytes(self, path: str, data: bytes) -> None:
        """Append binary data to GCS object."""
        # GCS doesn't support native append, so we read, concatenate, and write
        try:
            existing_data = await self.read_bytes(path)
            new_data = existing_data + data
        except StorageError:
            # File doesn't exist, create it
            new_data = data
        
        await self.write_bytes(path, new_data)

    async def exists(self, path: str) -> bool:
        """Check if a GCS object exists."""
        key = self._get_key(path)
        blob = self.bucket.blob(key)
        return await asyncio.to_thread(blob.exists)

    async def delete(self, path: str) -> bool:
        """Delete a GCS object."""
        key = self._get_key(path)
        blob = self.bucket.blob(key)
        
        try:
            await asyncio.to_thread(blob.delete)
            return True
        except NotFound:
            return False
        except Exception as e:
            raise StorageError(f"Failed to delete {path}: {e}")

    async def list_keys(self, prefix: str) -> List[str]:
        """List all GCS objects with the given prefix."""
        search_prefix = self._get_key(prefix)
        keys = []
        
        try:
            # Run the blocking list_blobs operation in a thread
            def _list_blobs():
                result = []
                for blob in self.client.list_blobs(self.bucket, prefix=search_prefix):
                    # Remove the storage prefix to get the original key
                    key = blob.name
                    if key.startswith(self.prefix):
                        key = key[len(self.prefix):]
                        # Skip lock files and hidden files
                        if not key.startswith('.locks/') and not key.startswith('.'):
                            result.append(key)
                return result
            
            keys = await asyncio.to_thread(_list_blobs)
        except Exception as e:
            raise StorageError(f"Failed to list keys with prefix {prefix}: {e}")
        
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
        # More efficient implementation would use a username index
        user_keys = await self.list_keys("users/")
        
        for key in user_keys:
            if key.endswith("/profile"):
                user_data = await self._read_json(key)
                if user_data and user_data.get("username") == username:
                    return User(**user_data)
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        # More efficient implementation would use an email index
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
        # This requires scanning all users - could be optimized with an index
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