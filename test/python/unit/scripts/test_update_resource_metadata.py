"""Unit tests for the update_resource_metadata.py script."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.update_resource_metadata import ResourceUpdater

@pytest.fixture
def resource_updater(tmp_path):
    """Fixture to create a ResourceUpdater instance."""
    return ResourceUpdater(str(tmp_path), bump_version=False, modified_by="test_user")

def create_resource_file(path, content):
    """Helper to create a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(content, f, indent=2)

class TestResourceUpdater:
    """Tests for the ResourceUpdater class."""

    def test_init(self, resource_updater, tmp_path):
        """Test updater initialization."""
        assert resource_updater.path == str(tmp_path)
        assert resource_updater.bump_version is False
        assert resource_updater.modified_by == "test_user"

    def test_update_single_file(self, tmp_path):
        """Test updating a single resource file."""
        file_path = tmp_path / "characters.json"
        create_resource_file(file_path, {
            "resource_version": "1.0",
            "last_modified": "2024-01-01T00:00:00Z",
            "modified_by": "manual",
            "characters": []
        })

        updater = ResourceUpdater(str(file_path), bump_version=True, modified_by="test_runner")
        assert updater.run() is True

        with open(file_path, 'r') as f:
            data = json.load(f)
        
        assert data["resource_version"] == "1.1"
        assert data["modified_by"] == "test_runner"
        assert data["last_modified"] != "2024-01-01T00:00:00Z"

    def test_update_directory(self, tmp_path):
        """Test updating all JSON files in a directory."""
        file1 = tmp_path / "dir1" / "file1.json"
        file2 = tmp_path / "dir2" / "file2.json"
        create_resource_file(file1, {"resource_version": "1.0", "last_modified": "2024-01-01T00:00:00Z"})
        create_resource_file(file2, {"resource_version": "1.2", "last_modified": "2024-01-01T00:00:00Z"})
        (tmp_path / "not_a_json.txt").write_text("hello")

        updater = ResourceUpdater(str(tmp_path), bump_version=True, modified_by="dir_runner")
        assert updater.run() is True
        assert updater.success_count == 2
        assert updater.fail_count == 0

        with open(file1, 'r') as f:
            data1 = json.load(f)
        assert data1["resource_version"] == "1.1"
        assert data1["modified_by"] == "dir_runner"

        with open(file2, 'r') as f:
            data2 = json.load(f)
        assert data2["resource_version"] == "1.3"
        assert data2["modified_by"] == "dir_runner"

    def test_run_on_invalid_json(self, tmp_path):
        """Test that updater handles invalid JSON gracefully."""
        file_path = tmp_path / "invalid.json"
        file_path.write_text("{ not json }")

        updater = ResourceUpdater(str(tmp_path), bump_version=False, modified_by="test")
        assert updater.run() is False
        assert updater.fail_count == 1

    def test_run_on_nonexistent_path(self):
        """Test that updater handles a non-existent path."""
        updater = ResourceUpdater("/non/existent/path", bump_version=False, modified_by="test")
        assert updater.run() is False

    def test_bump_version_logic(self):
        """Test the patch version bumping logic."""
        assert ResourceUpdater._bump_patch_version("1.0") == "1.1"
        assert ResourceUpdater._bump_patch_version("1.9") == "1.10"
        assert ResourceUpdater._bump_patch_version("2.123") == "2.124"
        # Should not change non-compliant versions
        assert ResourceUpdater._bump_patch_version("1.0.1") == "1.0.1"
        assert ResourceUpdater._bump_patch_version("abc") == "abc"

@patch('scripts.update_resource_metadata.argparse.ArgumentParser')
@patch('scripts.update_resource_metadata.ResourceUpdater')
@patch('scripts.update_resource_metadata.subprocess.run')
@patch('scripts.update_resource_metadata.sys.exit')
def test_main_function(mock_exit, mock_subprocess, mock_updater, mock_argparse):
    """Test the main function of the script."""
    # Setup mock args
    mock_args = MagicMock()
    mock_args.path = "/fake/path"
    mock_args.bump_version = True
    mock_args.modified_by = "cli_user"
    mock_args.no_validate = False
    
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = mock_args
    mock_argparse.return_value = mock_parser

    # Mock updater instance
    instance = mock_updater.return_value
    instance.run.return_value = True

    from scripts.update_resource_metadata import main

    # Run main and check for success
    main()
    
    mock_updater.assert_called_once_with("/fake/path", True, "cli_user")
    mock_subprocess.assert_called_once()
    mock_exit.assert_not_called() # Should not exit on success

    # Test failure case
    instance.run.return_value = False
    main()
    mock_exit.assert_called_with(1)
    
    # Test --no-validate
    mock_subprocess.reset_mock()
    mock_exit.reset_mock()
    mock_args.no_validate = True
    instance.run.return_value = True
    main()
    mock_subprocess.assert_not_called()
    mock_exit.assert_not_called()
