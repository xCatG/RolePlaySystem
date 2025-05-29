"""Base server class for the Role Play System."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    
    def _setup_cors(self):
        """Setup CORS middleware for frontend development."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],  # Vue.js dev servers
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
        
        # Include the handler's router
        self.app.include_router(
            handler.router,
            prefix=handler.prefix,
            tags=handler.tags,
        )
        
        logger.info(f"Registered {handler_class.__name__} at {handler.prefix}")
    
    def get_app(self) -> FastAPI:
        """Return the FastAPI application instance."""
        return self.app