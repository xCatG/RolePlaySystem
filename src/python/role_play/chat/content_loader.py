"""Content loader for static roleplay scenarios and characters."""
from typing import List, Dict, Optional
import json
import sys

# Handle resource loading for Python 3.9+ and older versions
if sys.version_info >= (3, 9):
    from importlib import resources
else:
    import importlib_resources as resources


class ContentLoader:
    """Load roleplay scenarios and characters from packaged resources."""
    
    def __init__(self, resource_name: str = "scenarios.json", supported_languages: Optional[List[str]] = None):
        """Initialize content loader with resource name.
        
        Args:
            resource_name: Name of the JSON resource file
        """
        self.resource_name = resource_name

        self.supported_languages = supported_languages or ["en"]
        self._data = None
    
    def load_data(self) -> Dict:
        """Load data from packaged resource, caching the result.
        
        Returns:
            Dictionary containing scenarios and characters
            
        Raises:
            FileNotFoundError: If resource doesn't exist
            JSONDecodeError: If resource contains invalid JSON
            ValueError: If scenarios or characters contain unsupported languages

        """
        if self._data is None:
            # Load resource from the package
            try:
                # For Python 3.9+
                if sys.version_info >= (3, 9):
                    files = resources.files('role_play.resources')
                    resource = files / self.resource_name
                    with resource.open('r', encoding='utf-8') as f:
                        self._data = json.load(f)
                else:
                    # For older Python versions (using importlib_resources backport)
                    with resources.open_text('role_play.resources', self.resource_name) as f:
                        self._data = json.load(f)
            except Exception as e:
                raise FileNotFoundError(f"Could not load resource '{self.resource_name}': {e}")
        
            self._validate_languages()

        return self._data
    
    def _validate_languages(self) -> None:
        """Validate that all scenarios and characters use supported languages.
        
        Raises:
            ValueError: If any scenario or character has unsupported language
        """
        # Validate scenarios
        for scenario in self._data.get("scenarios", []):
            scenario_lang = scenario.get("language", "en")
            if scenario_lang not in self.supported_languages:
                raise ValueError(
                    f"Scenario '{scenario.get('id', 'unknown')}' has unsupported language '{scenario_lang}'. "
                    f"Supported languages: {self.supported_languages}"
                )
        
        # Validate characters
        for character in self._data.get("characters", []):
            character_lang = character.get("language", "en")
            if character_lang not in self.supported_languages:
                raise ValueError(
                    f"Character '{character.get('id', 'unknown')}' has unsupported language '{character_lang}'. "
                    f"Supported languages: {self.supported_languages}"
                )
    
    def get_scenarios(self) -> List[Dict]:
        """Get all available scenarios.
        
        Returns:
            List of scenario dictionaries
        """
        return self.load_data()["scenarios"]
    
    def get_characters(self) -> List[Dict]:
        """Get all available characters.
        
        Returns:
            List of character dictionaries
        """
        return self.load_data()["characters"]
    
    def get_scenario_by_id(self, scenario_id: str) -> Optional[Dict]:
        """Get a specific scenario by ID.
        
        Args:
            scenario_id: The scenario ID to look up
            
        Returns:
            Scenario dictionary or None if not found
        """
        return next((s for s in self.get_scenarios() if s["id"] == scenario_id), None)
    
    def get_character_by_id(self, character_id: str) -> Optional[Dict]:
        """Get a specific character by ID.
        
        Args:
            character_id: The character ID to look up
            
        Returns:
            Character dictionary or None if not found
        """
        return next((c for c in self.get_characters() if c["id"] == character_id), None)
    
    def get_scenario_characters(self, scenario_id: str) -> List[Dict]:
        """Get all characters compatible with a scenario.
        
        Args:
            scenario_id: The scenario ID
            
        Returns:
            List of compatible character dictionaries
        """
        scenario = self.get_scenario_by_id(scenario_id)
        if not scenario:
            return []
        
        compatible_chars = scenario.get("compatible_characters", [])
        return [c for c in self.get_characters() if c["id"] in compatible_chars]
    
    def get_scenarios_by_language(self, language: str = "en") -> List[Dict]:
        """Get all scenarios for a specific language.
        
        Args:
            language: Language code to filter by
            
        Returns:
            List of scenario dictionaries for the specified language
        """
        return [s for s in self.get_scenarios() if s.get("language", "en") == language]
    
    def get_characters_by_language(self, language: str = "en") -> List[Dict]:
        """Get all characters for a specific language.
        
        Args:
            language: Language code to filter by
            
        Returns:
            List of character dictionaries for the specified language
        """
        return [c for c in self.get_characters() if c.get("language", "en") == language]
    
    def get_scenario_characters_by_language(self, scenario_id: str, language: str = "en") -> List[Dict]:
        """Get all characters compatible with a scenario in a specific language.
        
        Args:
            scenario_id: The scenario ID
            language: Language code to filter by
            
        Returns:
            List of compatible character dictionaries for the specified language
        """
        scenario = self.get_scenario_by_id(scenario_id)
        if not scenario:
            return []
        
        compatible_chars = scenario.get("compatible_characters", [])
        return [c for c in self.get_characters_by_language(language) if c["id"] in compatible_chars]