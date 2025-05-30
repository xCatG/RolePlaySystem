#!/usr/bin/env python3
"""
Server runner for the Role Play System.
"""

import uvicorn
import asyncio
import os
import logging
from pathlib import Path

from role_play.server.base_server import BaseServer
# Updated to use the centralized config loader
from role_play.server.config_loader import get_config as get_server_config, ConfigLoader


# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def create_server() -> BaseServer:
    """Create and configure the server with handlers."""
    # Get config using the loader, which respects ENVIRONMENT env var
    config = get_server_config() 

    # Validate configuration early for fail-fast behavior
    # This validation is now more robust within the ConfigLoader and ServerConfig models
    logger.info(f"Server configuration loaded for environment: {config.environment}")
    _validate_runtime_dependencies(config) # Keep specific runtime checks

    # Create server - dependencies will be injected via FastAPI Depends()
    server = BaseServer(
        # BaseServer now reads most of these from the loaded config internally
        # title=config.title,
        # description=config.description,
        # version=config.version,
        # enable_cors=config.enable_cors,
        # cors_origins=config.cors_origins
    )

    # Dynamically register handlers based on configuration
    _register_handlers(server, config)
    
    # Setup static files AFTER handlers to ensure catch-all route doesn't override APIs
    server.setup_static_files_after_handlers()

    return server


def _register_handlers(server: BaseServer, config) -> None:
    """
    Dynamically register handlers based on configuration.
    """
    import importlib
    
    if not config.enabled_handlers:
        logger.warning("No handlers enabled in the configuration.")
        return

    for handler_name, handler_path in config.enabled_handlers.items():
        try:
            module_path, class_name = handler_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            handler_class = getattr(module, class_name)
            server.register_handler(handler_class)
            logger.info(f"Registered handler: {handler_name} ({handler_path})")
        except ImportError as e:
            logger.error(f"Failed to import handler '{handler_name}' from '{handler_path}': {e}", exc_info=True)
            raise # Re-raise to stop server startup on critical error
        except AttributeError as e:
            logger.error(f"Handler class '{class_name}' not found in module '{module_path}': {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to register handler '{handler_name}': {e}", exc_info=True)
            raise


def _validate_runtime_dependencies(config) -> None:
    """
    Validate runtime dependencies like storage path accessibility.
    """
    if config.storage_type == "file":
        storage_path = Path(config.storage_path)
        if not storage_path.exists():
            logger.warning(
                f"Storage path '{storage_path.resolve()}' does not exist. "
                "Application might attempt to create it or fail if permissions are insufficient."
            )
            # For FileStorage, it creates the directory, so this is more of a warning.
            # However, for Cloud Run, /tmp/ is usually writable.
            # If STORAGE_PATH is set to something like /app_specific_data/data,
            # the Dockerfile should create this path.
        elif not storage_path.is_dir():
            logger.error(f"Storage path '{storage_path.resolve()}' is not a directory.")
            raise NotADirectoryError(f"Storage path '{storage_path.resolve()}' is not a directory.")
        elif not os.access(storage_path, os.R_OK | os.W_OK):
            # This check might be problematic in restricted environments like Cloud Run if path is outside /tmp
            # For /tmp/data, it should be fine.
            logger.warning(
                f"Storage path '{storage_path.resolve()}' might not be readable/writable. "
                f"Current access: R={os.access(storage_path, os.R_OK)}, W={os.access(storage_path, os.W_OK)}"
            )
            # raise PermissionError(f"Storage path '{storage_path.resolve()}' is not readable/writable.")
    
    # JWT Secret validation is now part of Pydantic model validation for ProductionConfig/PocConfig
    # if config.environment in ["prod", "poc"] and (not config.jwt_secret_key or config.jwt_secret_key == "development-secret-key" or config.jwt_secret_key == "development-secret-key-not-for-production"):
    #     logger.error(f"FATAL: JWT_SECRET_KEY must be securely set in {config.environment} environment. Current value is not secure.")
    #     raise ValueError(f"JWT_SECRET_KEY must be securely set in {config.environment} environment.")


def main():
    """Main entry point."""
    # Load configuration using the centralized loader
    # This will also load .env files and perform substitutions
    config = get_server_config()

    logger.info(f"Starting {config.title} v{config.version} in {config.environment} mode.")
    logger.info(f"Server will listen on {config.host}:{config.port}")
    logger.info(f"Debug mode: {config.debug}")
    logger.info(f"Enabled handlers: {config.enabled_handlers}")
    logger.info(f"CORS enabled: {config.enable_cors}, Origins: {config.cors_origins}")
    logger.info(f"Storage: type='{config.storage_type}', path='{config.storage_path}'")

    # Initialize app synchronously
    # This ensures that config is fully loaded and validated before uvicorn starts
    try:
        server_instance = asyncio.run(create_server())
        app = server_instance.get_app()
    except Exception as e:
        logger.error(f"Failed to create server instance: {e}", exc_info=True)
        # Exit if server creation fails, as uvicorn might start with a broken app
        return 

    uvicorn.run(
        app, # Use the app instance from the created server
        host=config.host,
        port=config.port, # This port is now correctly read from ENV or defaults
        reload=config.debug, # Reload only in debug mode (typically dev)
        log_level="info" if not config.debug else "debug",
    )


if __name__ == "__main__":
    main()
