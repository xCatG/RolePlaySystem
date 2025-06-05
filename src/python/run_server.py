#!/usr/bin/env python3
"""
Server runner for the Role Play System.
"""

import uvicorn
import asyncio
import os

from role_play.server.base_server import BaseServer
from role_play.server.config_loader import get_config
from role_play.common.logging_config import setup_logging, get_logger


async def create_server() -> BaseServer:
    """Create and configure the server with handlers."""
    config = get_config()

    # Validate configuration early for fail-fast behavior
    _validate_configuration(config)
    
    # Handle CORS origins from environment variable
    cors_origins = config.cors_origins
    if os.getenv("CORS_ALLOWED_ORIGINS"):
        cors_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS").split(",")]

    # Create server - dependencies will be injected via FastAPI Depends()
    server = BaseServer(
        title=config.title,
        description=config.description,
        version=config.version,
        enable_cors=config.enable_cors,
        cors_origins=cors_origins,
    )

    # Dynamically register handlers based on configuration
    _register_handlers(server, config)
    
    # Set up SPA handler AFTER all API handlers are registered
    server.setup_spa_handler()

    return server


def _register_handlers(server: BaseServer, config) -> None:
    """
    Dynamically register handlers based on configuration.
    
    Args:
        server: BaseServer instance to register handlers on
        config: Server configuration with enabled_handlers mapping
    """
    import importlib
    logger = get_logger(__name__)
    
    for handler_name, handler_path in config.enabled_handlers.items():
        try:
            # Parse module and class name
            module_path, class_name = handler_path.rsplit('.', 1)
            
            # Import module and get class
            module = importlib.import_module(module_path)
            handler_class = getattr(module, class_name)
            
            # Register handler
            server.register_handler(handler_class)
            logger.info(f"Registered handler: {handler_name} ({handler_path})")
            
        except ImportError as e:
            raise ImportError(f"Failed to import handler '{handler_name}' from '{handler_path}': {e}")
        except AttributeError as e:
            raise AttributeError(f"Handler class '{class_name}' not found in module '{module_path}': {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to register handler '{handler_name}': {e}")


def _validate_configuration(config) -> None:
    """
    Validate configuration for fail-fast behavior.
    
    Args:
        config: Server configuration to validate
        
    Raises:
        FileNotFoundError: If storage path doesn't exist (for file storage)
        NotADirectoryError: If storage path is not a directory (for file storage)
        PermissionError: If storage path is not readable/writable (for file storage)
        ValueError: If required environment variables are missing
    """
    import os
    
    # Only validate file paths for file storage
    if config.storage_type == "file":
        # Validate storage path exists
        if not os.path.exists(config.storage_path):
            raise FileNotFoundError(
                f"Storage path '{config.storage_path}' does not exist. "
                "Please create the directory before starting the server."
            )
        if not os.path.isdir(config.storage_path):
            raise NotADirectoryError(
                f"Storage path '{config.storage_path}' is not a directory."
            )
        if not os.access(config.storage_path, os.R_OK | os.W_OK):
            raise PermissionError(
                f"Storage path '{config.storage_path}' is not readable/writable."
            )
    elif config.storage_type == "gcs":
        # For GCS, just validate that required env vars are present
        if not os.getenv("GCP_PROJECT_ID"):
            raise ValueError("GCP_PROJECT_ID environment variable is required for GCS storage")
        if not os.getenv("GCS_BUCKET"):
            raise ValueError("GCS_BUCKET environment variable is required for GCS storage")
    elif config.storage_type not in ["file", "gcs", "s3"]:
        raise ValueError(f"Unsupported storage type: {config.storage_type}")
    
    # Validate JWT secret in production
    if hasattr(config, 'debug') and not config.debug:
        if config.jwt_secret_key == "development-secret-key":
            raise ValueError("JWT_SECRET_KEY must be set in production environment")


# Create app at module level for uvicorn
app = None


async def init_app():
    """Initialize the app."""
    global app
    server = await create_server()
    app = server.get_app()
    return app


def main():
    """Main entry point."""
    config = get_config()
    
    # Setup logging based on environment
    log_level = os.getenv("LOG_LEVEL", "INFO" if not config.debug else "DEBUG")
    setup_logging(log_level=log_level)
    
    logger = get_logger(__name__)
    logger.info(f"Starting {config.title} on {config.host}:{config.port}")
    logger.info(f"Debug mode: {config.debug}")
    logger.info(f"Enabled handlers: {config.enabled_handlers}")

    # Initialize app synchronously for uvicorn
    asyncio.run(init_app())

    # Use PORT environment variable if set (required by Cloud Run)
    port = int(os.getenv("PORT", config.port))
    
    uvicorn.run(
        app,
        host=config.host,
        port=port,
        reload=False,  # Disable reload for testing
    )


if __name__ == "__main__":
    main()
