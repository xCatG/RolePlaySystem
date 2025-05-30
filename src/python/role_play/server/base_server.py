"""Base server class for the Role Play System."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from typing import Type
from contextlib import asynccontextmanager
from .base_handler import BaseHandler
import logging

logger = logging.getLogger(__name__)


class BaseServer:
    """
    Base server class that manages FastAPI app and handler registration.
    
    Provides automatic handler registration and common middleware setup.
    """
    
    def __init__(
        self,
        title: str = "Role Play System",
        description: str = "Role Play System API",
        version: str = "1.0.0",
        enable_cors: bool = True,
    ):
        """
        Initialize the base server.
        
        Args:
            title: API title for OpenAPI docs
            description: API description for OpenAPI docs
            version: API version
            enable_cors: Whether to enable CORS middleware
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
        
        if enable_cors:
            self._setup_cors()
        
        # Don't setup static files here - we'll do it after handlers are registered
        self._static_frontend_dir = "static_frontend"
    
    def _setup_cors(self):
        """Setup CORS middleware for frontend development."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],  # Vue.js dev servers
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

        # Health check endpoint - add before catch-all route
        @self.app.get("/health", tags=["Health"])
        async def health_check():
            """Health check endpoint that reports system status."""
            health_status = {
                "status": "healthy",
                "version": self.app.version,
                "checks": {}
            }
            
            # Check scenarios loading
            try:
                from ..server.dependencies import get_content_loader
                loader = get_content_loader()
                scenarios = loader.get_scenarios()
                health_status["checks"]["scenarios"] = {
                    "status": "ok",
                    "count": len(scenarios),
                    "data_file": str(loader.data_file.absolute())
                }
            except Exception as e:
                health_status["status"] = "degraded"
                health_status["checks"]["scenarios"] = {
                    "status": "error",
                    "error": str(e)
                }
            
            # Check storage
            try:
                storage_path = os.getenv("STORAGE_PATH", "./data")
                if os.path.exists(storage_path) and os.access(storage_path, os.R_OK | os.W_OK):
                    health_status["checks"]["storage"] = {
                        "status": "ok",
                        "path": os.path.abspath(storage_path)
                    }
                else:
                    health_status["status"] = "degraded"
                    health_status["checks"]["storage"] = {
                        "status": "error",
                        "error": "Storage path not accessible"
                    }
            except Exception as e:
                health_status["status"] = "degraded"
                health_status["checks"]["storage"] = {
                    "status": "error",
                    "error": str(e)
                }
            
            return health_status
        
        # Catch-all route for Vue app (client-side routing)
        @self.app.get("/{full_path:path}", include_in_schema=False)
        async def serve_vue_app(full_path: str):
            index_html_path = os.path.join(static_frontend_dir, "index.html")
            if os.path.exists(index_html_path):
                return FileResponse(index_html_path)
            else:
                logger.error(f"index.html not found at {index_html_path}")
                from fastapi.responses import HTMLResponse
                return HTMLResponse(content="Frontend not found.", status_code=404)
    
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