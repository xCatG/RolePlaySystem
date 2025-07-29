#!/usr/bin/env python3
"""
Script to validate resource JSON files for the Role Play System.

Validates:
- JSON syntax
- Required metadata fields (resource_version, last_modified)
- Resource version compatibility
- Character/scenario ID references
- Language consistency

Usage: python scripts/validate_resources.py [path_to_resources_dir]
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "python"))

from role_play.common.resource_loader import ResourceLoader


def validate_json_syntax(file_path: str) -> Tuple[bool, str]:
    """Validate JSON syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True, "OK"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_metadata(data: dict, file_path: str) -> List[str]:
    """Validate required metadata fields."""
    errors = []
    
    # Check resource_version
    if "resource_version" not in data:
        errors.append("Missing 'resource_version' field")
    else:
        version = data["resource_version"]
        if version not in ResourceLoader.SUPPORTED_VERSIONS:
            errors.append(
                f"Unsupported resource_version '{version}'. "
                f"Supported versions: {', '.join(ResourceLoader.SUPPORTED_VERSIONS)}"
            )
    
    # Check last_modified
    if "last_modified" not in data:
        errors.append("Missing 'last_modified' field")
    else:
        try:
            datetime.fromisoformat(data["last_modified"].replace('Z', '+00:00'))
        except ValueError:
            errors.append(f"Invalid 'last_modified' format: {data['last_modified']}")
    
    # Check modified_by (optional but recommended)
    if "modified_by" not in data:
        errors.append("Missing 'modified_by' field (recommended)")
    
    return errors


def validate_scenarios(scenarios: List[dict]) -> List[str]:
    """Validate scenario data structure."""
    errors = []
    seen_ids = set()
    
    for i, scenario in enumerate(scenarios):
        prefix = f"Scenario {i}: "
        
        # Check required fields
        if "id" not in scenario:
            errors.append(f"{prefix}Missing 'id' field")
        else:
            if scenario["id"] in seen_ids:
                errors.append(f"{prefix}Duplicate scenario ID '{scenario['id']}'")
            seen_ids.add(scenario["id"])
        
        if "name" not in scenario:
            errors.append(f"{prefix}Missing 'name' field")
        
        if "description" not in scenario:
            errors.append(f"{prefix}Missing 'description' field")
        
        if "language" not in scenario:
            errors.append(f"{prefix}Missing 'language' field")
        
        if "compatible_characters" not in scenario:
            errors.append(f"{prefix}Missing 'compatible_characters' field")
        elif not isinstance(scenario["compatible_characters"], list):
            errors.append(f"{prefix}'compatible_characters' must be a list")
    
    return errors


def validate_characters(characters: List[dict]) -> List[str]:
    """Validate character data structure."""
    errors = []
    seen_ids = set()
    
    for i, character in enumerate(characters):
        prefix = f"Character {i}: "
        
        # Check required fields
        if "id" not in character:
            errors.append(f"{prefix}Missing 'id' field")
        else:
            if character["id"] in seen_ids:
                errors.append(f"{prefix}Duplicate character ID '{character['id']}'")
            seen_ids.add(character["id"])
        
        if "name" not in character:
            errors.append(f"{prefix}Missing 'name' field")
        
        if "description" not in character:
            errors.append(f"{prefix}Missing 'description' field")
        
        if "language" not in character:
            errors.append(f"{prefix}Missing 'language' field")
        
        if "system_prompt" not in character:
            errors.append(f"{prefix}Missing 'system_prompt' field")
    
    return errors


def validate_cross_references(
    scenarios: List[dict], 
    all_character_ids: Set[str]
) -> List[str]:
    """Validate character references in scenarios."""
    errors = []
    
    for scenario in scenarios:
        if "compatible_characters" in scenario:
            for char_id in scenario["compatible_characters"]:
                if char_id not in all_character_ids:
                    errors.append(
                        f"Scenario '{scenario.get('id', 'unknown')}' references "
                        f"non-existent character '{char_id}'"
                    )
    
    return errors


def validate_language_consistency(items: List[dict], file_name: str) -> List[str]:
    """Validate language consistency within a file."""
    errors = []
    
    # Extract expected language from filename
    if "_" in file_name and file_name.endswith(".json"):
        # e.g., scenarios_zh-TW.json -> zh-TW
        expected_lang = file_name.rsplit("_", 1)[1].replace(".json", "")
    else:
        # Default files (scenarios.json) should be English
        expected_lang = "en"
    
    # Check each item's language
    languages = set()
    for item in items:
        if "language" in item:
            languages.add(item["language"])
            if item["language"] != expected_lang:
                errors.append(
                    f"Item '{item.get('id', 'unknown')}' has language "
                    f"'{item['language']}' but file suggests '{expected_lang}'"
                )
    
    if len(languages) > 1:
        errors.append(
            f"Multiple languages found in same file: {', '.join(sorted(languages))}"
        )
    
    return errors


def validate_resource_file(file_path: str, all_character_ids: Set[str]) -> Tuple[bool, List[str]]:
    """Validate a single resource file."""
    errors = []
    file_name = os.path.basename(file_path)
    
    # Validate JSON syntax
    valid, error = validate_json_syntax(file_path)
    if not valid:
        return False, [error]
    
    # Load data
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Validate metadata
    errors.extend(validate_metadata(data, file_path))
    
    # Validate content based on file type
    if "scenarios" in file_name:
        if "scenarios" in data:
            errors.extend(validate_scenarios(data["scenarios"]))
            errors.extend(validate_language_consistency(data["scenarios"], file_name))
            # Cross-reference validation will be done later
        else:
            errors.append("Missing 'scenarios' key in scenarios file")
    
    elif "characters" in file_name:
        if "characters" in data:
            errors.extend(validate_characters(data["characters"]))
            errors.extend(validate_language_consistency(data["characters"], file_name))
            # Collect character IDs for cross-reference
            for char in data.get("characters", []):
                if "id" in char:
                    all_character_ids.add(char["id"])
        else:
            errors.append("Missing 'characters' key in characters file")
    
    return len(errors) == 0, errors


def validate_resources_directory(resources_dir: str) -> bool:
    """Validate all resource files in a directory."""
    print(f"Validating resources in: {resources_dir}\n")
    
    all_valid = True
    all_character_ids: Set[str] = set()
    scenario_files = []
    
    # First pass: validate all files and collect character IDs
    for root, dirs, files in os.walk(resources_dir):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, resources_dir)
                
                print(f"Validating {rel_path}...")
                valid, errors = validate_resource_file(file_path, all_character_ids)
                
                if valid:
                    print(f"  ✓ Valid")
                    if "scenarios" in file:
                        scenario_files.append(file_path)
                else:
                    print(f"  ✗ Invalid:")
                    for error in errors:
                        print(f"    - {error}")
                    all_valid = False
                print()
    
    # Second pass: validate cross-references
    if scenario_files and all_character_ids:
        print("Validating cross-references...")
        for scenario_file in scenario_files:
            with open(scenario_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "scenarios" in data:
                errors = validate_cross_references(data["scenarios"], all_character_ids)
                if errors:
                    rel_path = os.path.relpath(scenario_file, resources_dir)
                    print(f"  ✗ {rel_path}:")
                    for error in errors:
                        print(f"    - {error}")
                    all_valid = False
        
        if all_valid:
            print("  ✓ All cross-references valid")
    
    return all_valid


def main():
    """Main entry point."""
    # Default to data/resources directory
    if len(sys.argv) > 1:
        resources_dir = sys.argv[1]
    else:
        resources_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "resources"
        )
    
    if not os.path.exists(resources_dir):
        print(f"Error: Resources directory not found: {resources_dir}")
        sys.exit(1)
    
    # Validate all resources
    all_valid = validate_resources_directory(resources_dir)
    
    print("\n" + "="*60)
    if all_valid:
        print("✓ All resources are valid!")
        sys.exit(0)
    else:
        print("✗ Some resources have validation errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()