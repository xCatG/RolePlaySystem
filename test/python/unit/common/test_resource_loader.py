import json
import pytest
from unittest.mock import AsyncMock

from role_play.common.resource_loader import ResourceLoader

@pytest.fixture
def mock_storage():
    """Fixture for a mocked StorageBackend."""
    storage = AsyncMock()
    # Default mock for list_keys to avoid errors in tests that don't specify it
    storage.list_keys.return_value = []
    return storage

@pytest.mark.asyncio
async def test_get_scenarios_english(mock_storage):
    """Test loading English scenarios by discovering them via list_keys."""
    mock_storage.list_keys.return_value = [
        "resources/scenarios/scenarios.json",
        "resources/scenarios/scenarios_zh-TW.json"
    ]
    mock_storage.read.return_value = '{"scenarios": [{"id": "en_s1", "name": "English Scenario"}]}'
    
    loader = ResourceLoader(mock_storage, base_prefix="resources/")
    scenarios = await loader.get_scenarios(language="en")

    mock_storage.list_keys.assert_called_once_with("resources/scenarios")
    mock_storage.read.assert_called_once_with("resources/scenarios/scenarios.json")
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "English Scenario"

@pytest.mark.asyncio
async def test_get_scenarios_chinese(mock_storage):
    """Test loading Chinese scenarios by discovering them."""
    mock_storage.list_keys.return_value = [
        "resources/scenarios/scenarios.json",
        "resources/scenarios/scenarios_zh-TW.json"
    ]
    mock_storage.read.return_value = '{"scenarios": [{"id": "zh_s1", "name": "Chinese Scenario"}]}'
    
    loader = ResourceLoader(mock_storage, base_prefix="resources/")
    scenarios = await loader.get_scenarios(language="zh-TW")

    mock_storage.list_keys.assert_called_once_with("resources/scenarios")
    mock_storage.read.assert_called_once_with("resources/scenarios/scenarios_zh-TW.json")
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Chinese Scenario"

@pytest.mark.asyncio
async def test_caching_logic(mock_storage):
    """Test that file content is cached after the first load."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '{"scenarios": [{"id": "s1"}]}'
    
    loader = ResourceLoader(mock_storage, base_prefix="resources/")

    # First call - should call storage.read
    await loader.get_scenarios(language="en")
    # Second call - should use cache and not call read again
    await loader.get_scenarios(language="en")

    # list_keys is still called to find the path, but read is not.
    assert mock_storage.list_keys.call_count == 2
    mock_storage.read.assert_called_once()

@pytest.mark.asyncio
async def test_cache_invalidation(mock_storage):
    """Test that cache invalidation forces a reload."""
    path = "resources/scenarios/scenarios.json"
    mock_storage.list_keys.return_value = [path]
    mock_storage.read.side_effect = [
        '{"scenarios": [{"id": "s1", "version": 1}]}',
        '{"scenarios": [{"id": "s1", "version": 2}]}'
    ]
    
    loader = ResourceLoader(mock_storage, base_prefix="resources/")

    # First call
    scenarios_v1 = await loader.get_scenarios(language="en")
    assert scenarios_v1[0]["version"] == 1

    # Invalidate cache for the specific path
    loader.invalidate_cache(path)

    # Second call after invalidation
    scenarios_v2 = await loader.get_scenarios(language="en")
    assert scenarios_v2[0]["version"] == 2

    assert mock_storage.read.call_count == 2

@pytest.mark.asyncio
async def test_get_scenario_by_id(mock_storage):
    """Test retrieving a single scenario by its ID."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '''
    {"scenarios": [
        {"id": "s1", "name": "Scenario 1"},
        {"id": "s2", "name": "Scenario 2"}
    ]}
    '''
    
    loader = ResourceLoader(mock_storage, base_prefix="resources/")
    scenario = await loader.get_scenario_by_id("s2", language="en")

    assert scenario is not None
    assert scenario["name"] == "Scenario 2"

@pytest.mark.asyncio
async def test_get_character_by_id_not_found(mock_storage):
    """Test that get_character_by_id returns None if not found."""
    mock_storage.list_keys.return_value = ["resources/characters/characters.json"]
    mock_storage.read.return_value = '{"characters": [{"id": "c1"}]}'
    
    loader = ResourceLoader(mock_storage, base_prefix="resources/")
    character = await loader.get_character_by_id("c99", language="en")

    assert character is None


# Error Handling Tests
@pytest.mark.asyncio
async def test_storage_read_failure(mock_storage):
    """Test handling when storage.read() raises an exception."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.side_effect = Exception("Storage read failed")
    
    loader = ResourceLoader(mock_storage)
    
    with pytest.raises(Exception) as exc_info:
        await loader.get_scenarios()
    assert "Storage read failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_malformed_json(mock_storage):
    """Test handling when storage returns invalid JSON."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '{"scenarios": [invalid json'
    
    loader = ResourceLoader(mock_storage)
    
    with pytest.raises(json.JSONDecodeError):
        await loader.get_scenarios()


@pytest.mark.asyncio
async def test_storage_list_keys_failure(mock_storage):
    """Test handling when storage.list_keys() raises an exception."""
    mock_storage.list_keys.side_effect = Exception("Storage list failed")
    
    loader = ResourceLoader(mock_storage)
    
    with pytest.raises(Exception) as exc_info:
        await loader.get_scenarios()
    assert "Storage list failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_missing_resource_key(mock_storage):
    """Test handling when JSON doesn't contain expected resource key."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    # Missing "scenarios" key
    mock_storage.read.return_value = '{"version": "1.0", "data": []}'
    
    loader = ResourceLoader(mock_storage)
    scenarios = await loader.get_scenarios()
    
    assert scenarios == []  # Should return empty list when key is missing


# Edge Cases
@pytest.mark.asyncio
async def test_empty_resource_list(mock_storage):
    """Test handling empty resource lists."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '{"scenarios": []}'
    
    loader = ResourceLoader(mock_storage)
    scenarios = await loader.get_scenarios()
    
    assert scenarios == []
    assert len(scenarios) == 0


@pytest.mark.asyncio
async def test_no_language_specific_file_fallback(mock_storage):
    """Test fallback to default file when language-specific file not found."""
    # Only default file exists, no ja.json
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '{"scenarios": [{"id": "default", "name": "Default Scenario"}]}'
    
    loader = ResourceLoader(mock_storage)
    # Request Japanese, should fallback to default
    scenarios = await loader.get_scenarios(language="ja")
    
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Default Scenario"


@pytest.mark.asyncio
async def test_no_files_found(mock_storage):
    """Test when no resource files exist."""
    mock_storage.list_keys.return_value = []
    
    loader = ResourceLoader(mock_storage)
    scenarios = await loader.get_scenarios()
    
    assert scenarios == []
    # Should not call read when no files found
    mock_storage.read.assert_not_called()


# Cache Tests
@pytest.mark.asyncio
async def test_invalidate_all_cache(mock_storage):
    """Test invalidating entire cache."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '{"scenarios": [{"id": "s1"}]}'
    
    loader = ResourceLoader(mock_storage)
    
    # Load to populate cache
    await loader.get_scenarios()
    assert mock_storage.read.call_count == 1
    
    # Invalidate entire cache
    loader.invalidate_cache()
    
    # Should read again after cache cleared
    await loader.get_scenarios()
    assert mock_storage.read.call_count == 2


@pytest.mark.asyncio
async def test_invalidate_nonexistent_path(mock_storage):
    """Test invalidating a path that's not in cache."""
    loader = ResourceLoader(mock_storage)
    
    # Should not raise error
    loader.invalidate_cache("nonexistent/path.json")


# Character Loading Tests
@pytest.mark.asyncio
async def test_get_characters_success(mock_storage):
    """Test successful character loading."""
    mock_storage.list_keys.return_value = ["resources/characters/characters.json"]
    mock_storage.read.return_value = '''
    {"characters": [
        {"id": "c1", "name": "Character 1"},
        {"id": "c2", "name": "Character 2"}
    ]}
    '''
    
    loader = ResourceLoader(mock_storage)
    characters = await loader.get_characters()
    
    assert len(characters) == 2
    assert characters[0]["name"] == "Character 1"
    assert characters[1]["name"] == "Character 2"


@pytest.mark.asyncio
async def test_get_characters_language_specific(mock_storage):
    """Test loading language-specific characters."""
    mock_storage.list_keys.return_value = [
        "resources/characters/characters.json",
        "resources/characters/characters_fr.json"
    ]
    mock_storage.read.return_value = '{"characters": [{"id": "c1", "name": "Personnage 1"}]}'
    
    loader = ResourceLoader(mock_storage)
    characters = await loader.get_characters(language="fr")
    
    mock_storage.read.assert_called_once_with("resources/characters/characters_fr.json")
    assert characters[0]["name"] == "Personnage 1"


@pytest.mark.asyncio
async def test_get_character_by_id_found(mock_storage):
    """Test finding an existing character by ID."""
    mock_storage.list_keys.return_value = ["resources/characters/characters.json"]
    mock_storage.read.return_value = '''
    {"characters": [
        {"id": "hero", "name": "The Hero"},
        {"id": "villain", "name": "The Villain"}
    ]}
    '''
    
    loader = ResourceLoader(mock_storage)
    character = await loader.get_character_by_id("villain")
    
    assert character is not None
    assert character["name"] == "The Villain"


# Resource Path Discovery Tests
@pytest.mark.asyncio
async def test_custom_base_prefix(mock_storage):
    """Test ResourceLoader with custom base prefix."""
    custom_prefix = "custom/path/"
    mock_storage.list_keys.return_value = ["custom/path/scenarios/scenarios.json"]
    mock_storage.read.return_value = '{"scenarios": [{"id": "s1"}]}'
    
    loader = ResourceLoader(mock_storage, base_prefix=custom_prefix)
    scenarios = await loader.get_scenarios()
    
    mock_storage.list_keys.assert_called_once_with("custom/path/scenarios")
    assert len(scenarios) == 1


# Integration-like Tests
@pytest.mark.asyncio
async def test_full_workflow(mock_storage):
    """Test loading multiple resource types with caching."""
    # Setup mock responses
    def side_effect(prefix):
        if "scenarios" in prefix:
            return ["resources/scenarios/scenarios.json"]
        elif "characters" in prefix:
            return ["resources/characters/characters.json"]
        return []
    
    mock_storage.list_keys.side_effect = side_effect
    mock_storage.read.side_effect = [
        '{"scenarios": [{"id": "s1", "compatible_characters": ["c1"]}]}',
        '{"characters": [{"id": "c1", "name": "Character 1"}]}'
    ]
    
    loader = ResourceLoader(mock_storage)
    
    # Load scenarios
    scenarios = await loader.get_scenarios()
    assert len(scenarios) == 1
    
    # Load characters
    characters = await loader.get_characters()
    assert len(characters) == 1
    
    # Verify compatible character exists
    scenario = scenarios[0]
    compatible_char_id = scenario["compatible_characters"][0]
    character = await loader.get_character_by_id(compatible_char_id)
    assert character is not None
    assert character["name"] == "Character 1"


@pytest.mark.asyncio
async def test_language_switching(mock_storage):
    """Test loading resources in different languages."""
    mock_storage.list_keys.return_value = [
        "resources/scenarios/scenarios.json",
        "resources/scenarios/scenarios_zh-TW.json"
    ]
    
    # Different content for each language
    mock_storage.read.side_effect = [
        '{"scenarios": [{"id": "en_s1", "name": "English Scenario"}]}',
        '{"scenarios": [{"id": "zh_s1", "name": "中文場景"}]}'
    ]
    
    loader = ResourceLoader(mock_storage)
    
    # Load English
    en_scenarios = await loader.get_scenarios("en")
    assert en_scenarios[0]["name"] == "English Scenario"
    
    # Load Chinese (should use cached list_keys result)
    zh_scenarios = await loader.get_scenarios("zh-TW")
    assert zh_scenarios[0]["name"] == "中文場景"
    
    assert mock_storage.read.call_count == 2
    assert mock_storage.list_keys.call_count == 2  # Called for each language


# Version Validation Tests
@pytest.mark.asyncio
async def test_valid_resource_version(mock_storage):
    """Test loading resource with valid version."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '''
    {
        "resource_version": "1.0",
        "last_modified": "2025-07-29T01:00:00Z",
        "scenarios": [{"id": "s1", "name": "Scenario 1"}]
    }
    '''
    
    loader = ResourceLoader(mock_storage)
    scenarios = await loader.get_scenarios()
    
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Scenario 1"


@pytest.mark.asyncio
async def test_unsupported_resource_version(mock_storage):
    """Test error when resource has unsupported version."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '''
    {
        "resource_version": "2.0",
        "scenarios": [{"id": "s1"}]
    }
    '''
    
    loader = ResourceLoader(mock_storage)
    
    with pytest.raises(ValueError) as exc_info:
        await loader.get_scenarios()
    
    assert "Unsupported resource version 2.0" in str(exc_info.value)
    assert "Supported versions: 1.0" in str(exc_info.value)


@pytest.mark.asyncio
async def test_legacy_resource_without_version(mock_storage):
    """Test warning but successful load for legacy resources without version."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    # No resource_version field
    mock_storage.read.return_value = '''
    {
        "scenarios": [{"id": "legacy", "name": "Legacy Scenario"}]
    }
    '''
    
    loader = ResourceLoader(mock_storage)
    
    # Should load successfully with warning
    scenarios = await loader.get_scenarios()
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Legacy Scenario"


@pytest.mark.asyncio
async def test_version_validation_caching(mock_storage):
    """Test that version validation happens before caching."""
    mock_storage.list_keys.return_value = ["resources/scenarios/scenarios.json"]
    mock_storage.read.return_value = '''
    {
        "resource_version": "99.0",
        "scenarios": []
    }
    '''
    
    loader = ResourceLoader(mock_storage)
    
    # First load should fail
    with pytest.raises(ValueError):
        await loader.get_scenarios()
    
    # Second attempt should also fail (not cached)
    with pytest.raises(ValueError):
        await loader.get_scenarios()
    
    # Verify read was called twice (no caching of invalid version)
    assert mock_storage.read.call_count == 2


@pytest.mark.asyncio
async def test_multiple_supported_versions():
    """Test that ResourceLoader can support multiple versions."""
    # This test verifies the class constant
    assert "1.0" in ResourceLoader.SUPPORTED_VERSIONS
    # In future, we might have:
    # assert "1.1" in ResourceLoader.SUPPORTED_VERSIONS
