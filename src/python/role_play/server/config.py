"""Configuration system for the Role Play System server."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os


class ServerConfig(BaseModel):
    """Server configuration settings."""

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host address")
    # Updated port to respect PORT environment variable for Cloud Run compatibility
    port: int = Field(
        default_factory=lambda: int(os.getenv("PORT", "8000")), 
        description="Server port (reads from PORT env var if set, defaults to 8000)"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "dev"),
        description="Deployment environment (dev, poc, beta, prod)"
    )

    # API settings
    title: str = Field(default="Role Play System", description="API title")
    description: str = Field(
        default="Role Play System API", description="API description"
    )
    version: str = Field(default="1.0.0", description="API version")

    # CORS settings
    enable_cors: bool = Field(default=True, description="Enable CORS middleware")
    cors_origins: List[str] = Field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(','),
        description="Allowed CORS origins (comma-separated string from env var or defaults)",
    )

    # Authentication settings
    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", "development-secret-key"),
        description="JWT secret key for token signing (MUST be set in production)",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expire_hours: int = Field(
        default_factory=lambda: int(os.getenv("JWT_EXPIRE_HOURS", "24")),
        description="JWT token expiration in hours"
    )

    # Storage settings
    storage_type: str = Field(
        default_factory=lambda: os.getenv("STORAGE_TYPE", "file"),
        description="Storage backend type (e.g., file, gcs)"
    )
    storage_path: str = Field(
        default_factory=lambda: os.path.expanduser(os.getenv("STORAGE_PATH", "./data")),
        description="Storage path for file backend (e.g., ./data or /tmp/data for ephemeral)",
    )
    # Example for GCS, if you were to use it later
    # gcs_bucket: Optional[str] = Field(
    #     default_factory=lambda: os.getenv("GCS_BUCKET"),
    #     description="Google Cloud Storage bucket name (if storage_type is gcs)"
    # )

    # Handler configuration
    enabled_handlers: Dict[str, str] = Field(
        default={
            "user_account": "role_play.server.user_account_handler.UserAccountHandler",
            "chat": "role_play.chat.handler.ChatHandler",
            "evaluation": "role_play.evaluation.handler.EvaluationHandler"
            },
        description="Map of handler names to their import paths"
    )

    class Config:
        # This allows the model to be created from environment variables directly
        # if you were to use Pydantic's settings management, but here we use default_factory.
        # For now, this is just for good practice.
        case_sensitive = False


class DevelopmentConfig(ServerConfig):
    """Development configuration with debug enabled."""
    debug: bool = True
    environment: str = "dev"
    # Ensure JWT secret is distinct for dev, even if a default is provided in ServerConfig
    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", "development-secret-key-not-for-production"),
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:8080").split(','),
    )


class ProductionConfig(ServerConfig):
    """Production configuration with secure defaults."""
    debug: bool = False
    environment: str = "prod"
    # For production, CORS should be explicitly set and not default to localhost
    enable_cors: bool = Field(default_factory=lambda: bool(os.getenv("ENABLE_CORS", "False").lower() in ['true', '1']))
    cors_origins: List[str] = Field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "").split(','), # Expect this to be set in prod
    )

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure JWT secret is set and not the default dev key in production
        if not self.jwt_secret_key or self.jwt_secret_key == "development-secret-key" or self.jwt_secret_key == "development-secret-key-not-for-production":
            raise ValueError("JWT_SECRET_KEY must be securely set in the production environment.")
        if not self.cors_origins or self.cors_origins == ['']:
             # Allow no origins if not set, or be more strict
            print("Warning: Production CORS origins not explicitly set. Defaulting to no origins allowed unless ENABLE_CORS is false.")


class PocConfig(ServerConfig):
    """PoC specific configuration."""
    debug: bool = False # Typically false for deployed environments
    environment: str = "poc"
    cors_origins: List[str] = Field(
        # Example: specific PoC domain
        default_factory=lambda: os.getenv("CORS_ORIGINS", "https://poc.rps.cattail-sw.com").split(','),
    )
    storage_path: str = Field(
        default_factory=lambda: os.getenv("STORAGE_PATH", "/tmp/data"), # Ephemeral for PoC
        description="Storage path for PoC (ephemeral)"
    )
    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY"), # Must be set via env var or secret manager
        description="JWT secret key for PoC (MUST be set)"
    )
    def __init__(self, **data):
        super().__init__(**data)
        if not self.jwt_secret_key:
            raise ValueError("JWT_SECRET_KEY must be set for the PoC environment.")


# The get_config function in config_loader.py will use these classes.
# We can simplify the old get_config function here or remove it if config_loader.py is the sole entry point.
# For now, let's assume config_loader.py's get_config is primary.
# This function is kept for context but `config_loader.get_config()` should be preferred.
def get_config_simple(environment: Optional[str] = None) -> ServerConfig:
    """
    Get configuration based on environment.
    NOTE: Prefer using `role_play.server.config_loader.get_config()`

    Args:
        environment: Environment name (dev, poc, prod) or None for auto-detection

    Returns:
        ServerConfig: Configuration instance
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "dev")

    if environment == "prod":
        return ProductionConfig()
    elif environment == "poc":
        return PocConfig()
    # Default to DevelopmentConfig for "dev" or any other unspecified environment
    return DevelopmentConfig()
