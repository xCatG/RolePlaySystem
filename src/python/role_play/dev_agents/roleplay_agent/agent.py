"""
Development agent for adk web and configuration export for production.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Optional
from google.adk.agents import Agent

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))
DEFAULT_MODEL = "gemini-1.5-flash" # Set a reasonable default
AGENT_MODEL = os.getenv("ADK_MODEL", DEFAULT_MODEL) # <-- Read from env

from .tools import resource_loader
from role_play.chat.orchestrator_agent import (
    Orchestrator,
    ScriptTracker,
    SideEffectExecutor,
    observer_agent,
    actor_agent,
)

# --- Bootstrap and create the final root_agent ---

# This would load your script rules from a file (e.g., data/resources/scripts/scripts.json)
tracker = ScriptTracker(rules=[
    # ... your ScriptRule instances ...
])

executor = SideEffectExecutor()

# This is the single entry point for your entire role-play system.
# This agent will be picked up by `adk web`.
root_agent = Orchestrator(
    name="RolePlaySystem",
    tracker=tracker,
    observer=observer_agent,
    actor=actor_agent,
    executor=executor,
)

agent = root_agent


# --- Configuration Export for Production (Legacy) ---
# Note: The primary agent is now the Orchestrator above. 
# This function remains for reference but creates a different, simpler agent type.
# It may need to be adapted or removed in the future.

class RolePlayAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

async def get_production_agent(character_id: str, scenario_id: str, language: str = "en", scripted: bool = False) -> Optional[Agent]:
    """
    Creates a production-ready RolePlayAgent for a specific
    character, scenario, and language.
    
    Args:
        character_id: The ID of the character
        scenario_id: The ID of the scenario
        language: The language code (e.g., "en", "zh-TW", "ja")
    
    Returns:
        A configured RolePlayAgent instance or None if character/scenario not found
    """
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
        scripted_prompt = '''
You are improvising based on "character" part of the script below, DO NOT say the lines in "participant" part. 
Try to steer conversation to follow the script. 
However when you are unable to steer the user back, please respond with "STOP". If you feel you can continue to improvise after the script end, please continue.

Here is the script:
{script_data}
'''

    # Production-focused prompt: Combines character, scenario, and language instructions
    prod_prompt = f'''{character.get(