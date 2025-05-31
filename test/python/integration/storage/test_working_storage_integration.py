"""Working integration tests for storage components.

These tests work with the actual implementation.
"""

import pytest
from unittest.mock import patch


class TestWorkingStorageFactory:
    """Test working storage factory functionality."""
    
    def test_create_file_storage_dev(self):
        """Test creating file storage in dev environment."""
        from role_play.common.storage_factory import create_storage_backend, Environment
        from role_play.common.storage import FileStorageConfig, LockConfig, FileStorage
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = FileStorageConfig(
                base_dir=tmpdir,
                lock=LockConfig(strategy="file")
            )
            storage = create_storage_backend(config, Environment.DEV)
            assert isinstance(storage, FileStorage)
            assert str(storage.storage_dir) == tmpdir
    
    @patch("google.cloud.storage.Client")
    def test_create_gcs_storage_beta(self, mock_client):
        """Test creating GCS storage in beta environment."""
        from role_play.common.storage_factory import create_storage_backend, Environment
        from role_play.common.storage import GCSStorageConfig, LockConfig
        from role_play.common.GCSBackend import GCSStorageBackend
        
        config = GCSStorageConfig(
            bucket="test-bucket",
            project_id="test-project",
            lock=LockConfig(strategy="object")
        )
        storage = create_storage_backend(config, Environment.BETA)
        assert isinstance(storage, GCSStorageBackend)
        assert storage.bucket_name == "test-bucket"
    
    def test_environment_restriction_works(self):
        """Test that environment restrictions are enforced."""
        from role_play.common.storage_factory import create_storage_backend, Environment
        from role_play.common.storage import FileStorageConfig, LockConfig
        from role_play.common.exceptions import StorageError
        
        config = FileStorageConfig(
            base_dir="/tmp",
            lock=LockConfig(strategy="file")
        )
        
        # Should work in dev
        storage = create_storage_backend(config, Environment.DEV)
        assert storage is not None
        
        # Should fail in beta
        with pytest.raises(StorageError, match="not allowed in beta"):
            create_storage_backend(config, Environment.BETA)


class TestWorkingStorageMonitoring:
    """Test working storage monitoring functionality."""
    
    def test_lock_metrics_exists(self):
        """Test that LockMetrics class works."""
        from role_play.common.storage_monitoring import LockMetrics
        
        metrics = LockMetrics()
        # Check it has expected attributes
        assert hasattr(metrics, 'acquisition_attempts')
        assert hasattr(metrics, 'acquisition_successes')
        assert hasattr(metrics, 'acquisition_failures')
    
    def test_storage_metrics_exists(self):
        """Test that StorageMetrics class works.""" 
        from role_play.common.storage_monitoring import StorageMetrics
        
        metrics = StorageMetrics()
        # Check it has expected attributes 
        assert hasattr(metrics, 'read_operations')
        assert hasattr(metrics, 'write_operations')
        assert hasattr(metrics, 'delete_operations')
    
    def test_storage_monitor_exists(self):
        """Test that StorageMonitor class works."""
        from role_play.common.storage_monitoring import StorageMonitor
        
        monitor = StorageMonitor()
        # Check it exists and has basic structure
        assert monitor is not None


class TestWorkingGCSBackend:
    """Test working GCS backend functionality."""
    
    @patch("google.cloud.storage.Client")
    def test_gcs_backend_creation(self, mock_client):
        """Test GCS backend can be created."""
        from role_play.common.GCSBackend import GCSStorageBackend
        from role_play.common.storage import GCSStorageConfig, LockConfig
        
        config = GCSStorageConfig(
            bucket="test-bucket",
            project_id="test-project", 
            prefix="test/",
            lock=LockConfig(strategy="object")
        )
        
        storage = GCSStorageBackend(config)
        assert storage.bucket_name == "test-bucket"
        assert storage.prefix == "test/"
    
    @patch("google.cloud.storage.Client")
    def test_gcs_backend_has_required_methods(self, mock_client):
        """Test GCS backend has all required methods."""
        from role_play.common.GCSBackend import GCSStorageBackend
        from role_play.common.storage import GCSStorageConfig, LockConfig
        
        config = GCSStorageConfig(
            bucket="test-bucket",
            project_id="test-project",
            lock=LockConfig(strategy="object")
        )
        
        storage = GCSStorageBackend(config)
        
        # Check required StorageBackend methods
        required_methods = [
            'read', 'write', 'exists', 'delete', 'list_keys', 'lock',
            'create_user', 'get_user', 'update_user', 'delete_user',
            'create_user_auth_method', 'get_user_auth_methods', 'delete_user_auth_method',
            'create_session', 'get_session', 'update_session', 'delete_session'
        ]
        
        for method in required_methods:
            assert hasattr(storage, method), f"Missing method: {method}"
            assert callable(getattr(storage, method)), f"Method not callable: {method}"


class TestWorkingConfigValidation:
    """Test working config validation."""
    
    def test_valid_gcs_config(self):
        """Test valid GCS config passes validation."""
        from role_play.common.storage_factory import validate_storage_config
        from role_play.common.storage import GCSStorageConfig, LockConfig
        
        config = GCSStorageConfig(
            bucket="test-bucket",
            project_id="test-project",
            lock=LockConfig(strategy="object")
        )
        
        # Should not raise
        validate_storage_config(config)
    
    def test_valid_file_config(self):
        """Test valid file config passes validation."""
        from role_play.common.storage_factory import validate_storage_config  
        from role_play.common.storage import FileStorageConfig, LockConfig
        
        config = FileStorageConfig(
            base_dir="/tmp",
            lock=LockConfig(strategy="file")
        )
        
        # Should not raise
        validate_storage_config(config)