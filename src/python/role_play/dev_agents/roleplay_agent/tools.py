"""
Tools for the development agent, primarily for exploring
scenarios and characters within the adk web environment.
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional

from google.adk.tools import FunctionTool

# Add project root to path to find ContentLoader
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
#sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))
resource_loader = None

try:
    from role_play.common.resource_loader import ResourceLoader
    from role_play.common.storage import FileStorageConfig
    from role_play.common.storage_factory import create_storage_backend
    from role_play.server.config import DevelopmentConfig
    file_storage_config = FileStorageConfig(base_dir=f"{PROJECT_ROOT}/data")
    storage = create_storage_backend(file_storage_config) # default to DEV with file storage
    resource_loader = ResourceLoader(storage) # this should be loading from {project_root}/data/resources

except ImportError:
    raise RuntimeError(f"Unable to import necessary storage config")

async def list_scenarios() -> str:
    """Lists all available roleplay scenarios by name and ID."""
    scenarios = await resource_loader.get_scenarios()
    if not scenarios:
        return "No scenarios found."
    return "\n".join([f"- {s['name']} (ID: {s['id']})" for s in scenarios])

async def list_scripts() -> str:
    """Lists all available roleplay scripts by goal and ID, and corresponding scenario and character."""
    scripts = await resource_loader.get_scripts()
    if not scripts:
        return "No scripts found."
    return "\n".join([f"- id: {s['id']}\tgoal: {s['goal']}\tscenario_id: {s['scenario_id']}\tchar_id: {s['character_id']}" for s in scripts])

async def list_characters(scenario_id: str) -> str:
    """Lists characters available for a specific scenario ID."""
    characters = await resource_loader.get_scenario_characters(scenario_id)
    if not characters:
        return f"No characters found for scenario '{scenario_id}' or scenario ID is invalid."
    return "\n".join([f"- {c['name']} (ID: {c['id']})" for c in characters])

async def get_character_prompt(character_id: str) -> str:
    """Gets the system prompt for a specific character ID."""
    character = await resource_loader.get_character_by_id(character_id)
    if not character:
        return f"Character '{character_id}' not found."
    return character.get("system_prompt", "No system prompt defined for this character.")

# Export tools only if ADK is available
dev_tools = [
    FunctionTool(list_scenarios),
    FunctionTool(list_characters),
    FunctionTool(get_character_prompt),
    FunctionTool(list_scripts),
]