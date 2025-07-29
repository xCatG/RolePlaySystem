#!/usr/bin/env python3
"""
Script to validate resource loading from different storage backends.
Usage: python scripts/test_resource_loading.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "python"))

from role_play.common.storage_factory import create_storage_backend
from role_play.common.resource_loader import ResourceLoader
from role_play.common.models import Environment
from role_play.common.storage import FileStorageConfig, GCSStorageConfig


async def test_resource_loading():
    """Test loading resources from configured storage backend."""
    
    # Get storage configuration from environment
    storage_type = os.environ.get("STORAGE_TYPE", "file")
    print(f"\n=== Testing Resource Loading ===")
    print(f"Storage Type: {storage_type}")
    
    # Configure storage based on type
    if storage_type == "gcs":
        bucket = os.environ.get("GCS_BUCKET")
        project_id = os.environ.get("GCP_PROJECT_ID")
        if not bucket:
            print("ERROR: GCS_BUCKET environment variable required for GCS storage")
            return False
        
        config = GCSStorageConfig(
            bucket=bucket,
            prefix=os.environ.get("GCS_PREFIX", ""),
            project_id=project_id
        )
        print(f"GCS Bucket: {bucket}")
        print(f"GCS Prefix: {config.prefix or '(root)'}")
    else:
        # File storage
        base_dir = os.environ.get("STORAGE_PATH", "./data")
        config = FileStorageConfig(
            base_dir=base_dir
        )
        print(f"File Storage Path: {base_dir}")
    
    # Create storage backend and resource loader
    try:
        environment = Environment.DEV  # Use dev for testing
        storage = create_storage_backend(config, environment)
        loader = ResourceLoader(storage, base_prefix="resources/")
        print("✓ Storage backend created successfully")
    except Exception as e:
        print(f"✗ Failed to create storage backend: {e}")
        return False
    
    # Test listing resource files
    print("\n--- Checking Available Resource Files ---")
    try:
        scenario_files = await storage.list_keys("resources/scenarios")
        print(f"Found {len(scenario_files)} scenario files:")
        for f in scenario_files:
            print(f"  - {f}")
            
        character_files = await storage.list_keys("resources/characters")
        print(f"\nFound {len(character_files)} character files:")
        for f in character_files:
            print(f"  - {f}")
    except Exception as e:
        print(f"✗ Failed to list resource files: {e}")
        return False
    
    # Test loading scenarios for each language
    print("\n--- Testing Scenario Loading ---")
    languages = ["en", "zh-TW", "ja"]
    all_success = True
    
    for lang in languages:
        try:
            scenarios = await loader.get_scenarios(lang)
            if scenarios:
                print(f"✓ {lang}: Loaded {len(scenarios)} scenarios")
                # Show first scenario as example
                if scenarios:
                    first = scenarios[0]
                    print(f"    Example: {first.get('id')} - {first.get('name')}")
            else:
                print(f"⚠ {lang}: No scenarios found (might be expected)")
        except Exception as e:
            print(f"✗ {lang}: Failed to load scenarios - {e}")
            all_success = False
    
    # Test loading characters
    print("\n--- Testing Character Loading ---")
    for lang in languages:
        try:
            characters = await loader.get_characters(lang)
            if characters:
                print(f"✓ {lang}: Loaded {len(characters)} characters")
                # Show first character as example
                if characters:
                    first = characters[0]
                    print(f"    Example: {first.get('id')} - {first.get('name')}")
            else:
                print(f"⚠ {lang}: No characters found (might be expected)")
        except Exception as e:
            print(f"✗ {lang}: Failed to load characters - {e}")
            all_success = False
    
    # Test specific scenario retrieval
    print("\n--- Testing Specific Resource Retrieval ---")
    try:
        # Try to get a specific scenario
        scenario = await loader.get_scenario_by_id("medical_interview", "en")
        if scenario:
            print(f"✓ Found scenario 'medical_interview': {scenario.get('name')}")
        else:
            print("✗ Scenario 'medical_interview' not found")
            
        # Try to get a specific character
        character = await loader.get_character_by_id("patient_chronic", "en")
        if character:
            print(f"✓ Found character 'patient_chronic': {character.get('name')}")
        else:
            print("✗ Character 'patient_chronic' not found")
    except Exception as e:
        print(f"✗ Failed to retrieve specific resources: {e}")
        all_success = False
    
    # Test cache behavior
    print("\n--- Testing Cache Behavior ---")
    try:
        # Load scenarios twice and check if cached
        import time
        start = time.time()
        await loader.get_scenarios("en")
        first_load = time.time() - start
        
        start = time.time()
        await loader.get_scenarios("en")
        second_load = time.time() - start
        
        print(f"First load: {first_load:.3f}s")
        print(f"Second load (cached): {second_load:.3f}s")
        if second_load < first_load * 0.5:  # Cached should be much faster
            print("✓ Caching appears to be working")
        else:
            print("⚠ Cache may not be working effectively")
            
        # Test cache invalidation
        loader.invalidate_cache()
        print("✓ Cache invalidated successfully")
    except Exception as e:
        print(f"✗ Cache testing failed: {e}")
        all_success = False
    
    print("\n=== Summary ===")
    if all_success:
        print("✓ All tests passed!")
        return True
    else:
        print("✗ Some tests failed. Check the output above.")
        return False


async def main():
    """Main entry point."""
    success = await test_resource_loading()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())