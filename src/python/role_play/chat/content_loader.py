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
            supported_languages: List of supported language codes
        """
        self.resource_name = resource_name
        self.supported_languages = supported_languages or ["en"]
        self._data = {}  # Cache by language: {language: data_dict}
    
    def _load_resource(self, resource_name: str) -> Dict:
        """Load a specific resource file.
        
        Args:
            resource_name: Name of the JSON resource file
            
        Returns:
            Dictionary containing the parsed JSON data
            
        Raises:
            FileNotFoundError: If resource doesn't exist
            JSONDecodeError: If resource contains invalid JSON
        """
        try:
            # For Python 3.9+
            if sys.version_info >= (3, 9):
                files = resources.files('role_play.resources')
                resource = files / resource_name
                with resource.open('r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # For older Python versions (using importlib_resources backport)
                with resources.open_text('role_play.resources', resource_name) as f:
                    return json.load(f)
        except Exception as e:
            raise FileNotFoundError(f"Could not load resource '{resource_name}': {e}")
    
    def _filter_by_language(self, data: Dict, language: str) -> Dict:
        """Filter scenarios, characters and scripts by language from combined data.
        
        Args:
            data: Dictionary containing scenarios and characters
            language: Language code to filter by
            
        Returns:
            Dictionary with filtered scenarios, characters and scripts
        """
        filtered_scenarios = [
            s for s in data.get("scenarios", []) 
            if s.get("language", "en") == language
        ]
        filtered_characters = [
            c for c in data.get("characters", [])
            if c.get("language", "en") == language
        ]
        
        filtered_scripts = [
            s for s in data.get("scripts", [])
            if s.get("language", "en") == language
        ]

        return {
            "scenarios": filtered_scenarios,
            "characters": filtered_characters,
            "scripts": filtered_scripts,
        }
    
    def load_data(self, language: str = "en") -> Dict:
        """Load data for a specific language, caching the result.
        
        Args:
            language: Language code (defaults to "en")
            
        Returns:
            Dictionary containing scenarios, characters and scripts for the language
            
        Raises:
            FileNotFoundError: If resource doesn't exist
            JSONDecodeError: If resource contains invalid JSON
            ValueError: If scenarios or characters contain unsupported languages
        """
        if language not in self._data:
            # Try language-specific file first (e.g., scenarios_zh-TW.json)
            if language != "en":
                language_specific_file = f"scenarios_{language}.json"
                try:
                    raw_data = self._load_resource(language_specific_file)
                    self._data[language] = self._normalize_language_codes(raw_data)
                    self._validate_languages(self._data[language])
                    return self._data[language]
                except FileNotFoundError:
                    # Fall back to filtering main scenarios.json
                    pass
            
            # Load main scenarios.json if language-specific file doesn't exist
            # or if requesting English content
            if "main" not in self._data:
                raw_main_data = self._load_resource(self.resource_name)
                self._data["main"] = self._normalize_language_codes(raw_main_data)
            
            # Filter by language
            self._data[language] = self._filter_by_language(self._data["main"], language)
            self._validate_languages(self._data[language])
        
        return self._data[language]
    
    def _normalize_language_codes(self, data: Dict) -> Dict:
        """Normalize language codes for consistency.
        
        Args:
            data: Dictionary containing scenarios and characters
            
        Returns:
            Dictionary with normalized language codes
        """
        # Create a copy to avoid mutating the original data
        normalized_data = {"scenarios": [], "characters": [], "scripts": []}
        
        # Normalize scenarios
        for scenario in data.get("scenarios", []):
            scenario_copy = scenario.copy()
            scenario_lang = scenario_copy.get("language", "en")
            if scenario_lang == "zh_tw":
                scenario_copy["language"] = "zh-TW"
            normalized_data["scenarios"].append(scenario_copy)
        
        # Normalize characters
        for character in data.get("characters", []):
            character_copy = character.copy()
            character_lang = character_copy.get("language", "en")
            if character_lang == "zh_tw":
                character_copy["language"] = "zh-TW"
            normalized_data["characters"].append(character_copy)

        # Normalize scripts
        for script in data.get("scripts", []):
            script_copy = script.copy()
            script_lang = script_copy.get("language", "en")
            if script_lang == "zh_tw":
                script_copy["language"] = "zh-TW"
            normalized_data["scripts"].append(script_copy)
        
        return normalized_data
    
    def _validate_languages(self, data: Dict) -> None:
        """Validate that all scenarios and characters use supported languages.
        
        Raises:
            ValueError: If any scenario or character has unsupported language
        """
        # Validate scenarios
        for scenario in data.get("scenarios", []):
            scenario_lang = scenario.get("language", "en")
            if scenario_lang not in self.supported_languages:
                raise ValueError(
                    f"Scenario '{scenario.get('id', 'unknown')}' has unsupported language '{scenario_lang}'. "
                    f"Supported languages: {self.supported_languages}"
                )
        
        # Validate characters
        for character in data.get("characters", []):
            character_lang = character.get("language", "en")
            if character_lang not in self.supported_languages:
                raise ValueError(
                    f"Character '{character.get('id', 'unknown')}' has unsupported language '{character_lang}'. "
                    f"Supported languages: {self.supported_languages}"
                )

        # Validate scripts
        for script in data.get("scripts", []):
            script_lang = script.get("language", "en")
            if script_lang not in self.supported_languages:
                raise ValueError(
                    f"Script '{script.get('id', 'unknown')}' has unsupported language '{script_lang}'. "
                    f"Supported languages: {self.supported_languages}"
                )
    
    def get_scenarios(self, language: str = "en") -> List[Dict]:
        """Get all available scenarios for a specific language.
        
        Args:
            language: Language code (defaults to "en")
            
        Returns:
            List of scenario dictionaries
        """
        return self.load_data(language)["scenarios"]
    
    def get_characters(self, language: str = "en") -> List[Dict]:
        """Get all available characters for a specific language.
        
        Args:
            language: Language code (defaults to "en")
            
        Returns:
            List of character dictionaries
        """
        return self.load_data(language)["characters"]
    
    def get_scenario_by_id(self, scenario_id: str, language: str = "en") -> Optional[Dict]:
        """Get a specific scenario by ID for a specific language.
        
        Args:
            scenario_id: The scenario ID to look up
            language: Language code (defaults to "en")
            
        Returns:
            Scenario dictionary or None if not found
        """
        return next((s for s in self.get_scenarios(language) if s["id"] == scenario_id), None)
    
    def get_character_by_id(self, character_id: str, language: str = "en") -> Optional[Dict]:
        """Get a specific character by ID for a specific language.
        
        Args:
            character_id: The character ID to look up
            language: Language code (defaults to "en")
            
        Returns:
            Character dictionary or None if not found
        """
        return next((c for c in self.get_characters(language) if c["id"] == character_id), None)
    
    def get_scenario_characters(self, scenario_id: str, language: str = "en") -> List[Dict]:
        """Get all characters compatible with a scenario for a specific language.
        
        Args:
            scenario_id: The scenario ID
            language: Language code (defaults to "en")
            
        Returns:
            List of compatible character dictionaries
        """
        scenario = self.get_scenario_by_id(scenario_id, language)
        if not scenario:
            return []
        
        compatible_chars = scenario.get("compatible_characters", [])
        return [c for c in self.get_characters(language) if c["id"] in compatible_chars]

    def get_scripts(self, language: str = "en") -> List[Dict]:
        """Get all available scripts for a specific language."""
        return self.load_data(language).get("scripts", [])

    def get_script_by_id(self, script_id: str, language: str = "en") -> Optional[Dict]:
        """Get a specific script by ID for a specific language."""
        return next((s for s in self.get_scripts(language) if s["id"] == script_id), None)
    
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