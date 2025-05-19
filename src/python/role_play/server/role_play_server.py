"""
FastAPI server for role play system backend using a class-based design
with stateless request handlers
"""
import uuid
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Path
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from datetime import datetime


from role_play.server.config import ServerConfig, config
from role_play.server.models import ChatResponse, StatusResponse, ChatRequest


class RolePlayServer:
    """
    Class-based implementation of the Role Play Server
    
    This class encapsulates the FastAPI app and routes but uses
    stateless handlers for each request to avoid state pollution.
    """
    
    def __init__(self, config:ServerConfig=config):
        """Initialize the server class"""
        self.app = FastAPI(
            title="Role Play System API",
            description="API for chat, script generation, and evaluation in role-play scenarios",
            version=config.version,
            lifespan=self.lifespan_context,
        )
        
        # Storage for scripts and evaluations (in production, these would be in a database)
        # These are only kept here for demo purposes. In a real app, each handler would
        # access the database directly.
        self.scripts = {}
        self.evaluations = {}
        
        # Long-lived resources (initialized once per worker process)
        self.chat_agent = None
        self.evaluator_agent = None
        self.script_generator = None
        self.db_connection = None  # Would be a database connection pool in production
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware, # type: ignore
            allow_origins=["*"],  # For development; restrict in production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes()
    
    @asynccontextmanager
    async def lifespan_context(self, app: FastAPI):
        """Lifespan context manager for the FastAPI app"""
        # Startup code
        logger.info(f"Starting Role Play Server v{config.version}")
        logger.info(f"Environment: {config.environment}")
        logger.info(f"Debug mode: {'Enabled' if config.debug else 'Disabled'}")
        
        # Validate configuration
        if not config.validate_config():
            logger.warning("Server starting with invalid configuration")
        
        # Log available providers
        providers = config.get_api_info()
        logger.info(f"Available providers: {[p for p, available in providers.items() if available]}")
        
        # Initialize long-lived resources
        try:
            # Try to initialize the real agents if possible
            # Use stub implementations as fallbacks if there are initialization errors


            # Initialize database connection (placeholder)
            # self.db_connection = await Database.connect()
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing server components: {str(e)}", exc_info=True)
            # Use stub implementations as fallbacks

            logger.info("Using stub implementations for all components")
        
        yield  # This is where FastAPI serves the application
        
        # Shutdown code
        logger.info("Shutting down Role Play Server")
        
        # Close database connection (placeholder)
        # await self.db_connection.close()
    
    def _register_routes(self):
        """Register all API routes with the FastAPI app"""
        # Status endpoints
        self.app.get("/")(self.get_status)
        self.app.get("/status")(self.get_status)
        
        # Chat endpoints
        self.app.post("/chat", response_model=ChatResponse)(self.create_chat)
        
        # Script endpoints
        # self.app.post("/scripts", response_model=ScriptResponse)(self.create_script)
        # self.app.get("/scripts/{script_id}", response_model=ScriptResponse)(self.get_script)
        
        # Evaluation endpoints
        # self.app.post("/evaluations", response_model=EvaluationResponse)(self.create_evaluation)
    
    # --- API Route Handlers ---
    
    async def get_status(self):
        """Status endpoint with API information"""
        return StatusResponse(
            status="ok",
            version=config.version,
            environment=config.environment,
            providers=config.get_api_info(),
        )

    async def create_chat(self):
        """

        :return:
        """
        return ChatResponse()
    
    def run(self, host=None, port=None):
        """Run the FastAPI server"""
        host = host or config.host
        port = port or config.port
        
        if config.debug:
            # When debug mode is enabled, use import string for hot reload
            uvicorn.run(
                "role_play.server.role_play_server:app",
                host=host,
                port=port,
                reload=True,
                log_level="debug",
            )
        else:
            # In production mode, use the app instance directly
            uvicorn.run(
                self.app,
                host=host,
                port=port,
                log_level="info",
            )


# Create a server instance for importing
server = RolePlayServer()
app = server.app
logger = logging.getLogger(__name__)

# --- Server Entry Point ---

def start_server(host=None, port=None):
    """Start the FastAPI server"""
    server.run(host=host, port=port)

if __name__ == "__main__":
    # TODO use different config to start server

    start_server()
