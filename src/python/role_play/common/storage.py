"""Storage abstraction layer for the Role Play System."""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import StorageError
from .models import User, UserAuthMethod, SessionData
from .time_utils import utc_now

try:
    from filelock import FileLock, Timeout
    FILELOCK_AVAILABLE = True
except ImportError:
    FILELOCK_AVAILABLE = False

try:
    from google.cloud import storage as gcs
    from google.auth.exceptions import DefaultCredentialsError
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import BotoCoreError, NoCredentialsError
    AWS_S3_AVAILABLE = True
except ImportError:
    AWS_S3_AVAILABLE = False

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

import asyncio
import uuid
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta


class DistributedLockMixin:
    """
    Mixin for adding distributed locking capabilities to storage backends.
    Supports Redis-based locking for cloud storage backends.
    """
    
    def __init__(self, *args, redis_url: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_client = None
        self.instance_id = str(uuid.uuid4())
        
        if redis_url and REDIS_AVAILABLE:
            self.redis_client = redis.from_url(redis_url)
            print("Distributed locking enabled with Redis")
        elif redis_url and not REDIS_AVAILABLE:
            print("Redis URL provided but redis package not available. Install with: pip install redis")
    
    @asynccontextmanager
    async def _acquire_distributed_lock(self, lock_key: str, timeout: int = 5):
        """
        Acquire a distributed lock for the given key.
        
        Args:
            lock_key: Key to lock
            timeout: Lock timeout in seconds
        """
        if not self.redis_client:
            # Fallback to no locking if Redis not available
            yield
            return
        
        full_lock_key = f"rps:lock:{lock_key}"
        acquired = False
        
        try:
            # Try to acquire lock
            acquired = await self.redis_client.set(
                full_lock_key,
                self.instance_id,
                nx=True,  # Only set if not exists
                ex=timeout  # Expire after timeout seconds
            )
            
            if not acquired:
                raise StorageError(f"Could not acquire distributed lock for {lock_key}")
            
            yield
            
        finally:
            if acquired and self.redis_client:
                # Release lock only if we own it
                lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                try:
                    await self.redis_client.eval(lua_script, 1, full_lock_key, self.instance_id)
                except Exception as e:
                    print(f"Warning: Failed to release lock {lock_key}: {e}")
    
    async def close(self):
        """Close Redis connection if open."""
        if self.redis_client:
            await self.redis_client.close()


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.
    
    WARNING: Implementations should be thread-safe for production use.
    FileStorage is suitable for development/testing but not for high-concurrency
    environments. Consider S3Storage or database backends for production scaling.
    """

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        pass

    @abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        pass

    @abstractmethod
    async def create_user(self, user: User) -> User:
        """Create a new user."""
        pass

    @abstractmethod
    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        pass

    @abstractmethod
    async def get_user_auth_methods(self, user_id: str) -> List[UserAuthMethod]:
        """Get all auth methods for a user."""
        pass

    @abstractmethod
    async def get_user_auth_method(
        self, provider: str, provider_user_id: str
    ) -> Optional[UserAuthMethod]:
        """Get auth method by provider and provider user ID."""
        pass

    @abstractmethod
    async def create_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Create a new auth method for a user."""
        pass

    @abstractmethod
    async def update_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Update an existing auth method."""
        pass

    @abstractmethod
    async def delete_user_auth_method(self, auth_method_id: str) -> bool:
        """Delete an auth method."""
        pass

    @abstractmethod
    async def create_session(self, session: SessionData) -> SessionData:
        """Create a new session."""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        pass

    @abstractmethod
    async def update_session(self, session: SessionData) -> SessionData:
        """Update an existing session."""
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        pass

    @abstractmethod
    async def store_data(self, key: str, data: Any) -> None:
        """Store arbitrary data."""
        pass

    @abstractmethod
    async def get_data(self, key: str) -> Optional[Any]:
        """Get arbitrary data."""
        pass

    @abstractmethod
    async def delete_data(self, key: str) -> bool:
        """Delete arbitrary data."""
        pass

    @abstractmethod
    async def append_to_log(self, log_key: str, data: Any) -> None:
        """
        Append data to a log file (JSONL format).
        
        This operation must be atomic and thread-safe. For file storage,
        this uses file locking. For cloud storage, this uses atomic operations.
        
        Args:
            log_key: Key identifying the log file
            data: Data to append (will be JSON serialized)
        """
        pass

    @abstractmethod
    async def read_log(self, log_key: str) -> List[Any]:
        """
        Read all entries from a log file.
        
        Returns:
            List of deserialized entries from the log
        """
        pass

    @abstractmethod
    async def log_exists(self, log_key: str) -> bool:
        """Check if a log file exists."""
        pass

    @abstractmethod
    async def delete_log(self, log_key: str) -> bool:
        """Delete a log file."""
        pass


class FileStorage(StorageBackend):
    """
    File-based storage backend for development and testing.
    
    WARNING: This implementation is NOT thread-safe and should only be used
    for development, testing, or single-user scenarios. For production use
    with multiple concurrent users, implement proper file locking or use
    a database/S3 backend instead.
    """

    def __init__(self, storage_dir: str = "data"):
        if not FILELOCK_AVAILABLE:
            raise ImportError(
                "filelock is required for FileStorage. "
                "Install with: pip install filelock"
            )
            
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        self.users_dir = self.storage_dir / "users"
        self.auth_methods_dir = self.storage_dir / "auth_methods"
        self.sessions_dir = self.storage_dir / "sessions"
        self.data_dir = self.storage_dir / "data"
        self.logs_dir = self.storage_dir / "logs"
        
        for dir_path in [self.users_dir, self.auth_methods_dir, self.sessions_dir, self.data_dir, self.logs_dir]:
            dir_path.mkdir(exist_ok=True)

    def _read_json_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Read and parse JSON file."""
        try:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    return json.load(f)
            return None
        except (json.JSONDecodeError, IOError) as e:
            raise StorageError(f"Failed to read file {file_path}: {e}")

    def _write_json_file(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Write data to JSON file."""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except IOError as e:
            raise StorageError(f"Failed to write file {file_path}: {e}")

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        user_file = self.users_dir / f"{user_id}.json"
        user_data = self._read_json_file(user_file)
        if user_data:
            return User(**user_data)
        return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        for user_file in self.users_dir.glob("*.json"):
            user_data = self._read_json_file(user_file)
            if user_data and user_data.get("username") == username:
                return User(**user_data)
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        for user_file in self.users_dir.glob("*.json"):
            user_data = self._read_json_file(user_file)
            if user_data and user_data.get("email") == email:
                return User(**user_data)
        return None

    async def create_user(self, user: User) -> User:
        """Create a new user."""
        user_file = self.users_dir / f"{user.id}.json"
        if user_file.exists():
            raise StorageError(f"User {user.id} already exists")
        
        self._write_json_file(user_file, user.model_dump())
        return user

    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        user_file = self.users_dir / f"{user.id}.json"
        if not user_file.exists():
            raise StorageError(f"User {user.id} not found")
        
        user.updated_at = utc_now()
        self._write_json_file(user_file, user.model_dump())
        return user

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        user_file = self.users_dir / f"{user_id}.json"
        if user_file.exists():
            user_file.unlink()
            return True
        return False

    async def get_user_auth_methods(self, user_id: str) -> List[UserAuthMethod]:
        """Get all auth methods for a user."""
        auth_methods = []
        for auth_file in self.auth_methods_dir.glob("*.json"):
            auth_data = self._read_json_file(auth_file)
            if auth_data and auth_data.get("user_id") == user_id:
                auth_methods.append(UserAuthMethod(**auth_data))
        return auth_methods

    async def get_user_auth_method(
        self, provider: str, provider_user_id: str
    ) -> Optional[UserAuthMethod]:
        """Get auth method by provider and provider user ID."""
        for auth_file in self.auth_methods_dir.glob("*.json"):
            auth_data = self._read_json_file(auth_file)
            if (auth_data and 
                auth_data.get("provider") == provider and 
                auth_data.get("provider_user_id") == provider_user_id):
                return UserAuthMethod(**auth_data)
        return None

    async def create_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Create a new auth method for a user."""
        auth_file = self.auth_methods_dir / f"{auth_method.id}.json"
        if auth_file.exists():
            raise StorageError(f"Auth method {auth_method.id} already exists")
        
        self._write_json_file(auth_file, auth_method.model_dump())
        return auth_method

    async def update_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Update an existing auth method."""
        auth_file = self.auth_methods_dir / f"{auth_method.id}.json"
        if not auth_file.exists():
            raise StorageError(f"Auth method {auth_method.id} not found")
        
        self._write_json_file(auth_file, auth_method.model_dump())
        return auth_method

    async def delete_user_auth_method(self, auth_method_id: str) -> bool:
        """Delete an auth method."""
        auth_file = self.auth_methods_dir / f"{auth_method_id}.json"
        if auth_file.exists():
            auth_file.unlink()
            return True
        return False

    async def create_session(self, session: SessionData) -> SessionData:
        """Create a new session."""
        session_file = self.sessions_dir / f"{session.session_id}.json"
        if session_file.exists():
            raise StorageError(f"Session {session.session_id} already exists")
        
        self._write_json_file(session_file, session.model_dump())
        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        session_file = self.sessions_dir / f"{session_id}.json"
        session_data = self._read_json_file(session_file)
        if session_data:
            return SessionData(**session_data)
        return None

    async def update_session(self, session: SessionData) -> SessionData:
        """Update an existing session."""
        session_file = self.sessions_dir / f"{session.session_id}.json"
        if not session_file.exists():
            raise StorageError(f"Session {session.session_id} not found")
        
        self._write_json_file(session_file, session.model_dump())
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False

    async def store_data(self, key: str, data: Any) -> None:
        """Store arbitrary data."""
        data_file = self.data_dir / f"{key}.json"
        self._write_json_file(data_file, {"data": data})

    async def get_data(self, key: str) -> Optional[Any]:
        """Get arbitrary data."""
        data_file = self.data_dir / f"{key}.json"
        file_data = self._read_json_file(data_file)
        if file_data:
            return file_data.get("data")
        return None

    async def delete_data(self, key: str) -> bool:
        """Delete arbitrary data."""
        data_file = self.data_dir / f"{key}.json"
        if data_file.exists():
            data_file.unlink()
            return True
        return False

    def _get_log_path(self, log_key: str) -> Path:
        """Get the path for a log file."""
        return self.logs_dir / f"{log_key}.jsonl"

    def _get_lock_path(self, file_path: Path) -> Path:
        """Get the lock file path for a given file."""
        return Path(f"{file_path}.lock")

    async def append_to_log(self, log_key: str, data: Any) -> None:
        """Append data to a log file with file locking."""
        log_file = self._get_log_path(log_key)
        lock_file = self._get_lock_path(log_file)
        
        try:
            with FileLock(lock_file, timeout=5):
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(data, default=str) + '\n')
        except Timeout:
            raise StorageError(f"Timeout acquiring lock for log {log_key}")
        except Exception as e:
            raise StorageError(f"Failed to append to log {log_key}: {e}")

    async def read_log(self, log_key: str) -> List[Any]:
        """Read all entries from a log file with file locking."""
        log_file = self._get_log_path(log_key)
        if not log_file.exists():
            return []
        
        lock_file = self._get_lock_path(log_file)
        entries = []
        
        try:
            with FileLock(lock_file, timeout=5):
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except json.JSONDecodeError:
                                # Skip malformed lines
                                continue
        except Timeout:
            raise StorageError(f"Timeout acquiring lock for reading log {log_key}")
        except Exception as e:
            raise StorageError(f"Failed to read log {log_key}: {e}")
        
        return entries

    async def log_exists(self, log_key: str) -> bool:
        """Check if a log file exists."""
        return self._get_log_path(log_key).exists()

    async def delete_log(self, log_key: str) -> bool:
        """Delete a log file."""
        log_file = self._get_log_path(log_key)
        if log_file.exists():
            log_file.unlink()
            return True
        return False


class GCSStorage(DistributedLockMixin, StorageBackend):
    """
    Google Cloud Storage backend for production deployments.
    
    This implementation stores JSON objects in GCS bucket with folder structure
    similar to FileStorage for consistency. Supports optional Redis-based
    distributed locking for high-concurrency scenarios.
    """

    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        prefix: str = "",
        redis_url: Optional[str] = None
    ):
        """
        Initialize GCS storage backend.
        
        Args:
            bucket_name: GCS bucket name
            project_id: GCP project ID (optional if using default credentials)
            credentials_path: Path to service account JSON file (optional)
            prefix: Object key prefix for namespacing (e.g., "dev/", "prod/")
            redis_url: Redis URL for distributed locking (optional)
        """
        if not GOOGLE_CLOUD_AVAILABLE:
            raise ImportError(
                "google-cloud-storage is required for GCS backend. "
                "Install with: pip install google-cloud-storage"
            )
        
        self.bucket_name = bucket_name
        self.project_id = project_id
        self.prefix = prefix.rstrip('/') + '/' if prefix else ''
        
        try:
            if credentials_path:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            self.client = gcs.Client(project=project_id)
            self.bucket = self.client.bucket(bucket_name)
            
            # Test connectivity
            if not self.bucket.exists():
                raise StorageError(f"GCS bucket '{bucket_name}' does not exist or is not accessible")
                
        except (DefaultCredentialsError, Exception) as e:
            raise StorageError(f"Failed to initialize GCS storage: {e}")
        
        # Initialize distributed locking mixin
        super().__init__(redis_url=redis_url)

    def _get_object_key(self, category: str, key: str) -> str:
        """Generate object key with prefix and category."""
        return f"{self.prefix}{category}/{key}.json"

    async def _store_object(self, key: str, data: Dict[str, Any]) -> None:
        """Store JSON object in GCS."""
        try:
            blob = self.bucket.blob(key)
            blob.upload_from_string(
                json.dumps(data, indent=2, default=str),
                content_type='application/json'
            )
        except Exception as e:
            raise StorageError(f"Failed to store object {key}: {e}")

    async def _get_object(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON object from GCS."""
        try:
            blob = self.bucket.blob(key)
            if not blob.exists():
                return None
            
            content = blob.download_as_text()
            return json.loads(content)
        except Exception as e:
            raise StorageError(f"Failed to get object {key}: {e}")

    async def _delete_object(self, key: str) -> bool:
        """Delete object from GCS."""
        try:
            blob = self.bucket.blob(key)
            if blob.exists():
                blob.delete()
                return True
            return False
        except Exception as e:
            raise StorageError(f"Failed to delete object {key}: {e}")

    async def _list_objects_in_category(self, category: str) -> List[Dict[str, Any]]:
        """List all objects in a category."""
        try:
            prefix = f"{self.prefix}{category}/"
            blobs = self.bucket.list_blobs(prefix=prefix)
            objects = []
            
            for blob in blobs:
                content = blob.download_as_text()
                objects.append(json.loads(content))
            
            return objects
        except Exception as e:
            raise StorageError(f"Failed to list objects in category {category}: {e}")

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        key = self._get_object_key("users", user_id)
        user_data = await self._get_object(key)
        return User(**user_data) if user_data else None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        users = await self._list_objects_in_category("users")
        for user_data in users:
            if user_data.get("username") == username:
                return User(**user_data)
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        users = await self._list_objects_in_category("users")
        for user_data in users:
            if user_data.get("email") == email:
                return User(**user_data)
        return None

    async def create_user(self, user: User) -> User:
        """Create a new user."""
        key = self._get_object_key("users", user.id)
        
        # Check if user already exists
        if await self._get_object(key):
            raise StorageError(f"User {user.id} already exists")
        
        await self._store_object(key, user.model_dump())
        return user

    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        key = self._get_object_key("users", user.id)
        
        # Check if user exists
        if not await self._get_object(key):
            raise StorageError(f"User {user.id} not found")
        
        user.updated_at = utc_now()
        await self._store_object(key, user.model_dump())
        return user

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        key = self._get_object_key("users", user_id)
        return await self._delete_object(key)

    async def get_user_auth_methods(self, user_id: str) -> List[UserAuthMethod]:
        """Get all auth methods for a user."""
        auth_methods = await self._list_objects_in_category("auth_methods")
        return [
            UserAuthMethod(**auth_data)
            for auth_data in auth_methods
            if auth_data.get("user_id") == user_id
        ]

    async def get_user_auth_method(
        self, provider: str, provider_user_id: str
    ) -> Optional[UserAuthMethod]:
        """Get auth method by provider and provider user ID."""
        auth_methods = await self._list_objects_in_category("auth_methods")
        for auth_data in auth_methods:
            if (auth_data.get("provider") == provider and 
                auth_data.get("provider_user_id") == provider_user_id):
                return UserAuthMethod(**auth_data)
        return None

    async def create_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Create a new auth method for a user."""
        key = self._get_object_key("auth_methods", auth_method.id)
        
        # Check if auth method already exists
        if await self._get_object(key):
            raise StorageError(f"Auth method {auth_method.id} already exists")
        
        await self._store_object(key, auth_method.model_dump())
        return auth_method

    async def update_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Update an existing auth method."""
        key = self._get_object_key("auth_methods", auth_method.id)
        
        # Check if auth method exists
        if not await self._get_object(key):
            raise StorageError(f"Auth method {auth_method.id} not found")
        
        await self._store_object(key, auth_method.model_dump())
        return auth_method

    async def delete_user_auth_method(self, auth_method_id: str) -> bool:
        """Delete an auth method."""
        key = self._get_object_key("auth_methods", auth_method_id)
        return await self._delete_object(key)

    async def create_session(self, session: SessionData) -> SessionData:
        """Create a new session."""
        key = self._get_object_key("sessions", session.session_id)
        
        # Check if session already exists
        if await self._get_object(key):
            raise StorageError(f"Session {session.session_id} already exists")
        
        await self._store_object(key, session.model_dump())
        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        key = self._get_object_key("sessions", session_id)
        session_data = await self._get_object(key)
        return SessionData(**session_data) if session_data else None

    async def update_session(self, session: SessionData) -> SessionData:
        """Update an existing session."""
        key = self._get_object_key("sessions", session.session_id)
        
        # Check if session exists
        if not await self._get_object(key):
            raise StorageError(f"Session {session.session_id} not found")
        
        await self._store_object(key, session.model_dump())
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        key = self._get_object_key("sessions", session_id)
        return await self._delete_object(key)

    async def store_data(self, key: str, data: Any) -> None:
        """Store arbitrary data."""
        object_key = self._get_object_key("data", key)
        await self._store_object(object_key, {"data": data})

    async def get_data(self, key: str) -> Optional[Any]:
        """Get arbitrary data."""
        object_key = self._get_object_key("data", key)
        file_data = await self._get_object(object_key)
        return file_data.get("data") if file_data else None

    async def delete_data(self, key: str) -> bool:
        """Delete arbitrary data."""
        object_key = self._get_object_key("data", key)
        return await self._delete_object(object_key)

    def _get_log_object_key(self, log_key: str) -> str:
        """Generate object key for log files."""
        return f"{self.prefix}logs/{log_key}.jsonl"

    async def append_to_log(self, log_key: str, data: Any) -> None:
        """
        Append data to a log file in S3.
        
        Note: S3 doesn't support true append operations, so we read-modify-write.
        This is atomic at the object level but has race conditions with concurrent writes.
        For production, consider using DynamoDB or SQS for high-concurrency logging.
        """
        object_key = self._get_log_object_key(log_key)
        
        try:
            # Read existing content
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
                existing_content = response['Body'].read().decode('utf-8')
            except self.s3_client.exceptions.NoSuchKey:
                existing_content = ""
            
            # Append new line
            new_line = json.dumps(data, default=str) + '\n'
            updated_content = existing_content + new_line
            
            # Write back atomically
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=updated_content,
                ContentType='application/x-jsonlines'
            )
        except Exception as e:
            raise StorageError(f"Failed to append to log {log_key}: {e}")

    async def read_log(self, log_key: str) -> List[Any]:
        """Read all entries from a log file in S3."""
        object_key = self._get_log_object_key(log_key)
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
            content = response['Body'].read().decode('utf-8')
            entries = []
            
            for line in content.splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
            
            return entries
        except self.s3_client.exceptions.NoSuchKey:
            return []
        except Exception as e:
            raise StorageError(f"Failed to read log {log_key}: {e}")

    async def log_exists(self, log_key: str) -> bool:
        """Check if a log file exists in S3."""
        object_key = self._get_log_object_key(log_key)
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except self.s3_client.exceptions.NoSuchKey:
            return False
        except Exception as e:
            raise StorageError(f"Failed to check log existence {log_key}: {e}")

    async def delete_log(self, log_key: str) -> bool:
        """Delete a log file from S3."""
        object_key = self._get_log_object_key(log_key)
        return await self._delete_object(object_key)


class S3Storage(StorageBackend):
    """
    AWS S3 storage backend for production deployments.
    
    This implementation stores JSON objects in S3 bucket with folder structure
    similar to FileStorage for consistency.
    """

    def __init__(
        self,
        bucket_name: str,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        prefix: str = ""
    ):
        """
        Initialize S3 storage backend.
        
        Args:
            bucket_name: S3 bucket name
            region_name: AWS region (default: us-east-1)
            aws_access_key_id: AWS access key (optional, uses IAM roles if not provided)
            aws_secret_access_key: AWS secret key (optional, uses IAM roles if not provided)
            prefix: Object key prefix for namespacing (e.g., "dev/", "prod/")
        """
        if not AWS_S3_AVAILABLE:
            raise ImportError(
                "boto3 is required for S3 backend. "
                "Install with: pip install boto3"
            )
        
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.prefix = prefix.rstrip('/') + '/' if prefix else ''
        
        try:
            # Create S3 client with optional credentials
            session_kwargs = {"region_name": region_name}
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key
                })
            
            session = boto3.Session(**session_kwargs)
            self.s3_client = session.client('s3')
            
            # Test connectivity
            self.s3_client.head_bucket(Bucket=bucket_name)
                
        except (NoCredentialsError, BotoCoreError, Exception) as e:
            raise StorageError(f"Failed to initialize S3 storage: {e}")

    def _get_object_key(self, category: str, key: str) -> str:
        """Generate object key with prefix and category."""
        return f"{self.prefix}{category}/{key}.json"

    async def _store_object(self, key: str, data: Dict[str, Any]) -> None:
        """Store JSON object in S3."""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(data, indent=2, default=str),
                ContentType='application/json'
            )
        except Exception as e:
            raise StorageError(f"Failed to store object {key}: {e}")

    async def _get_object(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON object from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except self.s3_client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            raise StorageError(f"Failed to get object {key}: {e}")

    async def _delete_object(self, key: str) -> bool:
        """Delete object from S3."""
        try:
            # Check if object exists first
            try:
                self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            except self.s3_client.exceptions.NoSuchKey:
                return False
            
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            raise StorageError(f"Failed to delete object {key}: {e}")

    async def _list_objects_in_category(self, category: str) -> List[Dict[str, Any]]:
        """List all objects in a category."""
        try:
            prefix = f"{self.prefix}{category}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            objects = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    obj_response = self.s3_client.get_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key']
                    )
                    content = obj_response['Body'].read().decode('utf-8')
                    objects.append(json.loads(content))
            
            return objects
        except Exception as e:
            raise StorageError(f"Failed to list objects in category {category}: {e}")

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        key = self._get_object_key("users", user_id)
        user_data = await self._get_object(key)
        return User(**user_data) if user_data else None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        users = await self._list_objects_in_category("users")
        for user_data in users:
            if user_data.get("username") == username:
                return User(**user_data)
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        users = await self._list_objects_in_category("users")
        for user_data in users:
            if user_data.get("email") == email:
                return User(**user_data)
        return None

    async def create_user(self, user: User) -> User:
        """Create a new user."""
        key = self._get_object_key("users", user.id)
        
        # Check if user already exists
        if await self._get_object(key):
            raise StorageError(f"User {user.id} already exists")
        
        await self._store_object(key, user.model_dump())
        return user

    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        key = self._get_object_key("users", user.id)
        
        # Check if user exists
        if not await self._get_object(key):
            raise StorageError(f"User {user.id} not found")
        
        user.updated_at = utc_now()
        await self._store_object(key, user.model_dump())
        return user

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        key = self._get_object_key("users", user_id)
        return await self._delete_object(key)

    async def get_user_auth_methods(self, user_id: str) -> List[UserAuthMethod]:
        """Get all auth methods for a user."""
        auth_methods = await self._list_objects_in_category("auth_methods")
        return [
            UserAuthMethod(**auth_data)
            for auth_data in auth_methods
            if auth_data.get("user_id") == user_id
        ]

    async def get_user_auth_method(
        self, provider: str, provider_user_id: str
    ) -> Optional[UserAuthMethod]:
        """Get auth method by provider and provider user ID."""
        auth_methods = await self._list_objects_in_category("auth_methods")
        for auth_data in auth_methods:
            if (auth_data.get("provider") == provider and 
                auth_data.get("provider_user_id") == provider_user_id):
                return UserAuthMethod(**auth_data)
        return None

    async def create_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Create a new auth method for a user."""
        key = self._get_object_key("auth_methods", auth_method.id)
        
        # Check if auth method already exists
        if await self._get_object(key):
            raise StorageError(f"Auth method {auth_method.id} already exists")
        
        await self._store_object(key, auth_method.model_dump())
        return auth_method

    async def update_user_auth_method(self, auth_method: UserAuthMethod) -> UserAuthMethod:
        """Update an existing auth method."""
        key = self._get_object_key("auth_methods", auth_method.id)
        
        # Check if auth method exists
        if not await self._get_object(key):
            raise StorageError(f"Auth method {auth_method.id} not found")
        
        await self._store_object(key, auth_method.model_dump())
        return auth_method

    async def delete_user_auth_method(self, auth_method_id: str) -> bool:
        """Delete an auth method."""
        key = self._get_object_key("auth_methods", auth_method_id)
        return await self._delete_object(key)

    async def create_session(self, session: SessionData) -> SessionData:
        """Create a new session."""
        key = self._get_object_key("sessions", session.session_id)
        
        # Check if session already exists
        if await self._get_object(key):
            raise StorageError(f"Session {session.session_id} already exists")
        
        await self._store_object(key, session.model_dump())
        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        key = self._get_object_key("sessions", session_id)
        session_data = await self._get_object(key)
        return SessionData(**session_data) if session_data else None

    async def update_session(self, session: SessionData) -> SessionData:
        """Update an existing session."""
        key = self._get_object_key("sessions", session.session_id)
        
        # Check if session exists
        if not await self._get_object(key):
            raise StorageError(f"Session {session.session_id} not found")
        
        await self._store_object(key, session.model_dump())
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        key = self._get_object_key("sessions", session_id)
        return await self._delete_object(key)

    async def store_data(self, key: str, data: Any) -> None:
        """Store arbitrary data."""
        object_key = self._get_object_key("data", key)
        await self._store_object(object_key, {"data": data})

    async def get_data(self, key: str) -> Optional[Any]:
        """Get arbitrary data."""
        object_key = self._get_object_key("data", key)
        file_data = await self._get_object(object_key)
        return file_data.get("data") if file_data else None

    async def delete_data(self, key: str) -> bool:
        """Delete arbitrary data."""
        object_key = self._get_object_key("data", key)
        return await self._delete_object(object_key)

    def _get_log_object_key(self, log_key: str) -> str:
        """Generate object key for log files."""
        return f"{self.prefix}logs/{log_key}.jsonl"

    async def append_to_log(self, log_key: str, data: Any) -> None:
        """
        Append data to a log file in S3.
        
        Note: S3 doesn't support true append operations, so we read-modify-write.
        This is atomic at the object level but has race conditions with concurrent writes.
        For production, consider using DynamoDB or SQS for high-concurrency logging.
        """
        object_key = self._get_log_object_key(log_key)
        
        try:
            # Read existing content
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
                existing_content = response['Body'].read().decode('utf-8')
            except self.s3_client.exceptions.NoSuchKey:
                existing_content = ""
            
            # Append new line
            new_line = json.dumps(data, default=str) + '\n'
            updated_content = existing_content + new_line
            
            # Write back atomically
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=updated_content,
                ContentType='application/x-jsonlines'
            )
        except Exception as e:
            raise StorageError(f"Failed to append to log {log_key}: {e}")

    async def read_log(self, log_key: str) -> List[Any]:
        """Read all entries from a log file in S3."""
        object_key = self._get_log_object_key(log_key)
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
            content = response['Body'].read().decode('utf-8')
            entries = []
            
            for line in content.splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
            
            return entries
        except self.s3_client.exceptions.NoSuchKey:
            return []
        except Exception as e:
            raise StorageError(f"Failed to read log {log_key}: {e}")

    async def log_exists(self, log_key: str) -> bool:
        """Check if a log file exists in S3."""
        object_key = self._get_log_object_key(log_key)
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except self.s3_client.exceptions.NoSuchKey:
            return False
        except Exception as e:
            raise StorageError(f"Failed to check log existence {log_key}: {e}")

    async def delete_log(self, log_key: str) -> bool:
        """Delete a log file from S3."""
        object_key = self._get_log_object_key(log_key)
        return await self._delete_object(object_key)