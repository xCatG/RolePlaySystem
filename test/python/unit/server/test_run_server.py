"""Tests for run_server configuration validation."""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from role_play.server.config import DevelopmentConfig
from role_play.common.storage import FileStorageConfig, GCSStorageConfig, LockConfig


def test_validate_configuration_with_valid_file_storage(tmp_path):
    """Test _validate_configuration with valid file storage configuration."""
    from src.python.run_server import _validate_configuration
    
    # Create a test directory
    storage_path = tmp_path / "storage"
    storage_path.mkdir()
    
    # Create config with file storage
    config = DevelopmentConfig()
    config.storage = FileStorageConfig(
        type="file",
        base_dir=str(storage_path),
        lock=LockConfig(strategy="file")
    )
    
    # Should not raise any exception
    _validate_configuration(config)


def test_validate_configuration_file_storage_path_not_exists():
    """Test _validate_configuration raises FileNotFoundError for non-existent path."""
    from src.python.run_server import _validate_configuration
    
    config = DevelopmentConfig()
    config.storage = FileStorageConfig(
        type="file",
        base_dir="/non/existent/path",
        lock=LockConfig(strategy="file")
    )
    
    with pytest.raises(FileNotFoundError, match="Storage path '/non/existent/path' does not exist"):
        _validate_configuration(config)


def test_validate_configuration_file_storage_path_not_directory(tmp_path):
    """Test _validate_configuration raises NotADirectoryError for file path."""
    from src.python.run_server import _validate_configuration
    
    # Create a file instead of directory
    storage_file = tmp_path / "storage_file"
    storage_file.write_text("not a directory")
    
    config = DevelopmentConfig()
    config.storage = FileStorageConfig(
        type="file",
        base_dir=str(storage_file),
        lock=LockConfig(strategy="file")
    )
    
    with pytest.raises(NotADirectoryError, match="is not a directory"):
        _validate_configuration(config)


@patch('os.access')
def test_validate_configuration_file_storage_no_permissions(mock_access, tmp_path):
    """Test _validate_configuration raises PermissionError for unreadable/unwritable path."""
    from src.python.run_server import _validate_configuration
    
    storage_path = tmp_path / "storage"
    storage_path.mkdir()
    
    # Mock os.access to return False (no read/write permissions)
    mock_access.return_value = False
    
    config = DevelopmentConfig()
    config.storage = FileStorageConfig(
        type="file",
        base_dir=str(storage_path),
        lock=LockConfig(strategy="file")
    )
    
    with pytest.raises(PermissionError, match="is not readable/writable"):
        _validate_configuration(config)


def test_validate_configuration_gcs_storage_missing_project_id():
    """Test _validate_configuration raises ValueError for missing GCS project_id."""
    from src.python.run_server import _validate_configuration
    
    config = DevelopmentConfig()
    config.storage = GCSStorageConfig(
        type="gcs",
        bucket="test-bucket",
        project_id="",  # Missing project_id
        lock=LockConfig(strategy="object")
    )
    
    with pytest.raises(ValueError, match="GCP_PROJECT_ID environment variable is required"):
        _validate_configuration(config)


def test_validate_configuration_gcs_storage_missing_bucket():
    """Test _validate_configuration raises ValueError for missing GCS bucket."""
    from src.python.run_server import _validate_configuration
    
    config = DevelopmentConfig()
    config.storage = GCSStorageConfig(
        type="gcs",
        bucket="",  # Missing bucket
        project_id="test-project",
        lock=LockConfig(strategy="object")
    )
    
    with pytest.raises(ValueError, match="GCS_BUCKET environment variable is required"):
        _validate_configuration(config)


def test_validate_configuration_gcs_storage_valid():
    """Test _validate_configuration with valid GCS storage configuration."""
    from src.python.run_server import _validate_configuration
    
    config = DevelopmentConfig()
    config.storage = GCSStorageConfig(
        type="gcs",
        bucket="test-bucket",
        project_id="test-project",
        lock=LockConfig(strategy="object")
    )
    
    # Should not raise any exception
    _validate_configuration(config)


def test_validate_configuration_unsupported_storage_type():
    """Test _validate_configuration raises ValueError for unsupported storage type."""
    from src.python.run_server import _validate_configuration
    
    config = DevelopmentConfig()
    # Create a mock storage config with unsupported type
    config.storage = MagicMock()
    config.storage.type = "unsupported"
    
    with pytest.raises(ValueError, match="Unsupported storage type: unsupported"):
        _validate_configuration(config)


def test_validate_configuration_no_storage():
    """Test _validate_configuration with no storage configuration."""
    from src.python.run_server import _validate_configuration
    
    config = DevelopmentConfig()
    config.storage = None
    
    # Should not raise any exception
    _validate_configuration(config)


@patch.dict(os.environ, {"JWT_SECRET_KEY": "production-secret"})
def test_validate_configuration_production_jwt_secret():
    """Test _validate_configuration validates JWT secret in production."""
    from src.python.run_server import _validate_configuration
    from role_play.server.config import ProductionConfig
    
    config = ProductionConfig()
    config.storage = None
    config.jwt_secret_key = "development-secret-key"
    
    with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set in production"):
        _validate_configuration(config)