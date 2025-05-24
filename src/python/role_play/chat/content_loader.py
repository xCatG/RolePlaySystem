"""Content loader for static roleplay scenarios and characters."""
from typing import List, Dict, Optional
import json
from pathlib import Path

class ContentLoader:
    """Load roleplay scenarios and characters from static JSON file."""
    
    def __init__(self, data_file: str = "data/scenarios.json"):
        """Initialize content loader with data file path.
        
        Args:
            data_file: Path to the JSON file containing scenarios and characters
        """
        self.data_file = Path(data_file)
        self._data = None
    
    def load_data(self) -> Dict:
        """Load data from JSON file, caching the result.
        
        Returns:
            Dictionary containing scenarios and characters
            
        Raises:
            FileNotFoundError: If data file doesn't exist
            JSONDecodeError: If data file contains invalid JSON
        """
        if self._data is None:
            with open(self.data_file) as f:
                self._data = json.load(f)
        return self._data
    
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