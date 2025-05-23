"""Storage abstraction layer for the Role Play System."""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import StorageError
from .models import User, UserAuthMethod, SessionData


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

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
    """File-based storage backend for development and testing."""

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
        
        user.updated_at = datetime.now()
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