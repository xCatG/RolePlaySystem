"""Configuration system for the Role Play System server."""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
import os

from ..common.storage import StorageConfigUnion, FileStorageConfig, GCSStorageConfig, S3StorageConfig, LockConfig


class ServerConfig(BaseModel):
    """Server configuration settings."""

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host address")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Enable debug mode")

    # API settings
    title: str = Field(default="Role Play System", description="API title")
    description: str = Field(
        default="Role Play System API", description="API description"
    )
    version: str = Field(default="1.0.0", description="API version")

    # CORS settings
    enable_cors: bool = Field(default=True, description="Enable CORS middleware")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )

    # Authentication settings
    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", "development-secret-key"),
        description="JWT secret key for token signing",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expire_hours: int = Field(
        default=24, description="JWT token expiration in hours"
    )

    # Storage settings (legacy - for backward compatibility)
    storage_type: str = Field(
        default="file", description="Storage backend type (file, s3) - DEPRECATED: Use storage.type"
    )
    storage_path: str = Field(
        default_factory=lambda: os.path.expanduser(os.getenv("STORAGE_PATH", "./data")),
        description="Storage path for file backend (must exist) - DEPRECATED: Use storage.base_dir",
    )
    
    # New storage configuration
    storage: Optional[StorageConfigUnion] = Field(
        default=None, description="Storage configuration (new format)"
    )

    # Handler configuration
    enabled_handlers: Dict[str, str] = Field(
        default={"user_account": "role_play.server.user_account_handler.UserAccountHandler"},
        description="Map of handler names to their import paths"
    )
    
    @validator('storage', pre=True)
    def parse_storage_config(cls, v):
        """Parse storage configuration from dict format."""
        if v is None:
            return None
        
        if isinstance(v, dict):
            storage_type = v.get('type')
            if storage_type == 'file':
                return FileStorageConfig(**v)
            elif storage_type == 'gcs':
                return GCSStorageConfig(**v)
            elif storage_type == 's3':
                return S3StorageConfig(**v)
            else:
                raise ValueError(f"Unknown storage type: {storage_type}")
        
        return v

    # Language configuration
    supported_languages: List[str] = Field(
        default=["en", "zh-TW", "ja"],
        description="List of supported language codes for scenarios and characters"
    )


class DevelopmentConfig(ServerConfig):
    """Development configuration with debug enabled."""

    debug: bool = True
    jwt_secret_key: str = "development-secret-key-not-for-production"


class ProductionConfig(ServerConfig):
    """Production configuration with secure defaults."""

    debug: bool = False
    enable_cors: bool = False  # Should be configured properly for production
    cors_origins: List[str] = []

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure JWT secret is set in production
        if self.jwt_secret_key == "development-secret-key":
            raise ValueError("JWT_SECRET_KEY must be set in production environment")


def get_config(environment: Optional[str] = None) -> ServerConfig:
    """
    Get configuration based on environment.

    Args:
        environment: Environment name (development, production) or None for auto-detection

    Returns:
        ServerConfig: Configuration instance
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")

    if environment == "production":
        return ProductionConfig()
    else:
        return DevelopmentConfig()
