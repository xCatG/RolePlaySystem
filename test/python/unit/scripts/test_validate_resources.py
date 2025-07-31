"""Unit tests for the validate_resources.py script."""
from __future__ import annotations

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.validate_resources import ResourceValidator

@pytest.fixture
def resource_validator(tmp_path):
    """Fixture to create a ResourceValidator instance with a temporary directory."""
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir()
    return ResourceValidator(str(resources_dir))

def create_resource_file(path, content):
    """Helper to create a JSON file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(content, f, indent=2)

class TestResourceValidator:
    """Tests for the ResourceValidator class."""

    def test_init(self, resource_validator, tmp_path):
        """Test validator initialization."""
        assert resource_validator.resources_dir == str(tmp_path / "resources")
        assert resource_validator.errors == []

    def test_validate_empty_dir(self, resource_validator):
        """Test validation on an empty directory."""
        assert resource_validator.validate() is True
        assert resource_validator.errors == []

    def test_validate_invalid_json(self, resource_validator):
        """Test validation fails on invalid JSON."""
        (Path(resource_validator.resources_dir) / "invalid.json").write_text("{'bad': json}")
        assert resource_validator.validate() is False
        assert len(resource_validator.errors) == 1
        assert "Invalid JSON" in resource_validator.errors[0]

    def test_validate_missing_metadata(self, resource_validator):
        """Test validation fails on missing metadata."""
        create_resource_file(
            Path(resource_validator.resources_dir) / "characters.json",
            {"characters": [{"id": "char1", "name": "Test"}]}
        )
        assert resource_validator.validate() is False
        assert "Missing 'resource_version'" in resource_validator.errors[0]
        assert "Missing 'last_modified'" in resource_validator.errors[1]

    def test_validate_unsupported_version(self, resource_validator):
        """Test validation fails on unsupported resource version."""
        create_resource_file(
            Path(resource_validator.resources_dir) / "characters.json",
            {
                "resource_version": "0.1",
                "last_modified": "2025-01-01T00:00:00Z",
                "characters": []
            }
        )
        assert resource_validator.validate() is False
        assert "Unsupported resource_version" in resource_validator.errors[0]

    def test_validate_duplicate_ids(self, resource_validator):
        """Test validation fails on duplicate character IDs."""
        create_resource_file(
            Path(resource_validator.resources_dir) / "characters.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "characters": [
                    {"id": "char1", "name": "Char 1", "description": "", "language": "en", "system_prompt": ""},
                    {"id": "char1", "name": "Char 2", "description": "", "language": "en", "system_prompt": ""}
                ]
            }
        )
        assert resource_validator.validate() is False
        assert "Duplicate ID 'char1'" in resource_validator.errors[0]

    def test_validate_missing_character_field(self, resource_validator):
        """Test validation fails on missing required character field."""
        create_resource_file(
            Path(resource_validator.resources_dir) / "characters.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "characters": [{"id": "char1", "language": "en"}]
            }
        )
        assert resource_validator.validate() is False
        assert "Missing 'name' field" in resource_validator.errors[0]

    def test_validate_cross_reference_failure(self, resource_validator):
        """Test validation fails on bad cross-references."""
        # Valid characters file
        create_resource_file(
            Path(resource_validator.resources_dir) / "characters.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "characters": [{"id": "char1", "name": "Char 1", "description": "", "language": "en", "system_prompt": ""}]
            }
        )
        # Scenarios file with a reference to a non-existent character
        create_resource_file(
            Path(resource_validator.resources_dir) / "scenarios.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "scenarios": [{
                    "id": "scen1", "name": "Scene 1", "description": "", "language": "en",
                    "compatible_characters": ["char1", "non_existent_char"]
                }]
            }
        )
        assert resource_validator.validate() is False
        assert "references non-existent character 'non_existent_char'" in resource_validator.errors[0]

    def test_validate_language_consistency_failure(self, resource_validator):
        """Test validation fails on language inconsistency."""
        create_resource_file(
            Path(resource_validator.resources_dir) / "characters_zh-TW.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "characters": [{"id": "char1", "name": "Char 1", "description": "", "language": "en", "system_prompt": ""}]
            }
        )
        assert resource_validator.validate() is False
        assert "language 'en' but file suggests 'zh-TW'" in resource_validator.errors[0]

    def test_validate_script_cross_reference_failure(self, resource_validator):
        """Test validation fails when a script references missing scenario or character."""
        create_resource_file(
            Path(resource_validator.resources_dir) / "characters.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "characters": [{"id": "char1", "name": "Char 1", "description": "", "language": "en", "system_prompt": ""}]
            }
        )
        create_resource_file(
            Path(resource_validator.resources_dir) / "scenarios.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "scenarios": [{"id": "sc1", "name": "Scene", "description": "", "language": "en", "compatible_characters": ["char1"]}]
            }
        )
        create_resource_file(
            Path(resource_validator.resources_dir) / "scripts.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "scripts": [
                    {"id": "scr1", "scenario_id": "sc_missing", "character_id": "char1", "language": "en", "script": []}
                ]
            }
        )
        assert resource_validator.validate() is False
        assert "references non-existent scenario" in resource_validator.errors[0]

    def test_validate_successful_run(self, resource_validator):
        """Test a successful validation run."""
        create_resource_file(
            Path(resource_validator.resources_dir) / "characters.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "characters": [{"id": "char1", "name": "Char 1", "description": "", "language": "en", "system_prompt": ""}]
            }
        )
        create_resource_file(
            Path(resource_validator.resources_dir) / "scenarios.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "scenarios": [{
                    "id": "scen1", "name": "Scene 1", "description": "", "language": "en",
                    "compatible_characters": ["char1"]
                }]
            }
        )
        create_resource_file(
            Path(resource_validator.resources_dir) / "scripts.json",
            {
                "resource_version": "1.0",
                "last_modified": "2025-01-01T00:00:00Z",
                "scripts": [{
                    "id": "script1", "scenario_id": "scen1", "character_id": "char1",
                    "language": "en", "script": []
                }]
            }
        )
        assert resource_validator.validate() is True
        assert resource_validator.errors == []

@patch('scripts.validate_resources.argparse.ArgumentParser')
@patch('scripts.validate_resources.sys.exit')
def test_main_function(mock_exit, mock_argparse, tmp_path):
    """Test the main function of the script."""
    # Setup mock args
    mock_args = MagicMock()
    mock_args.resources_dir = str(tmp_path)
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = mock_args
    mock_argparse.return_value = mock_parser

    # Patch the validator
    with patch('scripts.validate_resources.ResourceValidator') as mock_validator:
        instance = mock_validator.return_value
        
        from scripts.validate_resources import main
        
        # Check for success
        instance.validate.return_value = True
        main()
        mock_exit.assert_not_called()
        
        # Check for failure
        instance.validate.return_value = False
        main()
        mock_exit.assert_called_with(1)
