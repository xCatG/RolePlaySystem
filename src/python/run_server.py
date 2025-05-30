#!/usr/bin/env python3
"""
Server runner for the Role Play System.
"""

import uvicorn
import asyncio

from role_play.server.base_server import BaseServer
from role_play.server.config_loader import get_config


async def create_server() -> BaseServer:
    """Create and configure the server with handlers."""
    config = get_config()

    # Validate configuration early for fail-fast behavior
    _validate_configuration(config)

    # Create server - dependencies will be injected via FastAPI Depends()
    server = BaseServer(
        title=config.title,
        description=config.description,
        version=config.version,
        enable_cors=config.enable_cors,
    )

    # Dynamically register handlers based on configuration
    _register_handlers(server, config)

    return server


def _register_handlers(server: BaseServer, config) -> None:
    """
    Dynamically register handlers based on configuration.
    
    Args:
        server: BaseServer instance to register handlers on
        config: Server configuration with enabled_handlers mapping
    """
    import importlib
    
    for handler_name, handler_path in config.enabled_handlers.items():
        try:
            # Parse module and class name
            module_path, class_name = handler_path.rsplit('.', 1)
            
            # Import module and get class
            module = importlib.import_module(module_path)
            handler_class = getattr(module, class_name)
            
            # Register handler
            server.register_handler(handler_class)
            print(f"Registered handler: {handler_name} ({handler_path})")
            
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
        FileNotFoundError: If storage path doesn't exist
        NotADirectoryError: If storage path is not a directory
        PermissionError: If storage path is not readable/writable
        ValueError: If storage type is unsupported
    """
    import os
    
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
    elif config.storage_type != "file":
        raise ValueError(f"Unsupported storage type: {config.storage_type}")
    
    # Validate JWT secret in production
    if hasattr(config, 'debug') and not config.debug:
        if config.jwt_secret_key == "development-secret-key":
            raise ValueError("JWT_SECRET_KEY must be set in production environment")


def main():
    """Main entry point."""
    config = get_config()

    print(f"Starting {config.title} on {config.host}:{config.port}")
    print(f"Debug mode: {config.debug}")
    print(f"Enabled handlers: {config.enabled_handlers}")

    # Initialize app synchronously
    server = asyncio.run(create_server())
    app = server.get_app()

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
