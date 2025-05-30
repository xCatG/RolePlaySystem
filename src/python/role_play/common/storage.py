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


class FileStorage(StorageBackend):
    """
    File-based storage backend for development and testing.
    
    WARNING: This implementation is NOT thread-safe and should only be used
    for development, testing, or single-user scenarios. For production use
    with multiple concurrent users, implement proper file locking or use
    a database/S3 backend instead.
    """

    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        self.users_dir = self.storage_dir / "users"
        self.auth_methods_dir = self.storage_dir / "auth_methods"
        self.sessions_dir = self.storage_dir / "sessions"
        self.data_dir = self.storage_dir / "data"
        
        for dir_path in [self.users_dir, self.auth_methods_dir, self.sessions_dir, self.data_dir]:
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


class GCSStorage(StorageBackend):
    """
    Google Cloud Storage backend for production deployments.
    
    This implementation stores JSON objects in GCS bucket with folder structure
    similar to FileStorage for consistency.
    """

    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        prefix: str = ""
    ):
        """
        Initialize GCS storage backend.
        
        Args:
            bucket_name: GCS bucket name
            project_id: GCP project ID (optional if using default credentials)
            credentials_path: Path to service account JSON file (optional)
            prefix: Object key prefix for namespacing (e.g., "dev/", "prod/")
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