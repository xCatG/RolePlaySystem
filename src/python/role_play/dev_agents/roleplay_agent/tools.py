"""
Tools for the development agent, primarily for exploring
scenarios and characters within the adk web environment.
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add project root to path to find ContentLoader
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

try:
    from role_play.chat.content_loader import ContentLoader
    from google.adk.tools import FunctionTool

    ADK_AVAILABLE = True
    content_loader = ContentLoader(data_file=str(PROJECT_ROOT / "data" / "scenarios.json"))
except ImportError:
    ADK_AVAILABLE = False
    # Define dummy classes if ADK or ContentLoader not found
    class FunctionTool:
        def __init__(self, *args, **kwargs): pass
    class ContentLoader:
        def get_scenarios(self): return [{"id": "err", "name": "Error Loading"}]
        def get_scenario_characters(self, _): return [{"id": "err", "name": "Error Loading"}]
        def get_character_by_id(self, _): return None
    content_loader = ContentLoader()

def list_scenarios() -> str:
    """Lists all available roleplay scenarios by name and ID."""
    scenarios = content_loader.get_scenarios()
    if not scenarios:
        return "No scenarios found."
    return "\n".join([f"- {s['name']} (ID: {s['id']})" for s in scenarios])

def list_characters(scenario_id: str) -> str:
    """Lists characters available for a specific scenario ID."""
    characters = content_loader.get_scenario_characters(scenario_id)
    if not characters:
        return f"No characters found for scenario '{scenario_id}' or scenario ID is invalid."
    return "\n".join([f"- {c['name']} (ID: {c['id']})" for c in characters])

def get_character_prompt(character_id: str) -> str:
    """Gets the system prompt for a specific character ID."""
    character = content_loader.get_character_by_id(character_id)
    if not character:
        return f"Character '{character_id}' not found."
    return character.get("system_prompt", "No system prompt defined for this character.")

# Export tools only if ADK is available
dev_tools = [
    FunctionTool(list_scenarios),
    FunctionTool(list_characters),
    FunctionTool(get_character_prompt),
] if ADK_AVAILABLE else []