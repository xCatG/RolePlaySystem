"""Unit tests for GCS backend monitoring integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from role_play.common.GCSBackend import GCSStorageBackend, GCS_AVAILABLE
from role_play.common.storage import GCSStorageConfig, LockConfig


@pytest.mark.skipif(not GCS_AVAILABLE, reason="google-cloud-storage not installed")
class TestGCSStorageMonitoring:
    """Test that GCS backend properly integrates with storage monitoring."""

    @pytest.fixture
    def mock_gcs_client(self):
        """Create a mock GCS client."""
        with patch('role_play.common.GCSBackend.gcs') as mock_gcs:
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_gcs.Client.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            yield mock_gcs, mock_client, mock_bucket

    @pytest.fixture
    def mock_monitor(self):
        """Create a mock storage monitor."""
        with patch('role_play.common.GCSBackend.get_storage_monitor') as mock_get_monitor:
            mock_monitor = MagicMock()
            mock_monitor.monitor_storage_operation = MagicMock()
            mock_monitor.monitor_lock_acquisition = MagicMock()
            mock_monitor.record_lock_expiry = AsyncMock()
            
            # Make context managers work properly
            mock_monitor.monitor_storage_operation.return_value.__aenter__ = AsyncMock()
            mock_monitor.monitor_storage_operation.return_value.__aexit__ = AsyncMock()
            mock_monitor.monitor_lock_acquisition.return_value.__aenter__ = AsyncMock()
            mock_monitor.monitor_lock_acquisition.return_value.__aexit__ = AsyncMock()
            
            mock_get_monitor.return_value = mock_monitor
            yield mock_monitor

    @pytest.fixture
    def gcs_config(self):
        """Create a test GCS configuration."""
        return GCSStorageConfig(
            type="gcs",
            bucket="test-bucket",
            prefix="test/",
            project_id="test-project",
            lock=LockConfig(strategy="object")
        )

    def test_gcs_backend_initializes_monitor(self, mock_gcs_client, mock_monitor, gcs_config):
        """Test that GCS backend initializes with a storage monitor."""
        backend = GCSStorageBackend(gcs_config)
        assert backend.monitor is mock_monitor

    @pytest.mark.asyncio
    async def test_read_operation_is_monitored(self, mock_gcs_client, mock_monitor, gcs_config):
        """Test that read operations are monitored."""
        _, _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_text.return_value = "test data"
        
        backend = GCSStorageBackend(gcs_config)
        await backend.read("test/path")
        
        mock_monitor.monitor_storage_operation.assert_called_with("read")

    @pytest.mark.asyncio
    async def test_write_operation_is_monitored(self, mock_gcs_client, mock_monitor, gcs_config):
        """Test that write operations are monitored."""
        _, _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        
        backend = GCSStorageBackend(gcs_config)
        await backend.write("test/path", "test data")
        
        mock_monitor.monitor_storage_operation.assert_called_with("write")

    @pytest.mark.asyncio
    async def test_delete_operation_is_monitored(self, mock_gcs_client, mock_monitor, gcs_config):
        """Test that delete operations are monitored."""
        _, _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        
        backend = GCSStorageBackend(gcs_config)
        await backend.delete("test/path")
        
        mock_monitor.monitor_storage_operation.assert_called_with("delete")

    @pytest.mark.asyncio
    async def test_list_operation_is_monitored(self, mock_gcs_client, mock_monitor, gcs_config):
        """Test that list operations are monitored."""
        _, mock_client, _ = mock_gcs_client
        mock_client.list_blobs.return_value = []
        
        backend = GCSStorageBackend(gcs_config)
        await backend.list_keys("test/")
        
        mock_monitor.monitor_storage_operation.assert_called_with("list")

    @pytest.mark.asyncio
    async def test_lock_acquisition_is_monitored(self, mock_gcs_client, mock_monitor, gcs_config):
        """Test that lock acquisition is monitored."""
        _, _, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        
        backend = GCSStorageBackend(gcs_config)
        
        # Test successful lock acquisition
        async with backend.lock("test/resource"):
            pass
        
        mock_monitor.monitor_lock_acquisition.assert_called_with("test/resource", "object")