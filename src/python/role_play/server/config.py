"""Configuration system for the Role Play System server."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os


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

    # Storage settings
    storage_type: str = Field(
        default="file", description="Storage backend type (file, gcs, s3)"
    )
    storage_path: str = Field(
        default_factory=lambda: os.path.expanduser(os.getenv("STORAGE_PATH", "./data")),
        description="Storage path for file backend (must exist)",
    )
    
    # Google Cloud Storage settings
    gcs_bucket_name: Optional[str] = Field(
        default_factory=lambda: os.getenv("GCS_BUCKET_NAME"),
        description="GCS bucket name for gcs storage type"
    )
    gcs_project_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("GCS_PROJECT_ID"),
        description="GCS project ID (optional if using default credentials)"
    )
    gcs_credentials_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("GCS_CREDENTIALS_PATH"),
        description="Path to GCS service account JSON file (optional)"
    )
    gcs_prefix: str = Field(
        default_factory=lambda: os.getenv("GCS_PREFIX", ""),
        description="GCS object key prefix for namespacing"
    )
    
    # AWS S3 settings
    s3_bucket_name: Optional[str] = Field(
        default_factory=lambda: os.getenv("S3_BUCKET_NAME"),
        description="S3 bucket name for s3 storage type"
    )
    s3_region_name: str = Field(
        default_factory=lambda: os.getenv("S3_REGION_NAME", "us-east-1"),
        description="S3 region name"
    )
    s3_access_key_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("S3_ACCESS_KEY_ID"),
        description="S3 access key ID (optional, uses IAM roles if not provided)"
    )
    s3_secret_access_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("S3_SECRET_ACCESS_KEY"),
        description="S3 secret access key (optional, uses IAM roles if not provided)"
    )
    s3_prefix: str = Field(
        default_factory=lambda: os.getenv("S3_PREFIX", ""),
        description="S3 object key prefix for namespacing"
    )
    
    # Redis settings for distributed locking (optional)
    redis_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("REDIS_URL"),
        description="Redis URL for distributed locking (optional, for cloud storage)"
    )

    # Handler configuration
    enabled_handlers: Dict[str, str] = Field(
        default={"user_account": "role_play.server.user_account_handler.UserAccountHandler"},
        description="Map of handler names to their import paths"
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
