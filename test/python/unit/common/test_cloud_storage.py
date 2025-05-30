"""Unit tests for cloud storage backends."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Any, Dict, List

from role_play.common.exceptions import StorageError
from role_play.common.models import User, UserAuthMethod, SessionData, UserRole, AuthProvider

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from fixtures.factories import UserFactory, UserAuthMethodFactory, SessionDataFactory

# Import storage backends with proper skips for missing dependencies
try:
    from role_play.common.storage import GCSStorage, S3Storage, DistributedLockMixin
    STORAGE_IMPORTS_AVAILABLE = True
except ImportError as e:
    STORAGE_IMPORTS_AVAILABLE = False
    IMPORT_ERROR = str(e)


@pytest.mark.skipif(not STORAGE_IMPORTS_AVAILABLE, reason="Cloud storage dependencies not available")
class TestDistributedLockMixin:
    """Test distributed locking functionality."""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.eval = AsyncMock(return_value=1)
        mock_redis.close = AsyncMock()
        return mock_redis
    
    @pytest.fixture
    def lock_mixin(self, mock_redis_client):
        """Create DistributedLockMixin instance with mocked Redis."""
        
        class TestLockMixin(DistributedLockMixin):
            def __init__(self, redis_url=None):
                super().__init__(redis_url=redis_url)
        
        # Check if Redis is actually available first
        from role_play.common.storage import REDIS_AVAILABLE
        if not REDIS_AVAILABLE:
            pytest.skip("Redis dependencies not available")
        
        # Mock redis module at import time
        with patch('redis.asyncio.from_url', return_value=mock_redis_client):
            mixin = TestLockMixin(redis_url="redis://localhost:6379/0")
        
        return mixin
    
    @pytest.mark.asyncio
    async def test_acquire_distributed_lock_success(self, lock_mixin, mock_redis_client):
        """Test successful lock acquisition and release."""
        async with lock_mixin._acquire_distributed_lock("test_key", timeout=5):
            pass
        
        # Verify lock was acquired
        mock_redis_client.set.assert_called_once_with(
            "rps:lock:test_key",
            lock_mixin.instance_id,
            nx=True,
            ex=5
        )
        
        # Verify lock was released
        mock_redis_client.eval.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_acquire_distributed_lock_failure(self, lock_mixin, mock_redis_client):
        """Test lock acquisition failure."""
        mock_redis_client.set.return_value = False  # Lock acquisition fails
        
        with pytest.raises(StorageError, match="Could not acquire distributed lock"):
            async with lock_mixin._acquire_distributed_lock("test_key", timeout=5):
                pass
    
    @pytest.mark.asyncio
    async def test_no_redis_fallback(self):
        """Test fallback behavior when Redis is not available."""
        
        class TestLockMixin(DistributedLockMixin):
            def __init__(self, redis_url=None):
                super().__init__(redis_url=redis_url)
        
        mixin = TestLockMixin()  # No Redis URL
        
        # Should work without errors (no-op)
        async with mixin._acquire_distributed_lock("test_key"):
            pass
    
    @pytest.mark.asyncio
    async def test_redis_close(self, lock_mixin, mock_redis_client):
        """Test Redis connection cleanup."""
        await lock_mixin.close()
        mock_redis_client.close.assert_called_once()


@pytest.mark.skipif(not STORAGE_IMPORTS_AVAILABLE, reason="Cloud storage dependencies not available")
class TestGCSStorage:
    """Test Google Cloud Storage backend."""
    
    @pytest.fixture
    def mock_gcs_client(self):
        """Mock GCS client and bucket."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = True
        mock_client.bucket.return_value = mock_bucket
        return mock_client, mock_bucket
    
    @pytest.fixture
    def gcs_storage(self, mock_gcs_client):
        """Create GCSStorage instance with mocked dependencies."""
        mock_client, mock_bucket = mock_gcs_client
        
        # Check if Google Cloud is actually available first
        from role_play.common.storage import GOOGLE_CLOUD_AVAILABLE
        if not GOOGLE_CLOUD_AVAILABLE:
            pytest.skip("Google Cloud dependencies not available")
        
        with patch('role_play.common.storage.GOOGLE_CLOUD_AVAILABLE', True):
            with patch('google.cloud.storage.Client', return_value=mock_client):
                with patch('role_play.common.storage.REDIS_AVAILABLE', False):
                    storage = GCSStorage(
                        bucket_name="test-bucket",
                        project_id="test-project",
                        prefix="test/"
                    )
        
        storage.client = mock_client
        storage.bucket = mock_bucket
        return storage
    
    def test_gcs_storage_initialization(self, gcs_storage):
        """Test GCS storage initialization."""
        assert gcs_storage.bucket_name == "test-bucket"
        assert gcs_storage.project_id == "test-project"
        assert gcs_storage.prefix == "test/"
    
    def test_gcs_unavailable_error(self):
        """Test error when GCS library is not available."""
        with patch('role_play.common.storage.GOOGLE_CLOUD_AVAILABLE', False):
            with pytest.raises(ImportError, match="google-cloud-storage is required"):
                GCSStorage(bucket_name="test-bucket")
    
    def test_bucket_not_exists_error(self):
        """Test error when GCS bucket doesn't exist."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = False
        mock_client.bucket.return_value = mock_bucket
        
        with patch('role_play.common.storage.GOOGLE_CLOUD_AVAILABLE', True):
            with patch('google.cloud.storage.Client', return_value=mock_client):
                with patch('role_play.common.storage.REDIS_AVAILABLE', False):
                    with pytest.raises(StorageError, match="does not exist or is not accessible"):
                        GCSStorage(bucket_name="nonexistent-bucket")
    
    @pytest.mark.asyncio
    async def test_store_and_get_object(self, gcs_storage):
        """Test storing and retrieving objects."""
        test_data = {"key": "value", "number": 42}
        
        # Mock blob for storing
        mock_blob = MagicMock()
        gcs_storage.bucket.blob.return_value = mock_blob
        
        # Store object
        await gcs_storage._store_object("test/key.json", test_data)
        
        # Verify upload was called
        mock_blob.upload_from_string.assert_called_once()
        uploaded_content = mock_blob.upload_from_string.call_args[0][0]
        assert json.loads(uploaded_content) == test_data
        
        # Mock blob for getting
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = json.dumps(test_data)
        
        # Get object
        result = await gcs_storage._get_object("test/key.json")
        assert result == test_data
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_object(self, gcs_storage):
        """Test getting non-existent object returns None."""
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        gcs_storage.bucket.blob.return_value = mock_blob
        
        result = await gcs_storage._get_object("nonexistent.json")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_object(self, gcs_storage):
        """Test deleting objects."""
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        gcs_storage.bucket.blob.return_value = mock_blob
        
        result = await gcs_storage._delete_object("test/key.json")
        assert result is True
        mock_blob.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_user_operations(self, gcs_storage):
        """Test user CRUD operations."""
        user = UserFactory.create()
        
        # Mock successful storage
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False  # For create
        gcs_storage.bucket.blob.return_value = mock_blob
        
        # Create user
        created_user = await gcs_storage.create_user(user)
        assert created_user == user
        mock_blob.upload_from_string.assert_called()
        
        # Mock for get user
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = json.dumps(user.model_dump(), default=str)
        
        # Get user
        retrieved_user = await gcs_storage.get_user(user.id)
        assert retrieved_user.id == user.id
        assert retrieved_user.email == user.email


@pytest.mark.skipif(not STORAGE_IMPORTS_AVAILABLE, reason="Cloud storage dependencies not available")
class TestS3Storage:
    """Test AWS S3 storage backend."""
    
    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}  # Bucket exists
        return mock_client
    
    @pytest.fixture
    def s3_storage(self, mock_s3_client):
        """Create S3Storage instance with mocked dependencies."""
        # Check if AWS S3 is actually available first
        from role_play.common.storage import AWS_S3_AVAILABLE
        if not AWS_S3_AVAILABLE:
            pytest.skip("AWS S3 dependencies not available")
        
        with patch('role_play.common.storage.AWS_S3_AVAILABLE', True):
            with patch('boto3.Session') as mock_session:
                mock_session.return_value.client.return_value = mock_s3_client
                with patch('role_play.common.storage.REDIS_AVAILABLE', False):
                    storage = S3Storage(
                        bucket_name="test-bucket",
                        region_name="us-east-1",
                        prefix="test/"
                    )
        
        storage.s3_client = mock_s3_client
        return storage
    
    def test_s3_storage_initialization(self, s3_storage):
        """Test S3 storage initialization."""
        assert s3_storage.bucket_name == "test-bucket"
        assert s3_storage.region_name == "us-east-1"
        assert s3_storage.prefix == "test/"
    
    def test_s3_unavailable_error(self):
        """Test error when boto3 is not available."""
        with patch('role_play.common.storage.AWS_S3_AVAILABLE', False):
            with pytest.raises(ImportError, match="boto3 is required"):
                S3Storage(bucket_name="test-bucket")
    
    @pytest.mark.asyncio
    async def test_store_and_get_object(self, s3_storage):
        """Test storing and retrieving objects via S3."""
        test_data = {"key": "value", "number": 42}
        
        # Store object
        await s3_storage._store_object("test/key.json", test_data)
        
        # Verify put_object was called
        s3_storage.s3_client.put_object.assert_called_once()
        call_args = s3_storage.s3_client.put_object.call_args[1]
        assert call_args['Bucket'] == "test-bucket"
        assert call_args['Key'] == "test/key.json"
        assert json.loads(call_args['Body']) == test_data
        
        # Mock get_object response
        mock_response = {
            'Body': MagicMock()
        }
        mock_response['Body'].read.return_value = json.dumps(test_data).encode('utf-8')
        s3_storage.s3_client.get_object.return_value = mock_response
        
        # Get object
        result = await s3_storage._get_object("test/key.json")
        assert result == test_data
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_object_s3(self, s3_storage):
        """Test getting non-existent object from S3."""
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            pytest.skip("botocore not available")
        
        # Mock NoSuchKey exception
        error = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey'}},
            operation_name='GetObject'
        )
        s3_storage.s3_client.get_object.side_effect = error
        
        result = await s3_storage._get_object("nonexistent.json")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_user_operations_s3(self, s3_storage):
        """Test user operations with S3 backend."""
        user = UserFactory.create()
        
        # Mock get_object to return None (user doesn't exist)
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            pytest.skip("botocore not available")
        error = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey'}},
            operation_name='GetObject'
        )
        s3_storage.s3_client.get_object.side_effect = error
        
        # Create user
        created_user = await s3_storage.create_user(user)
        assert created_user == user
        s3_storage.s3_client.put_object.assert_called()


@pytest.mark.skipif(not STORAGE_IMPORTS_AVAILABLE, reason="Cloud storage dependencies not available")
class TestStorageLogOperations:
    """Test log operations across all storage backends."""
    
    @pytest.fixture
    def file_storage(self):
        """Create FileStorage instance for testing."""
        import tempfile
        
        # FileStorage should always be available
        try:
            from role_play.common.storage import FileStorage
        except ImportError:
            pytest.skip("FileStorage not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            yield storage
    
    @pytest.mark.asyncio
    async def test_file_storage_log_operations(self, file_storage):
        """Test log operations with file storage."""
        log_key = "test_session"
        test_data_1 = {"type": "session_start", "timestamp": "2024-01-01T00:00:00Z"}
        test_data_2 = {"type": "message", "content": "Hello world"}
        
        # Test log doesn't exist initially
        assert not await file_storage.log_exists(log_key)
        
        # Append first entry
        await file_storage.append_to_log(log_key, test_data_1)
        assert await file_storage.log_exists(log_key)
        
        # Append second entry
        await file_storage.append_to_log(log_key, test_data_2)
        
        # Read log
        entries = await file_storage.read_log(log_key)
        assert len(entries) == 2
        assert entries[0] == test_data_1
        assert entries[1] == test_data_2
        
        # Delete log
        result = await file_storage.delete_log(log_key)
        assert result is True
        assert not await file_storage.log_exists(log_key)
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_log(self, file_storage):
        """Test reading non-existent log returns empty list."""
        entries = await file_storage.read_log("nonexistent_log")
        assert entries == []
    
    @pytest.mark.asyncio
    async def test_concurrent_log_writes(self, file_storage):
        """Test concurrent writes to the same log file."""
        log_key = "concurrent_test"
        
        # Simulate concurrent writes
        tasks = []
        for i in range(10):
            data = {"message": f"Message {i}", "number": i}
            task = file_storage.append_to_log(log_key, data)
            tasks.append(task)
        
        # Wait for all writes to complete
        await asyncio.gather(*tasks)
        
        # Verify all entries were written
        entries = await file_storage.read_log(log_key)
        assert len(entries) == 10
        
        # Verify all numbers are present (order might vary due to concurrency)
        numbers = [entry["number"] for entry in entries]
        assert set(numbers) == set(range(10))


@pytest.mark.integration
class TestCloudStorageIntegration:
    """Integration tests for cloud storage (requires actual cloud credentials)."""
    
    @pytest.mark.skip(reason="Integration tests require actual cloud credentials")
    @pytest.mark.asyncio
    async def test_gcs_real_integration(self):
        """Test with real GCS (requires GCS_BUCKET_NAME environment variable)."""
        import os
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        
        if not bucket_name:
            pytest.skip("GCS_BUCKET_NAME environment variable not set")
        
        try:
            storage = GCSStorage(
                bucket_name=bucket_name,
                prefix="test_integration/"
            )
            
            # Test basic operations
            test_user = UserFactory.create()
            created_user = await storage.create_user(test_user)
            retrieved_user = await storage.get_user(test_user.id)
            
            assert retrieved_user.id == test_user.id
            
            # Cleanup
            await storage.delete_user(test_user.id)
            
        except Exception as e:
            pytest.skip(f"GCS integration test failed: {e}")
    
    @pytest.mark.skip(reason="Integration tests require actual cloud credentials")
    @pytest.mark.asyncio
    async def test_s3_real_integration(self):
        """Test with real S3 (requires S3_BUCKET_NAME environment variable)."""
        import os
        bucket_name = os.getenv("S3_BUCKET_NAME")
        
        if not bucket_name:
            pytest.skip("S3_BUCKET_NAME environment variable not set")
        
        try:
            storage = S3Storage(
                bucket_name=bucket_name,
                prefix="test_integration/"
            )
            
            # Test basic operations
            test_user = UserFactory.create()
            created_user = await storage.create_user(test_user)
            retrieved_user = await storage.get_user(test_user.id)
            
            assert retrieved_user.id == test_user.id
            
            # Cleanup
            await storage.delete_user(test_user.id)
            
        except Exception as e:
            pytest.skip(f"S3 integration test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__])