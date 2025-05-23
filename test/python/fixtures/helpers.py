"""Test helper functions and utilities."""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

from role_play.common.storage import StorageBackend


def assert_user_equal(user1, user2):
    """Assert that two User objects are equal."""
    assert user1.id == user2.id
    assert user1.username == user2.username
    assert user1.email == user2.email
    assert user1.role == user2.role
    assert user1.is_active == user2.is_active


def assert_auth_method_equal(auth1, auth2):
    """Assert that two UserAuthMethod objects are equal."""
    assert auth1.id == auth2.id
    assert auth1.user_id == auth2.user_id
    assert auth1.provider == auth2.provider
    assert auth1.provider_user_id == auth2.provider_user_id
    assert auth1.credentials == auth2.credentials
    assert auth1.is_active == auth2.is_active


def assert_session_equal(session1, session2):
    """Assert that two SessionData objects are equal."""
    assert session1.session_id == session2.session_id
    assert session1.user_id == session2.user_id
    assert session1.metadata == session2.metadata


def create_temp_json_file(data: Dict[str, Any]) -> Path:
    """Create a temporary JSON file with the given data."""
    temp_file = Path(tempfile.mktemp(suffix=".json"))
    with open(temp_file, 'w') as f:
        json.dump(data, f, default=str)
    return temp_file


class MockStorageBackend(StorageBackend):
    """Mock storage backend for testing."""
    
    def __init__(self):
        self.users = {}
        self.auth_methods = {}
        self.sessions = {}
        self.data = {}
    
    async def get_user(self, user_id: str):
        return self.users.get(user_id)
    
    async def get_user_by_username(self, username: str):
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    async def create_user(self, user):
        self.users[user.id] = user
        return user
    
    async def update_user(self, user):
        self.users[user.id] = user
        return user
    
    async def delete_user(self, user_id: str):
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False
    
    async def get_user_auth_methods(self, user_id: str):
        return [auth for auth in self.auth_methods.values() if auth.user_id == user_id]
    
    async def get_user_auth_method(self, provider: str, provider_user_id: str):
        for auth in self.auth_methods.values():
            if auth.provider == provider and auth.provider_user_id == provider_user_id:
                return auth
        return None
    
    async def create_user_auth_method(self, auth_method):
        self.auth_methods[auth_method.id] = auth_method
        return auth_method
    
    async def update_user_auth_method(self, auth_method):
        self.auth_methods[auth_method.id] = auth_method
        return auth_method
    
    async def delete_user_auth_method(self, auth_method_id: str):
        if auth_method_id in self.auth_methods:
            del self.auth_methods[auth_method_id]
            return True
        return False
    
    async def create_session(self, session):
        self.sessions[session.session_id] = session
        return session
    
    async def get_session(self, session_id: str):
        return self.sessions.get(session_id)
    
    async def update_session(self, session):
        self.sessions[session.session_id] = session
        return session
    
    async def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    async def store_data(self, key: str, data: Any):
        self.data[key] = data
    
    async def get_data(self, key: str):
        return self.data.get(key)
    
    async def delete_data(self, key: str):
        if key in self.data:
            del self.data[key]
            return True
        return False