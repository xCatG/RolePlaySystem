#!/usr/bin/env python3
"""
Script to validate resource JSON files for the Role Play System.

Validates:
- JSON syntax
- Required metadata fields (resource_version, last_modified)
- Resource version compatibility
- Character/scenario ID references
- Language consistency
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "python"))

from role_play.common.resource_loader import ResourceLoader


class ResourceValidator:
    """A class to encapsulate validation logic."""

    def __init__(self, resources_dir: str):
        self.resources_dir = resources_dir
        self.all_character_ids: Set[str] = set()
        self.all_scenario_ids: Set[str] = set()
        self.errors: List[str] = []
        self.scenario_files: List[str] = []
        self.script_files: List[str] = []

    def validate(self) -> bool:
        """Run all validation steps."""
        print(f"Validating resources in: {self.resources_dir}\n")
        self._validate_all_files()
        self._validate_cross_references()

        if self.errors:
            print("✗ Some resources have validation errors:")
            for error in self.errors:
                print(f"  - {error}")
            return False
        else:
            print("✓ All resources are valid!")
            return True

    def _validate_all_files(self):
        """First pass: validate all files and collect character IDs."""
        for root, _, files in os.walk(self.resources_dir):
            for file in sorted(files):
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.resources_dir)
                    print(f"Validating {rel_path}...")
                    
                    file_errors = self._validate_resource_file(file_path)
                    
                    if file_errors:
                        self.errors.extend(f"{rel_path}: {e}" for e in file_errors)
                        print(f"  ✗ Invalid")
                    else:
                        print(f"  ✓ Valid")
                    print()

    def _validate_resource_file(self, file_path: str) -> List[str]:
        """Validate a single resource file."""
        file_errors: List[str] = []
        file_name = os.path.basename(file_path)

        # 1. Validate JSON syntax
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return [f"Invalid JSON: {e}"]
        except IOError as e:
            return [f"Error reading file: {e}"]

        # 2. Validate metadata
        file_errors.extend(self._validate_metadata(data))

        # 3. Validate content based on file type
        if "scenarios" in file_name:
            if "scenarios" in data:
                scenarios = data["scenarios"]
                file_errors.extend(self._validate_scenarios(scenarios))
                file_errors.extend(self._validate_language_consistency(scenarios, file_name))
                self.scenario_files.append(file_path)
            else:
                file_errors.append("Missing 'scenarios' key in scenarios file")
        
        elif "characters" in file_name:
            if "characters" in data:
                characters = data["characters"]
                file_errors.extend(self._validate_characters(characters))
                file_errors.extend(self._validate_language_consistency(characters, file_name))
                for char in characters:
                    if "id" in char:
                        self.all_character_ids.add(char["id"])
            else:
                file_errors.append("Missing 'characters' key in characters file")

        elif "scripts" in file_name:
            if "scripts" in data:
                scripts = data["scripts"]
                file_errors.extend(self._validate_scripts(scripts))
                file_errors.extend(self._validate_language_consistency(scripts, file_name))
                self.script_files.append(file_path)
            else:
                file_errors.append("Missing 'scripts' key in scripts file")

        return file_errors

    def _validate_metadata(self, data: dict[str, Any]) -> List[str]:
        """Validate required metadata fields."""
        errors = []
        if "resource_version" not in data:
            errors.append("Missing 'resource_version' field")
        else:
            version = data["resource_version"]
            if version not in ResourceLoader.SUPPORTED_VERSIONS:
                errors.append(
                    f"Unsupported resource_version '{version}'. "
                    f"Supported: {', '.join(ResourceLoader.SUPPORTED_VERSIONS)}"
                )
        if "last_modified" not in data:
            errors.append("Missing 'last_modified' field")
        else:
            try:
                datetime.fromisoformat(data["last_modified"].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                errors.append(f"Invalid 'last_modified' format: {data['last_modified']}")
        return errors

    def _validate_scenarios(self, scenarios: list[dict[str, Any]]) -> List[str]:
        """Validate scenario data structure."""
        errors, seen_ids = [], set()
        for i, scenario in enumerate(scenarios):
            prefix = f"Scenario {i}: "
            if "id" not in scenario:
                errors.append(f"{prefix}Missing 'id' field")
            elif scenario["id"] in seen_ids:
                errors.append(f"{prefix}Duplicate ID '{scenario['id']}'")
            else:
                seen_ids.add(scenario["id"])
                self.all_scenario_ids.add(scenario["id"])
            for field in ["name", "description", "language", "compatible_characters"]:
                if field not in scenario:
                    errors.append(f"{prefix}Missing '{field}' field")
        return errors

    def _validate_characters(self, characters: list[dict[str, Any]]) -> List[str]:
        """Validate character data structure."""
        errors, seen_ids = [], set()
        for i, character in enumerate(characters):
            prefix = f"Character {i}: "
            if "id" not in character:
                errors.append(f"{prefix}Missing 'id' field")
            elif character["id"] in seen_ids:
                errors.append(f"{prefix}Duplicate ID '{character['id']}'")
            else:
                seen_ids.add(character["id"])
            for field in ["name", "description", "language", "system_prompt"]:
                if field not in character:
                    errors.append(f"{prefix}Missing '{field}' field")
        return errors

    def _validate_scripts(self, scripts: list[dict[str, Any]]) -> List[str]:
        """Validate script data structure."""
        errors, seen_ids = [], set()
        for i, script in enumerate(scripts):
            prefix = f"Script {i}: "
            if "id" not in script:
                errors.append(f"{prefix}Missing 'id' field")
            elif script["id"] in seen_ids:
                errors.append(f"{prefix}Duplicate ID '{script['id']}'")
            else:
                seen_ids.add(script["id"])
            for field in ["scenario_id", "character_id", "language", "script"]:
                if field not in script:
                    errors.append(f"{prefix}Missing '{field}' field")
        return errors

    def _validate_language_consistency(self, items: list[dict[str, Any]], file_name: str) -> List[str]:
        """Validate language consistency within a file."""
        errors = []
        expected_lang = "en"
        if "_" in file_name and file_name.endswith(".json"):
            expected_lang = file_name.rsplit("_", 1)[1].replace(".json", "")
        
        for item in items:
            lang = item.get("language")
            if lang and lang != expected_lang:
                errors.append(
                    f"Item '{item.get('id', 'N/A')}' has language '{lang}' "
                    f"but file suggests '{expected_lang}'"
                )
        return errors

    def _validate_cross_references(self):
        """Second pass: validate cross-references for all scenarios."""
        if not self.scenario_files or not self.all_character_ids:
            return

        print("Validating cross-references...")
        all_refs_valid = True
        for scenario_file in self.scenario_files:
            rel_path = os.path.relpath(scenario_file, self.resources_dir)
            try:
                with open(scenario_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                scenarios = data.get("scenarios", [])
                for scenario in scenarios:
                    for char_id in scenario.get("compatible_characters", []):
                        if char_id not in self.all_character_ids:
                            error = (
                                f"{rel_path}: Scenario '{scenario.get('id', 'N/A')}' "
                                f"references non-existent character '{char_id}'"
                            )
                            self.errors.append(error)
                            all_refs_valid = False
            except (IOError, json.JSONDecodeError) as e:
                self.errors.append(f"Could not process {rel_path} for cross-referencing: {e}")
                all_refs_valid = False

        # Validate scripts references
        for script_file in self.script_files:
            rel_path = os.path.relpath(script_file, self.resources_dir)
            try:
                with open(script_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                scripts = data.get("scripts", [])
                for script in scripts:
                    if script.get("character_id") not in self.all_character_ids:
                        self.errors.append(
                            f"{rel_path}: Script '{script.get('id', 'N/A')}' references non-existent character '{script.get('character_id')}'"
                        )
                        all_refs_valid = False
                    if script.get("scenario_id") not in self.all_scenario_ids:
                        self.errors.append(
                            f"{rel_path}: Script '{script.get('id', 'N/A')}' references non-existent scenario '{script.get('scenario_id')}'"
                        )
                        all_refs_valid = False
            except (IOError, json.JSONDecodeError) as e:
                self.errors.append(f"Could not process {rel_path} for cross-referencing: {e}")
                all_refs_valid = False

        if all_refs_valid:
            print("  ✓ All cross-references valid\n")
        else:
            print("  ✗ Invalid cross-references found\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate resource JSON files for the Role Play System.")
    parser.add_argument(
        "resources_dir",
        nargs="?",
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "resources"
        ),
        help="Path to the resources directory. Defaults to ../data/resources.",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.resources_dir):
        print(f"Error: Resources directory not found: {args.resources_dir}", file=sys.stderr)
        sys.exit(1)

    validator = ResourceValidator(args.resources_dir)
    if not validator.validate():
        sys.exit(1)


if __name__ == "__main__":
    main()
