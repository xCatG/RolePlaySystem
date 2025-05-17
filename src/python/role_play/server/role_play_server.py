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

# Import our configuration
from role_play.server.config import config
from role_play.server.models import (
    ChatMessage, ChatRequest, ChatResponse, 
    ScriptRequest, ScriptResponse, 
    EvaluationRequest, EvaluationResponse,
    StatusResponse, ModelProvider, ChatMode
)

# Import components from other modules
from role_play.chat.chat_agent import ChatAgent
from role_play.chat.chat_handler import ChatHandler

try:
    from role_play.scripter import ScriptGenerator  # Import if available
except ImportError:
    # Create a stub class if not available
    class ScriptGenerator:
        """Stub class for ScriptGenerator"""
        def generate_script(self, **kwargs):
            return {"error": "ScriptGenerator not implemented"}

from role_play.evaluator.evaluator_agent import EvaluatorAgent

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if config.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("role_play_server")


# Create stub implementations for the agents to avoid dependency issues
class StubChatAgent:
    """Stub implementation of ChatAgent for development"""
    def __init__(self, name="ChatAgent"):
        self.name = name
        logger.info(f"Initialized stub {self.name}")
        
    async def generate_response(self, messages, **kwargs):
        """Simulate generating a response"""
        return "This is a stub response from ChatAgent"
        
class StubEvaluatorAgent:
    """Stub implementation of EvaluatorAgent for development"""
    def __init__(self, name="EvaluatorAgent"):
        self.name = name
        logger.info(f"Initialized stub {self.name}")
        
    async def evaluate(self, conversation, **kwargs):
        """Simulate evaluation"""
        return {
            "scores": {"overall": 0.85},
            "feedback": "This is stub feedback from EvaluatorAgent"
        }
        
class StubScriptGenerator:
    """Stub implementation of ScriptGenerator for development"""
    def __init__(self, name="ScriptGenerator"):
        self.name = name
        logger.info(f"Initialized stub {self.name}")
        
    async def generate_script(self, prompt, **kwargs):
        """Simulate script generation"""
        return {
            "title": f"Script from: {prompt[:20]}...",
            "characters": [
                {"name": "Character 1", "description": "Description of character 1"},
                {"name": "Character 2", "description": "Description of character 2"},
            ],
            "scenes": [
                {"description": "Scene 1 description", "dialogue": []},
            ],
        }


class RolePlayServer:
    """
    Class-based implementation of the Role Play Server
    
    This class encapsulates the FastAPI app and routes but uses
    stateless handlers for each request to avoid state pollution.
    """
    
    def __init__(self):
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
            CORSMiddleware,
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
            try:
                self.chat_agent = ChatAgent(name="ChatAgent")
                logger.info("Initialized real ChatAgent")
            except Exception as e:
                logger.warning(f"Could not initialize real ChatAgent: {str(e)}")
                self.chat_agent = StubChatAgent()
                
            try:
                self.evaluator_agent = EvaluatorAgent(name="EvaluatorAgent")
                logger.info("Initialized real EvaluatorAgent")
            except Exception as e:
                logger.warning(f"Could not initialize real EvaluatorAgent: {str(e)}")
                self.evaluator_agent = StubEvaluatorAgent()
                
            try:
                # Try to use the real ScriptGenerator if available
                self.script_generator = ScriptGenerator(name="ScriptGenerator")
                logger.info("Initialized real ScriptGenerator")
            except Exception as e:
                logger.warning(f"Could not initialize real ScriptGenerator: {str(e)}")
                self.script_generator = StubScriptGenerator()
                
            # Initialize database connection (placeholder)
            # self.db_connection = await Database.connect()
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing server components: {str(e)}", exc_info=True)
            # Use stub implementations as fallbacks
            self.chat_agent = StubChatAgent()
            self.evaluator_agent = StubEvaluatorAgent()
            self.script_generator = StubScriptGenerator()
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
        self.app.post("/scripts", response_model=ScriptResponse)(self.create_script)
        self.app.get("/scripts/{script_id}", response_model=ScriptResponse)(self.get_script)
        
        # Evaluation endpoints
        self.app.post("/evaluations", response_model=EvaluationResponse)(self.create_evaluation)
    
    # --- API Route Handlers ---
    
    async def get_status(self):
        """Status endpoint with API information"""
        return StatusResponse(
            status="ok",
            version=config.version,
            environment=config.environment,
            providers=config.get_api_info(),
        )
    
    async def create_chat(
        self,
        request: ChatRequest,
        background_tasks: BackgroundTasks,
    ):
        """
        Process a chat request using a stateless handler
        
        A new ChatHandler is created for each request to avoid state pollution.
        """
        try:
            # Get API keys from configuration
            api_keys = {
                ModelProvider.OPENAI.value: config.openai_api_key,
                ModelProvider.ANTHROPIC.value: config.anthropic_api_key,
                ModelProvider.GOOGLE.value: config.google_api_key,
            }
            
            # Create a new stateless handler for this specific request
            handler = ChatHandler(
                chat_agent=self.chat_agent,
                db_connection=self.db_connection,
                api_keys=api_keys
            )
            
            # Process the request using the handler
            response = await handler.process_request(request, scripts=self.scripts)
            
            # Use a background task to save the conversation
            # This avoids blocking the response
            background_tasks.add_task(
                handler.save_conversation,
                request.messages + [response.message]
            )
            
            return response
            
        except ValueError as e:
            # Handle expected errors
            logger.warning(f"Invalid request: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def create_script(
        self,
        request: ScriptRequest,
    ):
        """Generate a new role play script"""
        # Generate a unique script ID
        script_id = str(uuid.uuid4())
        
        try:
            # Use the script generator to create a script
            script_content = await self.script_generator.generate_script(
                prompt=request.prompt,
                parameters=request.parameters
            )
            
            # Store the script (in production, this would go to a database)
            self.scripts[script_id] = script_content
            
            return ScriptResponse(
                script_id=script_id,
                script_content=script_content,
                created_at=datetime.now(),
            )
            
        except Exception as e:
            logger.error(f"Error generating script: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def get_script(
        self,
        script_id: str = Path(..., description="Script ID")
    ):
        """Retrieve an existing script by ID"""
        if script_id not in self.scripts:
            raise HTTPException(status_code=404, detail=f"Script with ID {script_id} not found")
            
        return ScriptResponse(
            script_id=script_id,
            script_content=self.scripts[script_id],
            created_at=datetime.now(),  # In a real app, store the creation time
        )
    
    async def create_evaluation(
        self,
        request: EvaluationRequest,
    ):
        """Evaluate a conversation"""
        # Generate a unique evaluation ID
        evaluation_id = str(uuid.uuid4())
        
        try:
            # Check if we need to use a script
            script = None
            if request.script_id:
                if request.script_id not in self.scripts:
                    raise HTTPException(status_code=404, detail=f"Script with ID {request.script_id} not found")
                script = self.scripts[request.script_id]
                
            # Use the evaluator agent to evaluate the conversation
            evaluation_result = await self.evaluator_agent.evaluate(
                conversation=request.conversation,
                script=script,
                criteria=request.criteria
            )
            
            # Extract scores and feedback from the result
            scores = evaluation_result.get("scores", {})
            feedback = evaluation_result.get("feedback", "No feedback provided")
            
            # Store the evaluation results (in production, this would go to a database)
            self.evaluations[evaluation_id] = {
                "scores": scores,
                "feedback": feedback,
                "conversation": request.conversation,
                "script_id": request.script_id,
            }
            
            return EvaluationResponse(
                scores=scores,
                feedback=feedback,
                evaluation_id=evaluation_id,
            )
            
        except Exception as e:
            logger.error(f"Error creating evaluation: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")
    
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

# --- Server Entry Point ---

def start_server(host=None, port=None):
    """Start the FastAPI server"""
    server.run(host=host, port=port)

if __name__ == "__main__":
    start_server()
