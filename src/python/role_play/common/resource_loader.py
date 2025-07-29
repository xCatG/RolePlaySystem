import asyncio
import json
import logging
import os
from typing import Any, Dict, List

from role_play.common.storage import StorageBackend

logger = logging.getLogger(__name__)


class ResourceLoader:
    # Supported resource versions
    SUPPORTED_VERSIONS = ["1.0"]
    
    def __init__(self, storage: StorageBackend, base_prefix: str = "resources/"):
        self.storage = storage
        self.base_prefix = base_prefix
        self._cache: Dict[str, Any] = {}  # Internal cache: stores loaded JSON content

    async def _load_and_cache_json(self, path: str) -> Any:
        """Loads a specific JSON file from storage, validates version, and caches its content."""
        if path not in self._cache:
            content = await self.storage.read(path)
            data = json.loads(content)
            
            # Validate resource version
            resource_version = data.get("resource_version")
            if resource_version is None:
                # Legacy file without version - log warning but allow
                logger.warning(f"Resource file {path} missing resource_version field (legacy format)")
            elif resource_version not in self.SUPPORTED_VERSIONS:
                raise ValueError(
                    f"Unsupported resource version {resource_version} in {path}. "
                    f"Supported versions: {', '.join(self.SUPPORTED_VERSIONS)}"
                )
            
            self._cache[path] = data
        return self._cache[path]

    def invalidate_cache(self, path: str | None = None):
        """
        Invalidates the cache.
        - If path is provided, clears a specific file's cache.
        - If None, clears the entire cache.
        """
        if path:
            self._cache.pop(path, None)
        else:
            self._cache.clear()

    async def _find_resource_path(self, resource_type: str, language: str) -> str | None:
        """
        Finds the correct resource file path for a given type and language.
        Example: resource_type='scenarios', language='zh-TW' -> 'resources/scenarios/scenarios_zh-TW.json'
        """
        prefix = os.path.join(self.base_prefix, resource_type)
        all_files = await self.storage.list_keys(prefix)

        # Try to find a language-specific file
        lang_suffix = f"_{language}.json"
        for file_path in all_files:
            if file_path.endswith(lang_suffix):
                return file_path

        # Fallback to the default resource file (e.g., scenarios.json)
        default_file_name = f"{resource_type}.json"
        for file_path in all_files:
            if os.path.basename(file_path) == default_file_name:
                return file_path
        
        return None

    async def _get_all_from_resource_type(self, resource_type: str, language: str = "en") -> list[dict]:
        """Generic function to load all items from a resource type (e.g., all scenarios)."""
        path = await self._find_resource_path(resource_type, language)
        if not path:
            return []
        
        data = await self._load_and_cache_json(path)
        return data.get(resource_type, [])

    async def get_scenarios(self, language: str = "en") -> list[dict]:
        """Loads all scenarios for a specific language."""
        return await self._get_all_from_resource_type("scenarios", language)

    async def get_characters(self, language: str = "en") -> list[dict]:
        """Loads all characters for a specific language."""
        return await self._get_all_from_resource_type("characters", language)

    async def get_scenario_by_id(self, scenario_id: str, language: str = "en") -> dict | None:
        """Gets a single scenario by its ID for the specified language."""
        scenarios = await self.get_scenarios(language)
        return next((s for s in scenarios if s.get("id") == scenario_id), None)

    async def get_character_by_id(self, character_id: str, language: str = "en") -> dict | None:
        """Gets a single character by its ID for the specified language."""
        characters = await self.get_characters(language)
        return next((c for c in characters if c.get("id") == character_id), None)

