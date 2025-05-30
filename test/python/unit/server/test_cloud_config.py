"""Tests for cloud storage configuration options."""

import pytest
import os
from unittest.mock import patch, MagicMock

from role_play.server.config import ServerConfig, DevelopmentConfig, ProductionConfig
from role_play.server.dependencies import get_storage_backend
from role_play.common.storage import FileStorage, GCSStorage, S3Storage
from role_play.common.exceptions import StorageError


class TestCloudStorageConfiguration:
    """Test cloud storage configuration options."""
    
    def test_gcs_config_fields(self):
        """Test GCS configuration fields are present."""
        config = ServerConfig()
        
        # Check GCS fields exist
        assert hasattr(config, 'gcs_bucket_name')
        assert hasattr(config, 'gcs_project_id')
        assert hasattr(config, 'gcs_credentials_path')
        assert hasattr(config, 'gcs_prefix')
        
        # Check default values
        assert config.gcs_bucket_name is None
        assert config.gcs_project_id is None
        assert config.gcs_credentials_path is None
        assert config.gcs_prefix == ""
    
    def test_s3_config_fields(self):
        """Test S3 configuration fields are present."""
        config = ServerConfig()
        
        # Check S3 fields exist
        assert hasattr(config, 's3_bucket_name')
        assert hasattr(config, 's3_region_name')
        assert hasattr(config, 's3_access_key_id')
        assert hasattr(config, 's3_secret_access_key')
        assert hasattr(config, 's3_prefix')
        
        # Check default values
        assert config.s3_bucket_name is None
        assert config.s3_region_name == "us-east-1"
        assert config.s3_access_key_id is None
        assert config.s3_secret_access_key is None
        assert config.s3_prefix == ""
    
    def test_redis_config_field(self):
        """Test Redis configuration field is present."""
        config = ServerConfig()
        
        assert hasattr(config, 'redis_url')
        assert config.redis_url is None
    
    def test_storage_type_options(self):
        """Test storage_type field accepts cloud options."""
        config = ServerConfig(storage_type="gcs")
        assert config.storage_type == "gcs"
        
        config = ServerConfig(storage_type="s3")
        assert config.storage_type == "s3"
        
        config = ServerConfig(storage_type="file")
        assert config.storage_type == "file"
    
    @patch.dict(os.environ, {
        'GCS_BUCKET_NAME': 'test-gcs-bucket',
        'GCS_PROJECT_ID': 'test-project',
        'GCS_CREDENTIALS_PATH': '/path/to/credentials.json',
        'GCS_PREFIX': 'test/',
        'S3_BUCKET_NAME': 'test-s3-bucket',
        'S3_REGION_NAME': 'us-west-2',
        'S3_ACCESS_KEY_ID': 'test-access-key',
        'S3_SECRET_ACCESS_KEY': 'test-secret-key',
        'S3_PREFIX': 'prod/',
        'REDIS_URL': 'redis://localhost:6379/1'
    })
    def test_config_from_environment_variables(self):
        """Test configuration loads from environment variables."""
        config = ServerConfig()
        
        # GCS config
        assert config.gcs_bucket_name == 'test-gcs-bucket'
        assert config.gcs_project_id == 'test-project'
        assert config.gcs_credentials_path == '/path/to/credentials.json'
        assert config.gcs_prefix == 'test/'
        
        # S3 config
        assert config.s3_bucket_name == 'test-s3-bucket'
        assert config.s3_region_name == 'us-west-2'
        assert config.s3_access_key_id == 'test-access-key'
        assert config.s3_secret_access_key == 'test-secret-key'
        assert config.s3_prefix == 'prod/'
        
        # Redis config
        assert config.redis_url == 'redis://localhost:6379/1'


class TestStorageBackendFactory:
    """Test storage backend factory with new cloud options."""
    
    @patch('role_play.server.dependencies.get_server_config')
    @patch('role_play.server.dependencies.FileStorage')
    def test_file_storage_creation(self, mock_file_storage, mock_get_config):
        """Test FileStorage creation."""
        # Clear cache before test
        get_storage_backend.cache_clear()
        
        # Mock config
        mock_config = MagicMock()
        mock_config.storage_type = "file"
        mock_config.storage_path = "/test/path"
        mock_get_config.return_value = mock_config
        
        # Create mock instance
        mock_instance = MagicMock()
        mock_file_storage.return_value = mock_instance
        
        # Mock file system checks
        with patch('role_play.server.dependencies.os.path.exists', return_value=True):
            with patch('role_play.server.dependencies.os.path.isdir', return_value=True):
                with patch('role_play.server.dependencies.os.access', return_value=True):
                    result = get_storage_backend()
        
        mock_file_storage.assert_called_once_with("/test/path")
        assert result == mock_instance
        
        # Clear cache after test
        get_storage_backend.cache_clear()
    
    @patch('role_play.server.dependencies.get_server_config')
    @patch('role_play.server.dependencies.GCSStorage')
    def test_gcs_storage_creation(self, mock_gcs_storage, mock_get_config):
        """Test GCSStorage creation."""
        # Clear cache before test
        get_storage_backend.cache_clear()
        
        # Mock config
        mock_config = MagicMock()
        mock_config.storage_type = "gcs"
        mock_config.gcs_bucket_name = "test-bucket"
        mock_config.gcs_project_id = "test-project"
        mock_config.gcs_credentials_path = "/path/to/creds.json"
        mock_config.gcs_prefix = "test/"
        mock_get_config.return_value = mock_config
        
        # Mock the GCSStorage initialization
        mock_instance = MagicMock()
        mock_gcs_storage.return_value = mock_instance
        
        result = get_storage_backend()
        
        mock_gcs_storage.assert_called_once_with(
            bucket_name="test-bucket",
            project_id="test-project",
            credentials_path="/path/to/creds.json",
            prefix="test/"
        )
        assert result == mock_instance
        
        # Clear cache after test
        get_storage_backend.cache_clear()
    
    @patch('role_play.server.dependencies.get_server_config')
    @patch('role_play.server.dependencies.S3Storage')
    def test_s3_storage_creation(self, mock_s3_storage, mock_get_config):
        """Test S3Storage creation."""
        # Clear cache before test
        get_storage_backend.cache_clear()
        
        # Mock config
        mock_config = MagicMock()
        mock_config.storage_type = "s3"
        mock_config.s3_bucket_name = "test-bucket"
        mock_config.s3_region_name = "us-west-2"
        mock_config.s3_access_key_id = "test-access-key"
        mock_config.s3_secret_access_key = "test-secret-key"
        mock_config.s3_prefix = "prod/"
        mock_get_config.return_value = mock_config
        
        # Mock the S3Storage initialization
        mock_instance = MagicMock()
        mock_s3_storage.return_value = mock_instance
        
        result = get_storage_backend()
        
        mock_s3_storage.assert_called_once_with(
            bucket_name="test-bucket",
            region_name="us-west-2",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            prefix="prod/"
        )
        assert result == mock_instance
        
        # Clear cache after test
        get_storage_backend.cache_clear()
    
    @patch('role_play.server.dependencies.get_server_config')
    def test_gcs_missing_bucket_name_error(self, mock_get_config):
        """Test error when GCS bucket name is missing."""
        # Clear cache before test
        get_storage_backend.cache_clear()
        
        mock_config = MagicMock()
        mock_config.storage_type = "gcs"
        mock_config.gcs_bucket_name = None
        mock_get_config.return_value = mock_config
        
        with pytest.raises(ValueError, match="GCS_BUCKET_NAME is required"):
            get_storage_backend()
        
        # Clear cache after test
        get_storage_backend.cache_clear()
    
    @patch('role_play.server.dependencies.get_server_config')
    def test_s3_missing_bucket_name_error(self, mock_get_config):
        """Test error when S3 bucket name is missing."""
        # Clear cache before test
        get_storage_backend.cache_clear()
        
        mock_config = MagicMock()
        mock_config.storage_type = "s3"
        mock_config.s3_bucket_name = None
        mock_get_config.return_value = mock_config
        
        with pytest.raises(ValueError, match="S3_BUCKET_NAME is required"):
            get_storage_backend()
        
        # Clear cache after test
        get_storage_backend.cache_clear()
    
    @patch('role_play.server.dependencies.get_server_config')
    def test_unsupported_storage_type_error(self, mock_get_config):
        """Test error for unsupported storage type."""
        # Clear cache before test
        get_storage_backend.cache_clear()
        
        mock_config = MagicMock()
        mock_config.storage_type = "unsupported"
        mock_get_config.return_value = mock_config
        
        with pytest.raises(ValueError, match="Unsupported storage type: unsupported"):
            get_storage_backend()
        
        # Clear cache after test
        get_storage_backend.cache_clear()


class TestConfigurationIntegration:
    """Integration tests for configuration with real config classes."""
    
    def test_development_config_defaults(self):
        """Test development configuration defaults."""
        config = DevelopmentConfig()
        
        assert config.debug is True
        assert config.storage_type == "file"
        assert config.gcs_bucket_name is None
        assert config.s3_bucket_name is None
        assert config.redis_url is None
    
    def test_production_config_validation(self):
        """Test production configuration validation."""
        # Should work with proper JWT secret
        config = ProductionConfig(jwt_secret_key="proper-production-secret")
        assert config.debug is False
        
        # Should fail with default development secret
        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set"):
            ProductionConfig()
    
    @patch.dict(os.environ, {
        'JWT_SECRET_KEY': 'production-secret',
        'STORAGE_TYPE': 'gcs',
        'GCS_BUCKET_NAME': 'prod-bucket',
        'GCS_PROJECT_ID': 'prod-project',
        'REDIS_URL': 'redis://redis.prod:6379/0'
    })
    def test_production_gcs_config(self):
        """Test production configuration with GCS."""
        config = ProductionConfig()
        
        assert config.jwt_secret_key == 'production-secret'
        assert config.storage_type == 'file'  # Default, would need explicit override
        assert config.gcs_bucket_name == 'prod-bucket'
        assert config.gcs_project_id == 'prod-project'
        assert config.redis_url == 'redis://redis.prod:6379/0'
    
    def test_config_field_descriptions(self):
        """Test that configuration fields have proper descriptions."""
        config = ServerConfig()
        
        # Test that field descriptions exist (Pydantic should have these)
        field_info = config.__fields__
        
        assert 'gcs_bucket_name' in field_info
        assert 'gcs_project_id' in field_info
        assert 's3_bucket_name' in field_info
        assert 's3_region_name' in field_info
        assert 'redis_url' in field_info
        
        # Check some descriptions
        assert "GCS bucket name" in str(field_info['gcs_bucket_name'])
        assert "S3 bucket name" in str(field_info['s3_bucket_name'])
        assert "Redis URL" in str(field_info['redis_url'])


class TestStorageBackendCaching:
    """Test storage backend singleton caching."""
    
    @patch('role_play.server.dependencies.get_server_config')
    @patch('role_play.server.dependencies.FileStorage')
    def test_storage_backend_singleton(self, mock_file_storage, mock_get_config):
        """Test that storage backend is cached as singleton."""
        # Clear cache before test
        get_storage_backend.cache_clear()
        
        # Mock config
        mock_config = MagicMock()
        mock_config.storage_type = "file"
        mock_config.storage_path = "/test/path"
        mock_get_config.return_value = mock_config
        
        # Mock file system checks and create a mock instance
        mock_instance = MagicMock()
        mock_file_storage.return_value = mock_instance
        
        with patch('role_play.server.dependencies.os.path.exists', return_value=True):
            with patch('role_play.server.dependencies.os.path.isdir', return_value=True):
                with patch('role_play.server.dependencies.os.access', return_value=True):
                    
                    # Call multiple times
                    backend1 = get_storage_backend()
                    backend2 = get_storage_backend()
                    
                    # Should return same instance (singleton behavior)
                    assert backend1 is backend2
                    assert backend1 == mock_instance
                    
                    # FileStorage should only be called once
                    assert mock_file_storage.call_count == 1
        
        # Clear cache after test
        get_storage_backend.cache_clear()


if __name__ == "__main__":
    pytest.main([__file__])