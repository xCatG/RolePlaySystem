"""Base server class for the Role Play System."""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Type, Optional, List, Set
from contextlib import asynccontextmanager
from .base_handler import BaseHandler
import os
import logging

logger = logging.getLogger(__name__)


class BaseServer:
    """
    Base server class that manages FastAPI app and handler registration.
    
    Provides automatic handler registration, common middleware setup,
    and serves the Vue.js frontend as static files.
    """
    
    def __init__(
        self,
        title: str = "Role Play System",
        description: str = "Role Play System API",
        version: str = "1.0.0",
        enable_cors: bool = True,
        cors_origins: Optional[List[str]] = None,
        api_route_prefix: str = "/api"
    ):
        """
        Initialize the base server.
        
        Args:
            title: API title for OpenAPI docs
            description: API description for OpenAPI docs
            version: API version
            enable_cors: Whether to enable CORS middleware
            cors_origins: List of allowed CORS origins
            api_route_prefix: Prefix for all API routes (default: /api)
        """
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            logger.info("Server starting up...")
            yield
            # Shutdown
            logger.info("Server shutting down...")
            # Note: With stateless handlers, there's no per-handler cleanup needed.
            # Singleton services are cleaned up automatically by Python's garbage collector.
        
        self.app = FastAPI(
            title=title,
            description=description,
            version=version,
            lifespan=lifespan
        )
        
        self.api_route_prefix = api_route_prefix
        self._registered_api_paths: Set[str] = set()  # Track registered API paths
        
        if enable_cors:
            # Default origins if not provided
            if cors_origins is None:
                cors_origins = ["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"]
            self._setup_cors(cors_origins)
        
        # Add health check endpoint
        @self.app.get("/health", tags=["Health"], include_in_schema=False)
        async def health_check():
            """Health check endpoint for monitoring and Cloud Run."""
            return {
                "status": "healthy",
                "environment": os.getenv("ENV", "unknown"),
                "version": os.getenv("GIT_VERSION", "unknown"),
                "service": os.getenv("SERVICE_NAME", "rps")
            }
    
    def _setup_cors(self, origins: List[str]):
        """Setup CORS middleware for frontend development."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
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
        
        # Include the handler's router with API prefix
        router_prefix_with_api = f"{self.api_route_prefix}{handler.prefix}"
        self.app.include_router(
            handler.router,
            prefix=router_prefix_with_api,
            tags=handler.tags,
        )
        
        # Track this API path prefix
        self._registered_api_paths.add(router_prefix_with_api)
        
        logger.info(f"Registered {handler_class.__name__} at {router_prefix_with_api}")
    
    def setup_spa_handler(self):
        """
        Set up the SPA (Single Page Application) handler.
        This should be called AFTER all API handlers are registered.
        """
        static_files_dir = "/app/static_frontend"  # Matches Dockerfile COPY destination
        
        # Mount assets directory if it exists
        assets_path = os.path.join(static_files_dir, "assets")
        if os.path.exists(assets_path):
            self.app.mount("/assets", StaticFiles(directory=assets_path), name="static-assets")
        
        # Catch-all route to serve index.html for SPA client-side routing
        @self.app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa_index(full_path: str):
            """Serve Vue.js SPA for all non-API routes."""
            # Check if this is an API route
            # Need to check with leading slash
            path_with_slash = "/" + full_path if not full_path.startswith("/") else full_path
            
            # Check if path starts with any registered API prefix
            for api_path in self._registered_api_paths:
                if path_with_slash.startswith(api_path):
                    raise HTTPException(status_code=404, detail="API endpoint not found")
            
            # Also check if it starts with the general API prefix
            if path_with_slash.startswith(self.api_route_prefix):
                raise HTTPException(status_code=404, detail="API endpoint not found")
            
            index_html_path = os.path.join(static_files_dir, "index.html")
            
            # Check if the request path directly matches a file in the static directory
            # (e.g. /favicon.ico, /manifest.json, etc.)
            potential_file_path = os.path.join(static_files_dir, full_path)
            
            if os.path.isfile(potential_file_path):
                return FileResponse(potential_file_path)
            
            # If not a direct file, serve the main index.html for SPA routing
            if os.path.exists(index_html_path):
                return FileResponse(index_html_path)
            else:
                # In development, the frontend might not be built yet
                if os.getenv("ENV", "dev") == "dev":
                    return {
                        "message": "Frontend not found. In development, use 'npm run dev' for the frontend.",
                        "static_dir": static_files_dir
                    }
                else:
                    logger.error(f"SPA index.html not found at {index_html_path}")
                    raise HTTPException(status_code=404, detail="SPA client not found.")
    
    def get_app(self) -> FastAPI:
        """Return the FastAPI application instance."""
        return self.app