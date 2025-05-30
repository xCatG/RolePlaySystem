"""Base server class for the Role Play System."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os
from typing import Type, Optional
from pathlib import Path
from contextlib import asynccontextmanager
from .base_handler import BaseHandler
import logging
from datetime import datetime, timezone

# Assuming your config loader is the source of truth for config
from .config_loader import get_config as get_server_config_from_loader


logger = logging.getLogger(__name__)


class BaseServer:
    """
    Base server class that manages FastAPI app and handler registration.
    
    Provides automatic handler registration and common middleware setup.
    """
    
    def __init__(
        self,
        # These defaults can be overridden by the loaded configuration
        title: str = "Role Play System",
        description: str = "Role Play System API",
        version: str = "1.0.0",
        enable_cors: bool = True,
        cors_origins: Optional[list[str]] = None,
    ):
        """
        Initialize the base server.
        
        Args:
            title: API title for OpenAPI docs
            description: API description for OpenAPI docs
            version: API version
            enable_cors: Whether to enable CORS middleware
            cors_origins: List of allowed CORS origins
        """
        # Load configuration using the centralized loader
        # This config will be used for settings not directly passed as arguments
        self.config = get_server_config_from_loader()
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            logger.info(f"Server starting up in {self.config.environment} mode...")
            logger.info(f"Listening on {self.config.host}:{self.config.port}")
            logger.info(f"Storage type: {self.config.storage_type}, Path: {self.config.storage_path}")
            yield
            # Shutdown
            logger.info("Server shutting down...")
        
        self.app = FastAPI(
            title=self.config.title, # Use loaded config
            description=self.config.description, # Use loaded config
            version=self.config.version, # Use loaded config
            lifespan=lifespan
        )
        
        # Use CORS settings from loaded config
        if self.config.enable_cors:
            self._setup_cors(self.config.cors_origins)
        
        # Don't setup static files here - we'll do it after handlers are registered
        self._static_frontend_dir = "static_frontend"
    
    def _setup_cors(self, allowed_origins: list[str]):
        """Setup CORS middleware for frontend development."""
        if not allowed_origins:
            logger.warning("CORS enabled but no origins specified. This might block frontend access.")
            # Default to a restrictive but common pattern if needed, or let it be empty
            # For PoC, if poc.yaml sets it, this will be used.
            # allowed_origins = ["https://poc.rps.cattail-sw.com"] 
        
        logger.info(f"Setting up CORS with origins: {allowed_origins}")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins, 
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_static_files(self):
        """Setup serving of static frontend files."""
        static_frontend_dir = self._static_frontend_dir
        
        if not os.path.exists(static_frontend_dir) or not os.path.isdir(static_frontend_dir):
            logger.warning(
                f"Static frontend directory '{static_frontend_dir}' not found. "
                "Frontend will not be served. This is expected if running backend only for development."
            )
            return

        # Serve assets directory
        if os.path.exists(os.path.join(static_frontend_dir, "assets")):
            self.app.mount(
                "/assets", 
                StaticFiles(directory=os.path.join(static_frontend_dir, "assets")), 
                name="vue-assets"
            )
        
        # Serve static files from root
        for item in os.listdir(static_frontend_dir):
            item_path = os.path.join(static_frontend_dir, item)
            if os.path.isfile(item_path) and item != "index.html":
                # For each static file, create a specific route
                @self.app.get(f"/{item}", include_in_schema=False)
                async def serve_static_file(filename: str = item):
                    return FileResponse(os.path.join(static_frontend_dir, filename))

        # Enhanced Health check endpoint - add before catch-all route
        @self.app.get("/health", tags=["Health"])
        async def health_check():
            """
            Enhanced health check endpoint that reports system status,
            version, environment, and timestamp.
            """
            # Access config through self.config (loaded in __init__)
            current_config = self.config 
            
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "environment": current_config.environment,
                "version": current_config.version,
                "checks": {}
            }
            
            # Check scenarios loading (Example, adjust if ContentLoader is not always available)
            try:
                from ..server.dependencies import get_content_loader # Local import
                loader = get_content_loader()
                scenarios = loader.get_scenarios() # This might raise if file not found
                health_status["checks"]["scenarios"] = {
                    "status": "ok",
                    "count": len(scenarios),
                    "data_file": str(loader.data_file.resolve()) # Use resolve for absolute path
                }
            except Exception as e:
                logger.warning(f"Health check: Scenarios loading issue: {str(e)}")
                health_status["checks"]["scenarios"] = {
                    "status": "error",
                    "error": str(e),
                    "data_file_expected_at": str(Path("static_data/scenarios.json").resolve())
                }
                # Do not mark overall status as degraded for PoC if scenarios are optional
                # health_status["status"] = "degraded" 
            
            # Check storage path accessibility (relevant for FileStorage)
            if current_config.storage_type == "file":
                storage_path_str = current_config.storage_path
                storage_path = Path(storage_path_str)
                if storage_path.exists() and storage_path.is_dir() and os.access(storage_path, os.R_OK | os.W_OK):
                    health_status["checks"]["storage"] = {
                        "status": "ok",
                        "type": "file",
                        "path": str(storage_path.resolve())
                    }
                else:
                    logger.warning(f"Health check: Storage path issue: {storage_path_str} (Exists: {storage_path.exists()}, IsDir: {storage_path.is_dir()}, Access: {os.access(storage_path, os.R_OK | os.W_OK)})")
                    health_status["checks"]["storage"] = {
                        "status": "error",
                        "type": "file",
                        "path": str(storage_path.resolve()),
                        "error": "Storage path not accessible or not a directory"
                    }
                    # health_status["status"] = "degraded" # Potentially critical
            elif current_config.storage_type == "gcs": # Example for future
                 health_status["checks"]["storage"] = {
                    "status": "info", # Cannot check GCS bucket existence easily here
                    "type": "gcs",
                    # "bucket": current_config.gcs_bucket
                }

            # Determine overall status based on checks
            if any(check.get("status") == "error" for check in health_status["checks"].values()):
                 health_status["status"] = "degraded"

            return JSONResponse(content=health_status)
        
        # Catch-all route for Vue app (client-side routing)
        @self.app.get("/{full_path:path}", include_in_schema=False)
        async def serve_vue_app(full_path: str):
            index_html_path = os.path.join(static_frontend_dir, "index.html")
            if os.path.exists(index_html_path):
                return FileResponse(index_html_path)
            else:
                logger.error(f"index.html not found at {index_html_path} for path: {full_path}")
                from fastapi.responses import HTMLResponse
                return HTMLResponse(content=f"Frontend not found at index.html. Requested path: {full_path}", status_code=404)
    
    def register_handler(self, handler_class: Type[BaseHandler], **handler_kwargs):
        """
        Register a handler with the server.
        
        Args:
            handler_class: Handler class to register
            **handler_kwargs: Keyword arguments to pass to handler constructor
        """
        # Create a temporary handler instance just to get router configuration
        # The actual handler instances will be created per-request by FastAPI
        handler = handler_class(**handler_kwargs)
        
        # Include the handler's router
        self.app.include_router(
            handler.router,
            prefix=handler.prefix,
            tags=handler.tags,
        )
        
        logger.info(f"Registered {handler_class.__name__} at {handler.prefix}")
    
    def setup_static_files_after_handlers(self):
        """Setup static file serving after all handlers are registered.
        This must be called AFTER all handlers are registered to ensure
        the catch-all route doesn't override API routes."""
        self._setup_static_files()
    
    def get_app(self) -> FastAPI:
        """Return the FastAPI application instance."""
        return self.app