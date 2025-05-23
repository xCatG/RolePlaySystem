#!/usr/bin/env python3
"""
Server runner for the Role Play System.
"""

import uvicorn
import asyncio
import os
from role_play.server.base_server import BaseServer
from role_play.server.user_account_handler import UserAccountHandler
from role_play.server.config import get_config
from role_play.server.dependencies import set_storage_backend, set_auth_manager
from role_play.common.storage import FileStorage
from role_play.common.auth import AuthManager


async def create_server() -> BaseServer:
    """Create and configure the server with handlers."""
    config = get_config()
    
    # Initialize storage backend
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
            
        storage = FileStorage(config.storage_path)
    else:
        raise ValueError(f"Unsupported storage type: {config.storage_type}")
    
    set_storage_backend(storage)
    
    # Initialize auth manager
    auth_manager = AuthManager(storage, jwt_secret_key=config.jwt_secret_key)
    set_auth_manager(auth_manager)
    
    # Create server
    server = BaseServer(
        title=config.title,
        description=config.description,
        version=config.version,
        enable_cors=config.enable_cors,
    )
    
    # Register handlers
    if "user_account" in config.enabled_handlers:
        server.register_handler(UserAccountHandler)
    
    return server


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
    
    print(f"Starting {config.title} on {config.host}:{config.port}")
    print(f"Debug mode: {config.debug}")
    print(f"Enabled handlers: {config.enabled_handlers}")
    
    # Initialize app synchronously for uvicorn
    asyncio.run(init_app())
    
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=False,  # Disable reload for testing
    )


if __name__ == "__main__":
    main()
