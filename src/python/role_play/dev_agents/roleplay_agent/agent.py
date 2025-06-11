"""
Development agent for adk web and configuration export for production.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Optional
from google.adk.agents import Agent
from .tools import dev_tools, content_loader

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))
DEFAULT_MODEL = "gemini-2.0-flash-lite-001" # Set a reasonable default
AGENT_MODEL = os.getenv("ADK_MODEL", DEFAULT_MODEL) # <-- Read from env

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
3.  Show the system prompt for a character.

To test a character, get their prompt using 'get_character_prompt', copy it,
and then paste it into a new chat session (or imagine you are that character).
You DO NOT need to manage state or *become* the character in this dev view.
Focus on providing information and allowing prompt testing.""",
        tools=dev_tools,
    )

agent = root_agent

# --- Configuration Export for Production ---

def get_production_config(character_id: str, scenario_id: str) -> Optional[Dict]:
    """
    Generates the configuration (prompt, model) for a specific
    character and scenario, intended for production use.
    """
    character = content_loader.get_character_by_id(character_id)
    scenario = content_loader.get_scenario_by_id(scenario_id)

    if not character or not scenario:
        return None

    # Production-focused prompt: Combines character and scenario
    prod_prompt = f"""{character.get("system_prompt", "You are a helpful assistant.")}

**Current Scenario:**
{scenario.get("description", "No specific scenario description.")}

**Roleplay Instructions:**
-   **Stay fully in character.** Do NOT break character or mention you are an AI.
-   Respond naturally based on your character's personality and the scenario.
-   Engage with the user's messages within the roleplay context.
"""

    return {
        "model": AGENT_MODEL,
        "system_prompt": prod_prompt,
        "temperature": 0.75,
        "max_output_tokens": 2000,
        "character_name": character.get("name"),
        "scenario_name": scenario.get("name"),
    }

# --- Main block for verification ---
if __name__ == "__main__":
    print("Roleplay Development Agent Module")
    print(f"Agent Name: {root_agent.name}")
    print(f"Tools loaded: {len(dev_tools)}")

    print("\nTesting production config export:")
    # Assuming 'medical_interview' and 'patient_chronic' exist in scenarios.json
    config = get_production_config("patient_chronic", "medical_interview")
    if config:
        print("Successfully generated config for 'patient_chronic'.")
        print(f"  Model: {config['model']}")
        print(f"  Prompt starts with: {config['system_prompt'][:100]}...")
    else:
        print("Failed to generate config (check scenarios.json?).")
