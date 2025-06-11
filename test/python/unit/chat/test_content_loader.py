"""Test resource loading functionality."""
import pytest
from role_play.chat.content_loader import ContentLoader


def test_content_loader_loads_scenarios():
    """Test that ContentLoader can load scenarios from packaged resources."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
    # Test loading scenarios
    scenarios = loader.get_scenarios()
    assert isinstance(scenarios, list)
    assert len(scenarios) > 0
    assert all('id' in s for s in scenarios)
    assert all('name' in s for s in scenarios)  # Fixed: changed from 'title' to 'name'


def test_content_loader_loads_characters():
    """Test that ContentLoader can load characters from packaged resources."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
    # Test loading characters
    characters = loader.get_characters()
    assert isinstance(characters, list)
    assert len(characters) > 0
    assert all('id' in c for c in characters)
    assert all('name' in c for c in characters)


def test_content_loader_get_by_id():
    """Test getting specific scenarios and characters by ID."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
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
    data1 = loader.load_data("en")
    # Second load should return cached data
    data2 = loader.load_data("en")
    
    # Should be the same object (cached)
    assert data1 is data2


def test_get_scenario_characters():
    """Test getting compatible characters for a scenario."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
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
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
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
    loader = ContentLoader(supported_languages=["en", "zh-TW", "ja"])
    assert loader.supported_languages == ["en", "zh-TW", "ja"]
    
    # Test default language support
    loader_default = ContentLoader()
    assert loader_default.supported_languages == ["en"]


def test_get_scenarios_by_language():
    """Test filtering scenarios by language."""
    loader = ContentLoader(supported_languages=["en", "zh-TW", "ja"])
    
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
    loader = ContentLoader(supported_languages=["en", "zh-TW", "ja"])
    
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
    loader = ContentLoader(supported_languages=["en", "zh-TW", "ja"])
    
    try:
        # Should not raise if all languages are supported
        data = loader.load_data("en")
        assert "scenarios" in data
        assert "characters" in data
    except FileNotFoundError:
        # Skip if resources not available in test environment
        pytest.skip("Resource file not available")
    except ValueError as e:
        # If this fails, it means the scenarios.json has unsupported languages
        pytest.fail(f"Language validation failed: {e}")


def test_load_language_specific_content():
    """Test loading language-specific content files."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
    try:
        # Test English content
        en_data = loader.load_data("en")
        assert isinstance(en_data.get("scenarios", []), list)
        assert isinstance(en_data.get("characters", []), list)
        
        # Test Chinese content (should load scenarios_zh-TW.json if available)
        zh_data = loader.load_data("zh-TW")
        assert isinstance(zh_data.get("scenarios", []), list)
        assert isinstance(zh_data.get("characters", []), list)
        
        # Verify language filtering works
        for scenario in zh_data["scenarios"]:
            assert scenario.get("language", "en") == "zh-TW"
        for character in zh_data["characters"]:
            assert character.get("language", "en") == "zh-TW"
            
    except FileNotFoundError:
        pytest.skip("Resource files not available")


def test_get_content_by_language():
    """Test getting scenarios and characters by specific language."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
    try:
        # Test English scenarios and characters
        en_scenarios = loader.get_scenarios("en")
        en_characters = loader.get_characters("en")
        
        assert isinstance(en_scenarios, list)
        assert isinstance(en_characters, list)
        
        # Test Chinese scenarios and characters
        zh_scenarios = loader.get_scenarios("zh-TW")
        zh_characters = loader.get_characters("zh-TW")
        
        assert isinstance(zh_scenarios, list)
        assert isinstance(zh_characters, list)
        
        # Verify language consistency
        for scenario in zh_scenarios:
            assert scenario.get("language", "en") == "zh-TW"
        for character in zh_characters:
            assert character.get("language", "en") == "zh-TW"
            
    except FileNotFoundError:
        pytest.skip("Resource files not available")


def test_scenario_character_compatibility_by_language():
    """Test scenario-character compatibility within same language."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
    try:
        for language in ["en", "zh-TW"]:
            scenarios = loader.get_scenarios(language)
            if scenarios:
                scenario = scenarios[0]
                compatible_chars = loader.get_scenario_characters(scenario["id"], language)
                
                # All compatible characters should be in the same language
                for char in compatible_chars:
                    assert char.get("language", "en") == language
                    
    except FileNotFoundError:
        pytest.skip("Resource files not available")


def test_content_loader_cache_by_language():
    """Test that content is cached separately by language."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    
    try:
        # Load English content twice
        en_data1 = loader.load_data("en")
        en_data2 = loader.load_data("en")
        assert en_data1 is en_data2  # Should be cached
        
        # Load Chinese content
        zh_data = loader.load_data("zh-TW")
        assert zh_data is not en_data1  # Should be different cache entry
        
        # Load Chinese content again
        zh_data2 = loader.load_data("zh-TW")
        assert zh_data is zh_data2  # Should be cached
        
    except FileNotFoundError:
        pytest.skip("Resource files not available")


def test_unsupported_language_validation():
    """Test that unsupported languages raise appropriate errors."""
    loader = ContentLoader(supported_languages=["en"])  # Only English supported
    
    # Since we have Chinese content files in the test environment,
    # loading "zh-TW" should raise ValueError due to language validation
    try:
        with pytest.raises(ValueError) as exc_info:
            loader.load_data("zh-TW")
        assert "unsupported language" in str(exc_info.value)
    except FileNotFoundError:
        pytest.skip("Resource files not available")


def test_get_by_id_any_language():
    """Ensure get_scenario_by_id_any_language and get_character_by_id_any_language work."""
    loader = ContentLoader(supported_languages=["en", "zh-TW"])

    scenario = loader.get_scenario_by_id_any_language("customer_service")
    assert scenario is not None
    assert scenario["id"] == "customer_service"
    assert scenario.get("language") == "en"

    character = loader.get_character_by_id_any_language("angry_customer")
    assert character is not None
    assert character["id"] == "angry_customer"
    assert character.get("language") == "en"
