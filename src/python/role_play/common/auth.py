"""Authentication and authorization utilities."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext

from .exceptions import (
    AuthenticationError,
    InvalidTokenError,
    TokenExpiredError,
    UserNotFoundError,
)
from .models import AuthProvider, TokenData, User, UserAuthMethod, UserRole
from .storage import StorageBackend


class AuthManager:
    """Manages authentication and authorization."""

    def __init__(
        self,
        storage: StorageBackend,
        jwt_secret_key: str,
        jwt_algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
    ):
        self.storage = storage
        self.jwt_secret_key = jwt_secret_key
        self.jwt_algorithm = jwt_algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def _hash_password(self, password: str) -> str:
        """Hash a password."""
        return self.pwd_context.hash(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def _create_access_token(self, user: User) -> str:
        """Create a JWT access token."""
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        token_data = TokenData(
            user_id=user.id,
            username=user.username,
            role=user.role,
            exp=int(expire.timestamp()),
        )
        return jwt.encode(
            token_data.model_dump(), self.jwt_secret_key, algorithm=self.jwt_algorithm
        )

    def verify_token(self, token: str) -> TokenData:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(
                token, self.jwt_secret_key, algorithms=[self.jwt_algorithm]
            )
            token_data = TokenData(**payload)
            
            # Check if token is expired
            if datetime.utcnow().timestamp() > token_data.exp:
                raise TokenExpiredError("Token has expired")
            
            return token_data
        except jwt.InvalidTokenError:
            raise InvalidTokenError("Invalid token")
        except Exception as e:
            raise InvalidTokenError(f"Token verification failed: {e}")

    async def register_user(
        self, username: str, email: Optional[str] = None, password: Optional[str] = None
    ) -> tuple[User, str]:
        """Register a new user with local authentication."""
        # Check if user already exists
        existing_user = await self.storage.get_user_by_username(username)
        if existing_user:
            raise AuthenticationError("User already exists")

        # Create user
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            username=username,
            email=email,
            role=UserRole.USER,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        await self.storage.create_user(user)

        # Create local auth method if password provided
        if password:
            hashed_password = self._hash_password(password)
            auth_method = UserAuthMethod(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider=AuthProvider.LOCAL,
                provider_user_id=username,
                credentials={"password_hash": hashed_password},
                created_at=datetime.now(),
            )
            await self.storage.create_user_auth_method(auth_method)

        # Generate access token
        access_token = self._create_access_token(user)
        return user, access_token

    async def authenticate_user(self, username: str, password: str) -> tuple[User, str]:
        """Authenticate user with username and password."""
        # Get user
        user = await self.storage.get_user_by_username(username)
        if not user or not user.is_active:
            raise UserNotFoundError("User not found or inactive")

        # Get local auth method
        auth_method = await self.storage.get_user_auth_method(
            AuthProvider.LOCAL, username
        )
        if not auth_method or not auth_method.is_active:
            raise AuthenticationError("Local authentication not configured")

        # Verify password
        password_hash = auth_method.credentials.get("password_hash")
        if not password_hash or not self._verify_password(password, password_hash):
            raise AuthenticationError("Invalid credentials")

        # Generate access token
        access_token = self._create_access_token(user)
        return user, access_token

    async def authenticate_oauth_user(
        self, provider: AuthProvider, provider_user_id: str, user_info: dict
    ) -> tuple[User, str]:
        """Authenticate or create user via OAuth."""
        # Check if auth method exists
        auth_method = await self.storage.get_user_auth_method(
            provider, provider_user_id
        )

        if auth_method:
            # Existing user - get user and update credentials
            user = await self.storage.get_user(auth_method.user_id)
            if not user or not user.is_active:
                raise UserNotFoundError("User not found or inactive")

            # Update auth method credentials
            auth_method.credentials = user_info
            await self.storage.update_user_auth_method(auth_method)
        else:
            # New user - create user and auth method
            username = user_info.get("username") or user_info.get("email", "").split("@")[0]
            email = user_info.get("email")

            # Ensure unique username
            base_username = username
            counter = 1
            while await self.storage.get_user_by_username(username):
                username = f"{base_username}_{counter}"
                counter += 1

            user_id = str(uuid.uuid4())
            user = User(
                id=user_id,
                username=username,
                email=email,
                role=UserRole.USER,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            await self.storage.create_user(user)

            # Create OAuth auth method
            auth_method = UserAuthMethod(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider=provider,
                provider_user_id=provider_user_id,
                credentials=user_info,
                created_at=datetime.now(),
            )
            await self.storage.create_user_auth_method(auth_method)

        # Generate access token
        access_token = self._create_access_token(user)
        return user, access_token

    async def get_user_by_token(self, token: str) -> User:
        """Get user from JWT token."""
        token_data = self.verify_token(token)
        user = await self.storage.get_user(token_data.user_id)
        if not user or not user.is_active:
            raise UserNotFoundError("User not found or inactive")
        return user

    async def change_password(self, user_id: str, old_password: str, new_password: str) -> None:
        """Change user password."""
        # Get user
        user = await self.storage.get_user(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        # Get local auth method
        auth_method = await self.storage.get_user_auth_method(
            AuthProvider.LOCAL, user.username
        )
        if not auth_method:
            raise AuthenticationError("Local authentication not configured")

        # Verify old password
        old_password_hash = auth_method.credentials.get("password_hash")
        if not old_password_hash or not self._verify_password(old_password, old_password_hash):
            raise AuthenticationError("Invalid current password")

        # Update password
        new_password_hash = self._hash_password(new_password)
        auth_method.credentials["password_hash"] = new_password_hash
        await self.storage.update_user_auth_method(auth_method)