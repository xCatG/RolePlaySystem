"""Integration tests for the ResourceLoader against a mocked storage backend."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from role_play.common.resource_loader import ResourceLoader

@pytest.fixture
def mock_storage():
    """Fixture for a mocked StorageBackend that simulates a GCS-like structure."""
    storage = AsyncMock()
    
    # Simulate a file system in GCS
    mock_fs = {
        "resources/scenarios/scenarios.json": '{"resource_version": "1.0", "scenarios": [{"id": "en_s1", "name": "English Scenario"}]}',
        "resources/scenarios/scenarios_zh-TW.json": '{"resource_version": "1.0", "scenarios": [{"id": "zh_s1", "name": "Chinese Scenario"}]}',
        "resources/characters/characters.json": '{"resource_version": "1.0", "characters": [{"id": "en_c1", "name": "English Character"}]}',
        "resources/characters/characters_zh-TW.json": '{"resource_version": "1.0", "characters": [{"id": "zh_c1", "name": "Chinese Character"}]}',
    }

    async def mock_list_keys(prefix: str):
        # GCS list_keys returns full paths
        return [key for key in mock_fs if key.startswith(prefix)]

    async def mock_read(path: str):
        if path in mock_fs:
            return mock_fs[path]
        raise FileNotFoundError(f"Path not found: {path}")

    storage.list_keys.side_effect = mock_list_keys
    storage.read.side_effect = mock_read
    
    return storage

@pytest.mark.asyncio
async def test_loading_scenarios_and_characters(mock_storage):
    """Test loading both scenarios and characters for multiple languages."""
    loader = ResourceLoader(mock_storage, base_prefix="resources/")
    
    # Test English resources
    en_scenarios = await loader.get_scenarios("en")
    en_characters = await loader.get_characters("en")
    
    assert len(en_scenarios) == 1
    assert en_scenarios[0]["name"] == "English Scenario"
    assert len(en_characters) == 1
    assert en_characters[0]["name"] == "English Character"

    # Test Chinese resources
    zh_scenarios = await loader.get_scenarios("zh-TW")
    zh_characters = await loader.get_characters("zh-TW")

    assert len(zh_scenarios) == 1
    assert zh_scenarios[0]["name"] == "Chinese Scenario"
    assert len(zh_characters) == 1
    assert zh_characters[0]["name"] == "Chinese Character"

@pytest.mark.asyncio
async def test_fallback_to_default_language(mock_storage):
    """Test that it falls back to the default (e.g., 'en') file if a language-specific one is not found."""
    loader = ResourceLoader(mock_storage, base_prefix="resources/")
    
    # Request Japanese, which doesn't exist, should fall back to English
    ja_scenarios = await loader.get_scenarios("ja")
    
    assert len(ja_scenarios) == 1
    assert ja_scenarios[0]["name"] == "English Scenario"

@pytest.mark.asyncio
async def test_caching_behavior(mock_storage):
    """Test that repeated calls use the cache and invalidation works."""
    loader = ResourceLoader(mock_storage, base_prefix="resources/")
    
    # First call, should trigger read
    await loader.get_scenarios("en")
    assert mock_storage.read.call_count == 1
    
    # Second call, should be cached
    await loader.get_scenarios("en")
    assert mock_storage.read.call_count == 1
    
    # Invalidate cache and try again
    loader.invalidate_cache()
    await loader.get_scenarios("en")
    assert mock_storage.read.call_count == 2

@pytest.mark.asyncio
async def test_retrieving_specific_items_by_id(mock_storage):
    """Test get_scenario_by_id and get_character_by_id."""
    loader = ResourceLoader(mock_storage, base_prefix="resources/")
    
    # Get specific English scenario
    scenario = await loader.get_scenario_by_id("en_s1", "en")
    assert scenario is not None
    assert scenario["name"] == "English Scenario"
    
    # Get specific Chinese character
    character = await loader.get_character_by_id("zh_c1", "zh-TW")
    assert character is not None
    assert character["name"] == "Chinese Character"
    
    # Get non-existent item
    non_existent = await loader.get_scenario_by_id("non_existent", "en")
    assert non_existent is None
