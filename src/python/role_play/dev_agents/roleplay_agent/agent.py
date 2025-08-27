"""
Development agent for adk web and configuration export for production.
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Optional
from google.adk.agents import Agent

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))
DEFAULT_MODEL = "gemini-2.5-flash" # Set a reasonable default
AGENT_MODEL = os.getenv("ADK_MODEL", DEFAULT_MODEL) # <-- Read from env

logger = logging.getLogger(__name__)

from .tools import dev_tools

# --- Development Agent for adk web ---

class RolePlayAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


root_agent = RolePlayAgent(
        name="roleplay_dev_agent",
        model=AGENT_MODEL, # Use a capable model
        description="Development agent for testing roleplay prompts and tools.",
        instruction="""You are a development assistant for a roleplay system.
Your main purpose is to help test character prompts and interaction flows using 'adk web'.

Use your tools to:
1.  List available scenarios.
2.  List characters for a scenario.
3.  List available scripts
4.  Show the system prompt for a character.

To test a character, get their prompt using 'get_character_prompt', copy it,
and then paste it into a new chat session (or imagine you are that character).
You DO NOT need to manage state or *become* the character in this dev view.
Focus on providing information and allowing prompt testing.""",
        tools=dev_tools,
    )

agent = root_agent

# --- Configuration Export for Production ---

async def get_production_agent(character_id: str, scenario_id: str, language: str = "en", scripted: bool = False, agent_model: str = AGENT_MODEL, resource_loader=None) -> Optional[Agent]:
    """
    Creates a production-ready RolePlayAgent for a specific
    character, scenario, and language.
    
    Args:
        character_id: The ID of the character
        scenario_id: The ID of the scenario
        language: The language code (e.g., "en", "zh-TW", "ja")
        scripted: whether the session is scripted or not
        agent_model: id of the llm model to use
        resource_loader: ResourceLoader instance (injected from handler)
    
    Returns:
        A configured RolePlayAgent instance or None if character/scenario not found
    """
    # Use the injected resource_loader or create a fallback one
    if resource_loader is None:
        # Try to get from dependency injection system first
        try:
            from ...server.dependencies import get_resource_loader
            resource_loader = get_resource_loader()
            logger.info(f"Using dependency-injected ResourceLoader from server")
        except ImportError:
            # Last resort: Use the fallback FileStorage ResourceLoader 
            from .tools import resource_loader as fallback_loader
            resource_loader = fallback_loader
            logger.warning(f"Using fallback FileStorage ResourceLoader (dev only)")
    else:
        logger.info(f"Creating agent with {type(resource_loader).__name__}")
    
    # Use await since resource_loader methods are async
    character = await resource_loader.get_character_by_id(character_id, language)
    scenario = await resource_loader.get_scenario_by_id(scenario_id, language)

    if not character or not scenario:
        return None

    # Get language display name
    language_names = {
        "en": "English",
        "zh-TW": "Traditional Chinese",
        "ja": "Japanese"
    }
    language_name = language_names.get(language, "English")

    scripted_prompt = None
    if scripted:
        # we store the script in state[script_data], should be able to retrive it using {script_data} in the prompt
        scripted_prompt = """
You are improvising based on "character" part of the script below, DO NOT say the lines in "participant" part. 
Try to steer conversation to follow the script. 
However when you are unable to steer the user back, please respond with "STOP". If you feel you can continue to improvise after the script end, please continue.

Here is the script:
{script_data}
"""

    # Production-focused prompt: Combines character, scenario, and language instructions
    prod_prompt = f"""{character.get("system_prompt", "You are a helpful assistant.")}

**Current Scenario:**
{scenario.get("description", "No specific scenario description.")}

**Roleplay Instructions:**
-   **Stay fully in character.** Do NOT break character or mention you are an AI.
-   Respond naturally based on your character's personality and the scenario.
-   **IMPORTANT: Respond in {language_name} language as specified by your character and scenario.**
-   Engage with the user's messages within the roleplay context.
"""
    if scripted_prompt is not None:
        prod_prompt += scripted_prompt
    # Create and return the configured agent
    return RolePlayAgent(
        name=f"roleplay_{character_id}_{scenario_id}",
        model=agent_model,
        description=f"Roleplay agent for {character.get('name', 'Unknown Character')} in {scenario.get('name', 'Unknown Scenario')}",
        instruction=prod_prompt
    )

# --- Main block for verification ---
if __name__ == "__main__":
    import asyncio

    async def test_module():
        print("Roleplay Development Agent Module")
        print(f"Agent Name: {root_agent.name}")
        print(f"Tools loaded: {len(dev_tools)}")

        print("\nTesting production agent creation:")
        # Assuming 'medical_interview' and 'patient_chronic' exist in scenarios.json
        agent = await get_production_agent("patient_chronic", "medical_interview")
        if agent:
            print("Successfully created agent for 'patient_chronic'.")
            print(f"  Model: {agent.model}")
            print(f"  Name: {agent.name}")
            print(f"  Instruction starts with: {agent.instruction[:100]}...")
        else:
            print("Failed to create agent (check scenarios.json?).")

    asyncio.run(test_module())
