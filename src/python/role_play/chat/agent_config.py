"""ADK agent configuration for roleplay conversations."""
import os
from typing import Dict, Optional
from google import adk

class AgentConfig:
    """Configuration for ADK agents."""
    
    DEFAULT_MODEL = "gemini-2.0-flash"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 2000
    
    @classmethod
    def get_model(cls) -> str:
        """Get the AI model to use."""
        return os.getenv("ADK_MODEL", cls.DEFAULT_MODEL)
    
    @classmethod
    def get_generation_config(cls) -> Dict:
        """Get the generation configuration for the model."""
        return {
            "temperature": cls.DEFAULT_TEMPERATURE,
            "max_output_tokens": cls.DEFAULT_MAX_TOKENS,
            "top_p": 0.95,
            "top_k": 40
        }
    
    @classmethod
    def initialize_adk(cls) -> None:
        """Initialize the ADK with proper configuration."""
        # Set up environment variables if needed
        if not os.getenv("GOOGLE_AI_API_KEY"):
            raise ValueError("GOOGLE_AI_API_KEY environment variable not set")
        
        # Initialize ADK
        adk.init(
            api_key=os.getenv("GOOGLE_AI_API_KEY"),
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        )
    
    @classmethod
    def create_agent_prompt(cls, character_data: Dict, scenario_data: Dict) -> str:
        """Create a comprehensive system prompt for the agent.
        
        Args:
            character_data: Character information including system_prompt
            scenario_data: Scenario information for context
            
        Returns:
            Complete system prompt for the agent
        """
        base_prompt = character_data.get("system_prompt", "")
        
        # Add scenario context
        scenario_context = f"\n\nScenario Context: {scenario_data.get('description', '')}"
        
        # Add roleplay instructions
        roleplay_instructions = """

Remember to:
- Stay in character throughout the conversation
- Respond naturally as your character would
- Use appropriate emotional responses and mannerisms
- Keep responses conversational and realistic
- Don't break character or acknowledge you're an AI
"""
        
        return base_prompt + scenario_context + roleplay_instructions