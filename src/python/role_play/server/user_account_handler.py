"""User account handler for registration, login, and profile management."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Annotated

from .auth_decorators import auth_required
from .base_handler import BaseHandler
from .dependencies import get_auth_manager, get_current_user
from ..common.auth import AuthManager
from ..common.models import User, UserRole, AuthProvider
from ..common.exceptions import AuthenticationError, StorageError


class RegisterRequest(BaseModel):
    """Request model for user registration."""
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Response model for authentication (login/register)."""
    access_token: str
    token_type: str = "bearer"
    user: User


class UserResponse(BaseModel):
    """Response model for user profile."""
    user: User


class UserAccountHandler(BaseHandler):
    """
    Handler for user account operations: registration, login, profile access.
    
    Stateless handler instantiated per HTTP request.
    """
    
    def __init__(self):
        super().__init__()
    
    @property
    def router(self) -> APIRouter:
        """Return the FastAPI router for user account endpoints."""
        if self._router is None:
            self._router = APIRouter()
            
            @self._router.post("/register", response_model=AuthResponse)
            async def register(
                request: RegisterRequest,
                auth_manager: Annotated[AuthManager, Depends(get_auth_manager)]
            ):
                """
                Register a new user account.
                
                Args:
                    request: Registration request with username, email, password
                    auth_manager: AuthManager dependency
                    
                Returns:
                    AuthResponse: JWT token and user data
                    
                Raises:
                    HTTPException: If registration fails
                """
                try:
                    user, token = await auth_manager.register_user(
                        username=request.username,
                        email=request.email,
                        password=request.password
                    )
                    
                    return AuthResponse(
                        access_token=token,
                        user=user
                    )
                    
                except StorageError as e:
                    if "already exists" in str(e):
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="User with this email already exists"
                        )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Registration failed due to storage error"
                    )
                except AuthenticationError as e:
                    # This covers weak passwords or other auth validation issues
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=str(e)
                    )
                except ValueError as e:
                    # This covers validation errors like invalid email format
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=str(e)
                    )
            
            @self._router.post("/login", response_model=AuthResponse)
            async def login(
                request: LoginRequest,
                auth_manager: Annotated[AuthManager, Depends(get_auth_manager)]
            ):
                """
                Authenticate user and return JWT token.
                
                Args:
                    request: Login request with email and password
                    auth_manager: AuthManager dependency
                    
                Returns:
                    AuthResponse: JWT token and user data
                    
                Raises:
                    HTTPException: If authentication fails
                """
                try:
                    user, token = await auth_manager.authenticate_user(
                        email=request.email,
                        password=request.password
                    )
                    
                    return AuthResponse(
                        access_token=token,
                        user=user
                    )
                    
                except AuthenticationError:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password"
                    )
                except StorageError as e:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Login failed due to storage error"
                    )
                except ValueError as e:
                    # This covers validation errors like invalid email format
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=str(e)
                    )
            
            @self._router.get("/me", response_model=UserResponse)
            async def get_current_user_profile(
                current_user: Annotated[User, Depends(get_current_user)]
            ):
                """
                Get current user's profile information.
                
                Args:
                    current_user: Current authenticated user from JWT token
                    
                Returns:
                    UserResponse: Current user's profile data
                """
                return UserResponse(user=current_user)
        
        return self._router
    
    @property
    def prefix(self) -> str:
        """Return the URL prefix for user account endpoints."""
        return "/auth"