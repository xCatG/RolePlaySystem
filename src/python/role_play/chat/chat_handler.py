"""
Chat handler for processing chat requests in a stateless manner
"""
from typing import Dict, List, Optional
import uuid
from datetime import datetime
import logging

from role_play.server.models import (
    ChatMessage, ChatRequest, ChatResponse, 
    ModelProvider, ChatMode
)
from role_play.chat.chat_agent import ChatAgent

logger = logging.getLogger("chat_handler")

class ChatHandler:
    """
    Stateless handler for processing chat requests
    
    A new instance is created for each request to avoid state pollution.
    """
    
    def __init__(self, chat_agent: ChatAgent, db_connection=None, api_keys: Dict[str, str] = None):
        """
        Initialize a new chat handler for this specific request
        
        Args:
            chat_agent: The LLM agent to use for generating responses
            db_connection: Database connection for persistence (optional)
            api_keys: Dictionary of API keys for different providers
        """
        self.chat_agent = chat_agent
        self.db_connection = db_connection
        self.api_keys = api_keys or {}
        self.request_id = str(uuid.uuid4())
        
        # This is request-specific state that will be discarded after processing
        self.current_provider = None
        self.script = None
    
    async def process_request(self, request: ChatRequest, scripts: Dict = None) -> ChatResponse:
        """
        Process a chat request and generate a response
        
        Args:
            request: The chat request to process
            scripts: Dictionary of available scripts (temporary, would be in DB in production)
            
        Returns:
            ChatResponse: The generated response
        """
        logger.info(f"Processing chat request: {self.request_id}")
        
        try:
            # Select the appropriate provider based on availability
            self.current_provider = self._select_provider(request.provider)
            
            # Handle different chat modes
            if request.mode == ChatMode.ROLE_PLAY and request.script_id:
                # Get the script if available
                if scripts and request.script_id in scripts:
                    self.script = scripts[request.script_id]
                    response_content = await self._generate_role_play_response(request)
                else:
                    raise ValueError(f"Script with ID {request.script_id} not found")
                    
            elif request.mode == ChatMode.EVALUATION:
                response_content = await self._generate_evaluation_response(request)
                
            else:
                # Normal chat mode
                response_content = await self._generate_normal_response(request)
            
            # Create and return the response
            return self._create_response(response_content)
            
        except Exception as e:
            logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
            raise
    
    async def _generate_normal_response(self, request: ChatRequest) -> str:
        """Generate a response for normal chat mode"""
        # In a real implementation, this would use the chat_agent to generate a response
        # based on the message history and selected model/provider
        
        # Example of calling the chat agent (implementation depends on your ChatAgent class)
        # response = await self.chat_agent.generate_response(
        #     messages=request.messages,
        #     provider=self.current_provider,
        #     model=request.model,
        #     temperature=request.temperature,
        #     max_tokens=request.max_tokens
        # )
        
        # For now, this is a placeholder
        message_count = len(request.messages)
        last_message = request.messages[-1].content if message_count > 0 else ""
        return f"Response to: {last_message[:30]}... (using {self.current_provider})"
    
    async def _generate_role_play_response(self, request: ChatRequest) -> str:
        """Generate a response for role-play mode using a script"""
        # This would use the script to guide the response generation
        script_title = self.script.get("title", "Unknown script")
        return f"Role play response using script: {script_title}"
    
    async def _generate_evaluation_response(self, request: ChatRequest) -> str:
        """Generate a response for evaluation mode"""
        return "Evaluation mode response analyzing the conversation quality"
    
    def _select_provider(self, requested_provider: ModelProvider) -> ModelProvider:
        """Select an appropriate provider based on availability"""
        # If we have the requested provider's API key, use it
        if requested_provider.value in self.api_keys and self.api_keys[requested_provider.value]:
            return requested_provider
            
        # Otherwise, fall back to an available provider
        for provider_name, api_key in self.api_keys.items():
            if api_key:
                provider = ModelProvider(provider_name)
                logger.warning(f"Requested provider {requested_provider} not available, falling back to {provider}")
                return provider
                
        # If no providers are available, raise an error
        raise ValueError("No LLM providers available")
    
    def _create_response(self, content: str) -> ChatResponse:
        """Create a ChatResponse object with the generated content"""
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=content,
                timestamp=datetime.now(),
            ),
            usage={"total_tokens": len(content.split())},  # Simplified token count
            request_id=self.request_id,
        )
    
    async def save_conversation(self, messages: List[ChatMessage]) -> None:
        """Save the conversation to persistent storage"""
        # In a real implementation, this would save to a database
        if self.db_connection:
            # Example: await self.db_connection.save_conversation(self.request_id, messages)
            logger.info(f"Saved conversation {self.request_id} to database")
        else:
            logger.warning(f"No database connection available, conversation {self.request_id} not saved")
    
    def __del__(self):
        """Clean up any resources when the handler is garbage collected"""
        # Close any connections or clean up resources if needed
        logger.debug(f"ChatHandler for request {self.request_id} is being cleaned up")
