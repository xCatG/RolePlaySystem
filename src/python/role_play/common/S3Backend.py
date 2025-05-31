"""
AWS S3 Storage backend implementation (STUB).

⚠️  PRODUCTION WARNING: This S3 backend uses object-based locking which provides
only BEST-EFFORT guarantees due to S3's consistency model. For production use:

1. ALWAYS use Redis locking strategy instead of object locking
2. Monitor lock contention metrics closely
3. Consider using DynamoDB for user/auth lookups instead of S3 scanning
4. Be aware that append operations are expensive (full read-modify-write)

See config/storage-examples.yaml for Redis configuration examples.
"""

import json
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, AsyncGenerator

from .storage import StorageBackend, LockAcquisitionError, S3StorageConfig
from .exceptions import StorageError
from .models import User, UserAuthMethod, SessionData
from .time_utils import utc_now

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False


class S3StorageBackend(StorageBackend):
    """
    AWS S3 Storage backend with best-effort object-based locking (STUB IMPLEMENTATION).
    
    This is a stub implementation for AWS S3 storage. The locking mechanism
    provides best-effort guarantees due to S3's eventual consistency model.
    
    Locking Strategy Documentation:
    - object: Best-effort locking using S3 object operations with GET-after-PUT verification
    - redis: Recommended for production - uses Redis for strong consistency (requires Redis config)
    - file: Not supported for S3 backend
    
    ⚠️  WARNING: This is a STUB implementation. The object-based locking strategy
    for S3 is simplified and may not be suitable for high-contention scenarios.
    For production use, consider using the redis locking strategy instead.
    
    Production Recommendations:
    - Use redis locking strategy for mission-critical scenarios
    - Monitor lock acquisition metrics to detect contention issues
    - Consider implementing proper S3 object versioning for more robust locking
    - S3's best-effort locking is NOT suitable for high-concurrency or financial data
    
    ⚠️  IMPORTANT: For production deployments, configure Redis locking:
    storage:
      type: s3
      bucket: my-bucket
      lock:
        strategy: redis  # <-- STRONGLY RECOMMENDED for S3 production
        redis_host: redis.example.com
        redis_port: 6379
    """

    def __init__(self, config: S3StorageConfig):
        if not S3_AVAILABLE:
            raise StorageError("boto3 package not installed")
        
        self.config = config
        self.bucket_name = config.bucket
        self.prefix = config.prefix.rstrip('/') + '/' if config.prefix else ''
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=config.region_name,
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=config.aws_secret_access_key,
                endpoint_url=config.endpoint_url
            )
        except NoCredentialsError:
            raise StorageError("AWS credentials not configured")
        
        # Validate locking strategy
        if config.lock.strategy == "file":
            raise StorageError("File-based locking not supported for S3 backend")
        
        # Warn about object-based locking limitations
        if config.lock.strategy == "object":
            import warnings
            warnings.warn(
                "⚠️  S3 object-based locking provides only BEST-EFFORT guarantees. "
                "For production use with S3, configure Redis locking instead. "
                "See storage-examples.yaml for Redis configuration examples.",
                UserWarning,
                stacklevel=2
            )
        
        # Generate unique instance ID for lock ownership
        self.instance_id = str(uuid.uuid4())

    def _get_key(self, path: str) -> str:
        """Convert a storage path to an S3 object key."""
        return f"{self.prefix}{path}"

    def _get_lock_key(self, resource_path: str) -> str:
        """Get the lock object key for a resource."""
        return f"{self.prefix}.locks/{resource_path.replace('/', '_')}"

    @asynccontextmanager
    async def lock(self, resource_path: str, timeout: float = 5.0) -> AsyncGenerator[None, None]:
        """
        Acquire an S3 object-based lock for a resource (BEST-EFFORT IMPLEMENTATION).
        
        ⚠️  WARNING: This is a simplified best-effort locking mechanism.
        For production use with high contention, use redis locking strategy instead.
        
        The implementation uses S3 PutObject with GET-after-PUT verification,
        but due to S3's eventual consistency, race conditions may occur under
        extreme conditions or network partitions.
        
        Args:
            resource_path: The resource path to lock
            timeout: Maximum time to wait for lock acquisition
            
        Yields:
            None
            
        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        if self.config.lock.strategy == "redis":
            # TODO: Implement Redis-based locking (STRONGLY RECOMMENDED FOR PRODUCTION)
            raise NotImplementedError(
                "Redis-based locking not yet implemented but is STRONGLY RECOMMENDED for S3 production use. "
                "The object-based locking below is a simplified best-effort implementation that may have "
                "race conditions under high load. Please implement Redis locking before production deployment."
            )
        
        # Use simplified object-based locking (BEST-EFFORT)
        lock_key = self._get_lock_key(resource_path)
        
        # Lock metadata
        lock_data = {
            "owner": self.instance_id,
            "resource": resource_path,
            "acquired_at": utc_now().isoformat(),
            "expires_at": (utc_now().timestamp() + self.config.lock.lease_duration_seconds)
        }
        
        acquired = False
        start_time = time.time()
        
        for attempt in range(self.config.lock.retry_attempts):
            try:
                # Try to create lock object
                await asyncio.to_thread(
                    self.s3_client.put_object,
                    Bucket=self.bucket_name,
                    Key=lock_key,
                    Body=json.dumps(lock_data),
                    ContentType='application/json'
                )
                
                # Verify we actually own the lock (GET-after-PUT verification)
                # This helps detect race conditions but doesn't eliminate them entirely
                await asyncio.sleep(0.1)  # Brief delay to account for S3 propagation
                
                try:
                    response = await asyncio.to_thread(self.s3_client.get_object, Bucket=self.bucket_name, Key=lock_key)
                    body_content = await asyncio.to_thread(response['Body'].read)
                    existing_lock_data = json.loads(body_content.decode('utf-8'))
                    
                    if existing_lock_data.get("owner") == self.instance_id:
                        acquired = True
                        break
                    else:
                        # Someone else acquired the lock, check if it's expired
                        if existing_lock_data.get("expires_at", 0) < time.time():
                            # Try to delete expired lock and retry
                            try:
                                await asyncio.to_thread(self.s3_client.delete_object, Bucket=self.bucket_name, Key=lock_key)
                            except ClientError:
                                pass  # May have been deleted by someone else
                        
                except ClientError:
                    # Lock object disappeared, retry
                    pass
                    
            except ClientError as e:
                # Handle various S3 errors
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ['NoSuchBucket', 'AccessDenied']:
                    raise LockAcquisitionError(f"S3 error acquiring lock for {resource_path}: {e}")
                # For other errors, continue retrying
            
            if time.time() - start_time >= timeout:
                break
            
            await asyncio.sleep(self.config.lock.retry_delay_seconds)
        
        if not acquired:
            raise LockAcquisitionError(
                f"Failed to acquire S3 lock for {resource_path} within {timeout} seconds"
            )
        
        try:
            yield
        finally:
            # Release the lock (best effort)
            try:
                await asyncio.to_thread(self.s3_client.delete_object, Bucket=self.bucket_name, Key=lock_key)
            except ClientError:
                pass  # Lock may have expired or been cleaned up

    async def read(self, path: str) -> str:
        """Read text data from S3."""
        # TODO: Implement S3 read operation
        raise NotImplementedError("S3 read operation not yet implemented")

    async def write(self, path: str, data: str) -> None:
        """Write text data to S3."""
        # TODO: Implement S3 write operation
        raise NotImplementedError("S3 write operation not yet implemented")

    async def append(self, path: str, data: str) -> None:
        """Append text data to S3 object."""
        # TODO: Implement S3 append operation (read + concatenate + write)
        # WARNING: S3 doesn't support native append. This operation requires:
        # 1. Acquire lock (use Redis in production!)
        # 2. Read existing object
        # 3. Concatenate data
        # 4. Write back entire object
        # 5. Release lock
        # This is expensive and prone to race conditions without proper locking!
        raise NotImplementedError("S3 append operation not yet implemented - requires careful locking strategy")

    async def read_bytes(self, path: str) -> bytes:
        """Read binary data from S3."""
        # TODO: Implement S3 binary read operation
        raise NotImplementedError("S3 binary read operation not yet implemented")

    async def write_bytes(self, path: str, data: bytes) -> None:
        """Write binary data to S3."""
        # TODO: Implement S3 binary write operation
        raise NotImplementedError("S3 binary write operation not yet implemented")

    async def append_bytes(self, path: str, data: bytes) -> None:
        """Append binary data to S3 object."""
        # TODO: Implement S3 binary append operation
        raise NotImplementedError("S3 binary append operation not yet implemented")

    async def exists(self, path: str) -> bool:
        """Check if an S3 object exists."""
        # TODO: Implement S3 exists check
        raise NotImplementedError("S3 exists check not yet implemented")

    async def delete(self, path: str) -> bool:
        """Delete an S3 object."""
        # TODO: Implement S3 delete operation
        raise NotImplementedError("S3 delete operation not yet implemented")

    async def list_keys(self, prefix: str) -> List[str]:
        """List all S3 objects with the given prefix."""
        # TODO: Implement S3 list operation
        raise NotImplementedError("S3 list operation not yet implemented")

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

    # User management implementation (all methods use the base CRUD operations)
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        user_path = f"users/{user_id}/profile"
        user_data = await self._read_json(user_path)
        if user_data:
            return User(**user_data)
        return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        # WARNING: This implementation requires listing and reading all user profiles.
        # For production with many users, consider maintaining a username index in DynamoDB
        # or using a proper database for user lookups instead of S3 scanning.
        user_keys = await self.list_keys("users/")
        
        for key in user_keys:
            if key.endswith("/profile"):
                user_data = await self._read_json(key)
                if user_data and user_data.get("username") == username:
                    return User(**user_data)
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
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
        
        with self.lock(user_path):
            await self._write_json(user_path, user.model_dump())
        
        return user

    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        user_path = f"users/{user.id}/profile"
        
        if not await self.exists(user_path):
            raise StorageError(f"User {user.id} not found")
        
        user.updated_at = utc_now()
        
        with self.lock(user_path):
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
        
        with self.lock(auth_path):
            await self._write_json(auth_path, auth_method.model_dump())
        
        return auth_method

    async def update_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Update an existing auth method."""
        auth_path = f"users/{auth_method.user_id}/auth_methods/{auth_method.id}"
        
        if not await self.exists(auth_path):
            raise StorageError(f"Auth method {auth_method.id} not found")
        
        with self.lock(auth_path):
            await self._write_json(auth_path, auth_method.model_dump())
        
        return auth_method

    async def delete_user_auth_method(self, auth_method_id: str) -> bool:
        """Delete an auth method."""
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
        
        with self.lock(session_path):
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
        
        with self.lock(session_path):
            await self._write_json(session_path, session.model_dump())
        
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_path = f"sessions/{session_id}"
        return await self.delete(session_path)

    async def store_data(self, key: str, data: Any) -> None:
        """Store arbitrary data."""
        data_path = f"data/{key}"
        
        with self.lock(data_path):
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