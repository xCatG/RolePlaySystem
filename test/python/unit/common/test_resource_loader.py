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
