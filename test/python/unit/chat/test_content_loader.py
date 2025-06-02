"""Test resource loading functionality."""
import pytest
from role_play.chat.content_loader import ContentLoader


def test_content_loader_loads_scenarios():
    """Test that ContentLoader can load scenarios from packaged resources."""
    loader = ContentLoader()
    
    # Test loading scenarios
    scenarios = loader.get_scenarios()
    assert isinstance(scenarios, list)
    assert len(scenarios) > 0
    assert all('id' in s for s in scenarios)
    assert all('title' in s for s in scenarios)


def test_content_loader_loads_characters():
    """Test that ContentLoader can load characters from packaged resources."""
    loader = ContentLoader()
    
    # Test loading characters
    characters = loader.get_characters()
    assert isinstance(characters, list)
    assert len(characters) > 0
    assert all('id' in c for c in characters)
    assert all('name' in c for c in characters)


def test_content_loader_get_by_id():
    """Test getting specific scenarios and characters by ID."""
    loader = ContentLoader()
    
    # Get first scenario and character for testing
    scenarios = loader.get_scenarios()
    characters = loader.get_characters()
    
    if scenarios:
        scenario = loader.get_scenario_by_id(scenarios[0]['id'])
        assert scenario is not None
        assert scenario['id'] == scenarios[0]['id']
    
    if characters:
        character = loader.get_character_by_id(characters[0]['id'])
        assert character is not None
        assert character['id'] == characters[0]['id']


def test_content_loader_caching():
    """Test that content is cached after first load."""
    loader = ContentLoader()
    
    # First load
    data1 = loader.load_data()
    # Second load should return cached data
    data2 = loader.load_data()
    
    # Should be the same object (cached)
    assert data1 is data2