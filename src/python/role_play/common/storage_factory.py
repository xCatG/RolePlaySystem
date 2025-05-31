"""Storage backend factory with configuration-based selection."""

import os
from typing import Union

from .models import Environment
from .storage import (
    StorageBackend, FileStorage, StorageConfigUnion,
    FileStorageConfig, GCSStorageConfig, S3StorageConfig
)
from .exceptions import StorageError


def create_storage_backend(
    config: StorageConfigUnion,
    environment: Union[Environment, str] = Environment.DEV
) -> StorageBackend:
    """
    Create a storage backend instance based on configuration.
    
    Enforces environment-specific restrictions:
    - DEV: Allows all storage types (file, gcs, s3) for testing flexibility
    - BETA/PROD: Only allows cloud storage (gcs, s3) for production reliability
    
    Args:
        config: Storage configuration object
        environment: Deployment environment (dev/beta/prod)
        
    Returns:
        StorageBackend: Configured storage backend instance
        
    Raises:
        StorageError: If configuration is invalid or environment restrictions are violated
    """
    # Normalize environment
    if isinstance(environment, str):
        try:
            environment = Environment(environment.lower())
        except ValueError:
            raise StorageError(f"Invalid environment: {environment}. Must be one of: {list(Environment)}")
    
    # Enforce environment restrictions
    if environment in (Environment.BETA, Environment.PROD):
        if config.type == "file":
            raise StorageError(
                f"File-based storage not allowed in {environment.value} environment. "
                "Use 'gcs' or 's3' for production deployments."
            )
    
    # Create storage backend based on type
    if config.type == "file":
        if not isinstance(config, FileStorageConfig):
            raise StorageError("Invalid configuration type for file storage")
        return FileStorage(storage_dir=config.base_dir)
    
    elif config.type == "gcs":
        if not isinstance(config, GCSStorageConfig):
            raise StorageError("Invalid configuration type for GCS storage")
        
        # Import GCS backend only when needed to avoid dependency issues
        try:
            from .GCSBackend import GCSStorageBackend
            return GCSStorageBackend(config)
        except ImportError as e:
            raise StorageError(f"GCS dependencies not available: {e}")
    
    elif config.type == "s3":
        if not isinstance(config, S3StorageConfig):
            raise StorageError("Invalid configuration type for S3 storage")
        
        # Import S3 backend only when needed to avoid dependency issues
        try:
            from .S3Backend import S3StorageBackend
            return S3StorageBackend(config)
        except ImportError as e:
            raise StorageError(f"S3 dependencies not available: {e}")
    
    else:
        raise StorageError(f"Unsupported storage type: {config.type}")


def create_storage_from_env(environment: Union[Environment, str] = None) -> StorageBackend:
    """
    Create storage backend from environment variables.
    
    Expected environment variables:
    - STORAGE_TYPE: "file", "gcs", or "s3"
    - STORAGE_BASE_DIR: For file storage
    - STORAGE_BUCKET: For GCS/S3 storage
    - STORAGE_PREFIX: Optional prefix for GCS/S3
    - GCP_PROJECT_ID: For GCS
    - GCP_CREDENTIALS_FILE: For GCS service account
    - AWS_REGION: For S3
    - AWS_ACCESS_KEY_ID: For S3 (optional if using IAM roles)
    - AWS_SECRET_ACCESS_KEY: For S3 (optional if using IAM roles)
    - S3_ENDPOINT_URL: For S3-compatible services
    - LOCK_STRATEGY: "file", "object", or "redis"
    - LOCK_LEASE_DURATION: Lock lease duration in seconds
    - REDIS_HOST: For Redis locking
    - REDIS_PORT: For Redis locking
    - REDIS_PASSWORD: For Redis locking
    
    Args:
        environment: Deployment environment (auto-detected from ENV if not provided)
        
    Returns:
        StorageBackend: Configured storage backend instance
        
    Raises:
        StorageError: If required environment variables are missing or invalid
    """
    # Auto-detect environment if not provided
    if environment is None:
        env_str = os.getenv("ENV", "dev").lower()
        try:
            environment = Environment(env_str)
        except ValueError:
            raise StorageError(f"Invalid ENV environment variable: {env_str}")
    
    # Get storage type
    storage_type = os.getenv("STORAGE_TYPE")
    if not storage_type:
        raise StorageError("STORAGE_TYPE environment variable is required")
    
    storage_type = storage_type.lower()
    
    # Create lock configuration
    from .storage import LockConfig
    lock_config = LockConfig(
        strategy=os.getenv("LOCK_STRATEGY", "file"),
        lease_duration_seconds=int(os.getenv("LOCK_LEASE_DURATION", "60")),
        retry_attempts=int(os.getenv("LOCK_RETRY_ATTEMPTS", "3")),
        retry_delay_seconds=float(os.getenv("LOCK_RETRY_DELAY", "1.0")),
        redis_host=os.getenv("REDIS_HOST"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_password=os.getenv("REDIS_PASSWORD"),
        redis_db=int(os.getenv("REDIS_DB", "0"))
    )
    
    # Create storage configuration based on type
    if storage_type == "file":
        base_dir = os.getenv("STORAGE_BASE_DIR")
        if not base_dir:
            raise StorageError("STORAGE_BASE_DIR environment variable is required for file storage")
        
        config = FileStorageConfig(
            base_dir=base_dir,
            lock=lock_config
        )
    
    elif storage_type == "gcs":
        bucket = os.getenv("STORAGE_BUCKET")
        if not bucket:
            raise StorageError("STORAGE_BUCKET environment variable is required for GCS storage")
        
        config = GCSStorageConfig(
            bucket=bucket,
            prefix=os.getenv("STORAGE_PREFIX", ""),
            project_id=os.getenv("GCP_PROJECT_ID"),
            credentials_file=os.getenv("GCP_CREDENTIALS_FILE"),
            lock=lock_config
        )
    
    elif storage_type == "s3":
        bucket = os.getenv("STORAGE_BUCKET")
        if not bucket:
            raise StorageError("STORAGE_BUCKET environment variable is required for S3 storage")
        
        config = S3StorageConfig(
            bucket=bucket,
            prefix=os.getenv("STORAGE_PREFIX", ""),
            region_name=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            lock=lock_config
        )
    
    else:
        raise StorageError(f"Unsupported STORAGE_TYPE: {storage_type}")
    
    return create_storage_backend(config, environment)


def validate_storage_config(config: StorageConfigUnion) -> None:
    """
    Validate storage configuration.
    
    Args:
        config: Storage configuration to validate
        
    Raises:
        StorageError: If configuration is invalid
    """
    # Validate lock strategy compatibility
    if config.type == "file" and config.lock.strategy not in ("file", "redis"):
        raise StorageError(f"Lock strategy '{config.lock.strategy}' not supported for file storage")
    
    if config.type in ("gcs", "s3") and config.lock.strategy == "file":
        raise StorageError(f"File-based locking not supported for {config.type} storage")
    
    # Validate Redis configuration if using Redis locking
    if config.lock.strategy == "redis":
        if not config.lock.redis_host:
            raise StorageError("redis_host is required when using Redis locking strategy")
    
    # Type-specific validations
    if isinstance(config, FileStorageConfig):
        if not config.base_dir:
            raise StorageError("base_dir is required for file storage")
    
    elif isinstance(config, GCSStorageConfig):
        if not config.bucket:
            raise StorageError("bucket is required for GCS storage")
    
    elif isinstance(config, S3StorageConfig):
        if not config.bucket:
            raise StorageError("bucket is required for S3 storage")


# Example YAML configurations for documentation
EXAMPLE_CONFIGS = {
    "dev_file": """
storage:
  type: file
  base_dir: ./data
  lock:
    strategy: file
    lease_duration_seconds: 60
    retry_attempts: 3
    retry_delay_seconds: 1.0
""",
    
    "dev_gcs": """
storage:
  type: gcs
  bucket: my-dev-bucket
  prefix: roleplay-dev/
  project_id: my-gcp-project
  credentials_file: /path/to/service-account.json
  lock:
    strategy: object
    lease_duration_seconds: 60
    retry_attempts: 3
    retry_delay_seconds: 1.0
""",
    
    "prod_gcs_redis": """
storage:
  type: gcs
  bucket: my-prod-bucket
  prefix: roleplay-prod/
  project_id: my-gcp-project
  credentials_file: /path/to/service-account.json
  lock:
    strategy: redis
    lease_duration_seconds: 30
    retry_attempts: 5
    retry_delay_seconds: 0.5
    redis_host: redis.example.com
    redis_port: 6379
    redis_password: ${REDIS_PASSWORD}
    redis_db: 0
""",
    
    "prod_s3": """
storage:
  type: s3
  bucket: my-prod-bucket
  prefix: roleplay-prod/
  region_name: us-west-2
  lock:
    strategy: object  # Consider 'redis' for high-contention scenarios
    lease_duration_seconds: 60
    retry_attempts: 3
    retry_delay_seconds: 1.0
"""
}