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


def test_get_scenario_characters():
    """Test getting compatible characters for a scenario."""
    loader = ContentLoader()
    
    # Get first scenario with compatible_characters
    scenarios = loader.get_scenarios()
    for scenario in scenarios:
        if 'compatible_characters' in scenario and scenario['compatible_characters']:
            characters = loader.get_scenario_characters(scenario['id'])
            assert isinstance(characters, list)
            # All returned characters should be in the compatible list
            char_ids = [c['id'] for c in characters]
            for char_id in char_ids:
                assert char_id in scenario['compatible_characters']
            break


def test_nonexistent_ids():
    """Test behavior when requesting non-existent IDs."""
    loader = ContentLoader()
    
    # Non-existent scenario
    scenario = loader.get_scenario_by_id('nonexistent_scenario_id')
    assert scenario is None
    
    # Non-existent character
    character = loader.get_character_by_id('nonexistent_character_id')
    assert character is None
    
    # Characters for non-existent scenario
    characters = loader.get_scenario_characters('nonexistent_scenario_id')
    assert characters == []


# Language support tests
def test_language_support_initialization():
    """Test ContentLoader initialization with supported languages."""
    loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
    assert loader.supported_languages == ["en", "zh-tw", "ja"]
    
    # Test default language support
    loader_default = ContentLoader()
    assert loader_default.supported_languages == ["en"]


def test_get_scenarios_by_language():
    """Test filtering scenarios by language."""
    loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
    
    # Test getting scenarios by language
    # This assumes the actual scenarios.json has language fields
    try:
        en_scenarios = loader.get_scenarios_by_language("en")
        assert isinstance(en_scenarios, list)
        # All returned scenarios should have language "en" or no language (defaults to "en")
        for scenario in en_scenarios:
            assert scenario.get("language", "en") == "en"
    except FileNotFoundError:
        # Skip if resources not available in test environment
        pytest.skip("Resource file not available")


def test_get_characters_by_language():
    """Test filtering characters by language."""
    loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
    
    # Test getting characters by language
    try:
        en_characters = loader.get_characters_by_language("en")
        assert isinstance(en_characters, list)
        # All returned characters should have language "en" or no language (defaults to "en")
        for character in en_characters:
            assert character.get("language", "en") == "en"
    except FileNotFoundError:
        # Skip if resources not available in test environment
        pytest.skip("Resource file not available")


def test_language_validation_with_supported_languages():
    """Test that ContentLoader validates languages when configured."""
    # This test will pass if all scenarios/characters in the actual resource file
    # have supported languages or default to "en"
    loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
    
    try:
        # Should not raise if all languages are supported
        data = loader.load_data()
        assert "scenarios" in data
        assert "characters" in data
    except FileNotFoundError:
        # Skip if resources not available in test environment
        pytest.skip("Resource file not available")
    except ValueError as e:
        # If this fails, it means the scenarios.json has unsupported languages
        pytest.fail(f"Language validation failed: {e}")