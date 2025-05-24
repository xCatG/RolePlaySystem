"""ADK client for managing roleplay agents and conversations."""
import os
import asyncio
from typing import Dict, Optional, Any
from google import adk
from .agent_config import AgentConfig
import logging

logger = logging.getLogger(__name__)

class ADKClient:
    """Client for interacting with ADK agents."""
    
    def __init__(self):
        """Initialize the ADK client."""
        self._initialized = False
        self._current_agent = None
        self._model = AgentConfig.get_model()
        self._generation_config = AgentConfig.get_generation_config()
    
    def initialize(self) -> None:
        """Initialize ADK if not already initialized."""
        if not self._initialized:
            try:
                AgentConfig.initialize_adk()
                self._initialized = True
                logger.info("ADK initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize ADK: {e}")
                raise
    
    async def create_roleplay_agent(
        self, 
        character_data: Dict, 
        scenario_data: Dict
    ) -> Any:
        """Create a new roleplay agent with the given character and scenario.
        
        Args:
            character_data: Character information including system_prompt
            scenario_data: Scenario information for context
            
        Returns:
            Configured agent instance
        """
        self.initialize()
        
        # Create the system prompt
        system_prompt = AgentConfig.create_agent_prompt(character_data, scenario_data)
        
        # Create agent with configuration
        # Note: In production ADK, this would create a proper agent instance
        # For now, we'll store the configuration for use in generate_response
        self._current_agent = {
            "system_prompt": system_prompt,
            "character_name": character_data.get("name", "Character"),
            "scenario_name": scenario_data.get("name", "Scenario")
        }
        
        logger.info(f"Created roleplay agent for {self._current_agent['character_name']}")
        return self._current_agent
    
    async def generate_response(
        self, 
        user_message: str,
        session_context: Optional[Dict] = None
    ) -> str:
        """Generate a response from the current agent.
        
        Args:
            user_message: The user's message
            session_context: Optional session context (previous messages, etc.)
            
        Returns:
            The agent's response
        """
        if not self._current_agent:
            raise ValueError("No agent created. Call create_roleplay_agent first.")
        
        try:
            # In a real ADK implementation, this would use the ADK's generate method
            # For POC, we'll simulate with a placeholder that shows the flow
            logger.info(f"Generating response for: {user_message[:50]}...")
            
            # TODO: Replace with actual ADK generation call
            # response = await adk.generate(
            #     prompt=user_message,
            #     system_prompt=self._current_agent["system_prompt"],
            #     **self._generation_config
            # )
            
            # POC placeholder response
            character_name = self._current_agent["character_name"].split(" - ")[0]
            response = f"[{character_name} responds in character to: {user_message}]"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise
    
    def get_current_agent_info(self) -> Optional[Dict]:
        """Get information about the current agent.
        
        Returns:
            Agent information or None if no agent is active
        """
        return self._current_agent
    
    def reset(self) -> None:
        """Reset the client, clearing any current agent."""
        self._current_agent = None
        logger.info("ADK client reset")

# Global client instance (created per handler in production)
_adk_client = None

def get_adk_client() -> ADKClient:
    """Get or create the ADK client instance.
    
    Returns:
        ADK client instance
    """
    global _adk_client
    if _adk_client is None:
        _adk_client = ADKClient()
    return _adk_client