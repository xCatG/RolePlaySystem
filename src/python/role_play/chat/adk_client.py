"""
ADK client for managing roleplay agents and conversations in PRODUCTION.
It fetches configuration from the dev_agents module but runs the LLM directly.
"""
import os
import asyncio
from typing import Dict, Optional, Any
import logging

# Use google.generativeai directly for production calls
try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Import the config-exporting function from our new dev agent setup
try:
    from role_play.dev_agents.roleplay_agent.agent import get_production_config
    CONFIG_EXPORT_AVAILABLE = True
except ImportError:
    CONFIG_EXPORT_AVAILABLE = False

logger = logging.getLogger(__name__)

# --- ADKClient ---
class ADKClient:
    """Client for running roleplay LLM calls based on dev config."""

    def __init__(self):
        """Initialize the ADK client."""
        self._initialized = False
        self._current_config: Optional[Dict] = None
        self._genai_model = None

    def initialize(self) -> None:
        """Initialize Google GenAI if not already initialized."""
        if not self._initialized and GENAI_AVAILABLE:
            api_key = os.getenv("GOOGLE_AI_API_KEY")
            if not api_key:
                logger.error("GOOGLE_AI_API_KEY not set. Cannot initialize GenAI.")
                raise ValueError("GOOGLE_AI_API_KEY environment variable not set")

            try:
                genai.configure(api_key=api_key)
                self._initialized = True
                logger.info("Google GenAI initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI: {e}")
                raise
        elif not GENAI_AVAILABLE:
             logger.warning("google.generativeai not installed. Using placeholder responses.")


    def create_roleplay_session(self, character_id: str, scenario_id: str) -> bool:
        """
        Loads the configuration for a given character and scenario.
        Returns True if successful, False otherwise.
        """
        self.initialize()

        if not CONFIG_EXPORT_AVAILABLE:
            logger.error("Cannot load production config, dev_agent module not found.")
            self._current_config = None
            return False

        config = get_production_config(character_id, scenario_id)

        if not config:
            logger.error(f"Could not find config for char {character_id}, scenario {scenario_id}")
            self._current_config = None
            return False

        self._current_config = config
        logger.info(f"Loaded production config for: {config.get('character_name')}")

        # Prepare the genai model if available
        if GENAI_AVAILABLE and self._initialized:
            try:
                self._genai_model = genai.GenerativeModel(
                    self._current_config['model'],
                    system_instruction=self._current_config['system_prompt']
                    )
            except Exception as e:
                logger.error(f"Failed to create GenerativeModel: {e}")
                self._genai_model = None

        return True


    async def generate_response(
        self,
        user_message: str,
        session_context: Optional[Dict] = None
    ) -> str:
        """
        Generate a response using the loaded production config.
        """
        if not self._current_config:
            raise ValueError("No session created. Call create_roleplay_session first.")

        # --- Use Google GenAI if available ---
        if self._genai_model:
            try:
                # Build conversation history (simple format for genai)
                history = []
                if session_context and "messages" in session_context:
                    for msg in session_context["messages"][-10:]: # Last 10
                        if msg.get("type") == "message":
                            role = "user" if msg["role"] == "participant" else "model"
                            history.append({"role": role, "parts": [{"text": msg["content"]}]})

                # Create a chat session with history
                chat_session = self._genai_model.start_chat(history=history)

                # Send message and get response
                response = await chat_session.send_message_async(user_message)
                logger.info(f"Generated GenAI response for: {user_message[:50]}...")
                return response.text

            except Exception as e:
                logger.error(f"GenAI generation failed: {e}. Falling back to placeholder.")


        # --- Fallback Placeholder Response ---
        character_name = self._current_config.get("character_name", "Character")
        logger.warning(f"Using placeholder response for: {user_message[:50]}...")
        return f"[{character_name.split(' - ')[0]} responds in character to: {user_message}]"


    def reset(self) -> None:
        """Reset the client, clearing any current config."""
        self._current_config = None
        self._genai_model = None
        logger.info("ADK client reset")

# --- Global Client Instance ---
_adk_client = None

def get_adk_client() -> ADKClient:
    """Get or create the ADK client instance."""
    global _adk_client
    if _adk_client is None:
        _adk_client = ADKClient()
    return _adk_client