"""Unit tests for ChatLogger with storage backend integration."""

import pytest
import asyncio
import json
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from role_play.chat.chat_logger import ChatLogger
from role_play.common.storage import FileStorage, StorageBackend
from role_play.common.exceptions import StorageError

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from fixtures.helpers import MockStorageBackend


class TestChatLoggerStorageIntegration:
    """Test ChatLogger with different storage backends."""
    
    @pytest.fixture
    def mock_storage_backend(self):
        """Create a mock storage backend."""
        storage = AsyncMock(spec=StorageBackend)
        storage.append_to_log = AsyncMock()
        storage.read_log = AsyncMock(return_value=[])
        storage.log_exists = AsyncMock(return_value=False)
        storage.delete_log = AsyncMock(return_value=True)
        return storage
    
    @pytest.fixture
    def chat_logger(self, mock_storage_backend):
        """Create ChatLogger with mock storage."""
        return ChatLogger(storage_backend=mock_storage_backend)
    
    @pytest.fixture
    def file_storage_logger(self):
        """Create ChatLogger with real FileStorage for integration testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            logger = ChatLogger(storage_backend=storage)
            yield logger
    
    def test_chat_logger_initialization(self, mock_storage_backend):
        """Test ChatLogger initialization with storage backend."""
        logger = ChatLogger(storage_backend=mock_storage_backend)
        assert logger.storage == mock_storage_backend
    
    @pytest.mark.asyncio
    async def test_start_session(self, chat_logger, mock_storage_backend):
        """Test starting a chat session."""
        session_id = await chat_logger.start_session(
            user_id="test_user",
            participant_name="John Doe",
            scenario_id="scenario_1",
            scenario_name="Test Scenario",
            character_id="char_1",
            character_name="Test Character",
            goal="Test the system"
        )
        
        # Verify session ID is generated
        assert session_id is not None
        assert len(session_id) > 0
        
        # Verify storage was called
        mock_storage_backend.append_to_log.assert_called_once()
        
        # Check the logged event
        call_args = mock_storage_backend.append_to_log.call_args
        log_key = call_args[0][0]
        event_data = call_args[0][1]
        
        assert log_key == f"chat_sessions/test_user_{session_id}"
        assert event_data["type"] == "session_start"
        assert event_data["app_session_id"] == session_id
        assert event_data["user_id"] == "test_user"
        assert event_data["participant_name"] == "John Doe"
        assert event_data["scenario_name"] == "Test Scenario"
        assert event_data["character_name"] == "Test Character"
        assert event_data["goal"] == "Test the system"
        assert "timestamp" in event_data
        assert "version" in event_data
    
    @pytest.mark.asyncio
    async def test_log_message(self, chat_logger, mock_storage_backend):
        """Test logging a message."""
        session_id = "test_session_123"
        user_id = "test_user"
        
        await chat_logger.log_message(
            session_id=session_id,
            user_id=user_id,
            role="participant",
            content="Hello, world!",
            message_number=1,
            metadata={"test": "data"}
        )
        
        # Verify storage was called
        mock_storage_backend.append_to_log.assert_called_once()
        
        # Check the logged event
        call_args = mock_storage_backend.append_to_log.call_args
        log_key = call_args[0][0]
        event_data = call_args[0][1]
        
        assert log_key == f"chat_sessions/{user_id}_{session_id}"
        assert event_data["type"] == "message"
        assert event_data["app_session_id"] == session_id
        assert event_data["role"] == "participant"
        assert event_data["content"] == "Hello, world!"
        assert event_data["message_number"] == 1
        assert event_data["metadata"] == {"test": "data"}
        assert "timestamp" in event_data
    
    @pytest.mark.asyncio
    async def test_end_session(self, chat_logger, mock_storage_backend):
        """Test ending a chat session."""
        session_id = "test_session_123"
        user_id = "test_user"
        
        await chat_logger.end_session(
            session_id=session_id,
            user_id=user_id,
            total_messages=5,
            duration_seconds=123.45,
            reason="Normal completion",
            final_state={"status": "completed"}
        )
        
        # Verify storage was called
        mock_storage_backend.append_to_log.assert_called_once()
        
        # Check the logged event
        call_args = mock_storage_backend.append_to_log.call_args
        log_key = call_args[0][0]
        event_data = call_args[0][1]
        
        assert log_key == f"chat_sessions/{user_id}_{session_id}"
        assert event_data["type"] == "session_end"
        assert event_data["app_session_id"] == session_id
        assert event_data["total_messages"] == 5
        assert event_data["duration_seconds"] == 123.45
        assert event_data["reason"] == "Normal completion"
        assert event_data["final_state"] == {"status": "completed"}
        assert "timestamp" in event_data
    
    @pytest.mark.asyncio
    async def test_export_session_text(self, chat_logger, mock_storage_backend):
        """Test exporting session as text."""
        session_id = "test_session_123"
        user_id = "test_user"
        
        # Mock log data
        mock_log_data = [
            {
                "type": "session_start",
                "timestamp": "2024-01-01T00:00:00Z",
                "app_session_id": session_id,
                "user_id": user_id,
                "participant_name": "John Doe",
                "scenario_name": "Test Scenario",
                "character_name": "Test Character",
                "goal": "Test goal"
            },
            {
                "type": "message",
                "timestamp": "2024-01-01T00:01:00Z",
                "app_session_id": session_id,
                "role": "participant",
                "content": "Hello!",
                "message_number": 1
            },
            {
                "type": "message",
                "timestamp": "2024-01-01T00:01:30Z",
                "app_session_id": session_id,
                "role": "character",
                "content": "Hi there!",
                "message_number": 2
            },
            {
                "type": "session_end",
                "timestamp": "2024-01-01T00:02:00Z",
                "app_session_id": session_id,
                "total_messages": 2,
                "duration_seconds": 120.0,
                "reason": "Normal completion"
            }
        ]
        
        mock_storage_backend.log_exists.return_value = True
        mock_storage_backend.read_log.return_value = mock_log_data
        
        transcript = await chat_logger.export_session_text(session_id, user_id)
        
        # Verify storage was called
        mock_storage_backend.log_exists.assert_called_once_with(f"chat_sessions/{user_id}_{session_id}")
        mock_storage_backend.read_log.assert_called_once_with(f"chat_sessions/{user_id}_{session_id}")
        
        # Check transcript content
        assert "ROLEPLAY SESSION TRANSCRIPT" in transcript
        assert session_id in transcript
        assert "John Doe" in transcript
        assert "Test Scenario" in transcript
        assert "Test Character" in transcript
        assert "Hello!" in transcript
        assert "Hi there!" in transcript
        assert "SESSION ENDED" in transcript
        assert "Total Messages: 2" in transcript
        assert "Duration: 120.0 seconds" in transcript
    
    @pytest.mark.asyncio
    async def test_export_nonexistent_session(self, chat_logger, mock_storage_backend):
        """Test exporting non-existent session."""
        mock_storage_backend.log_exists.return_value = False
        
        transcript = await chat_logger.export_session_text("nonexistent", "test_user")
        
        assert "Session log file not found" in transcript
    
    @pytest.mark.asyncio
    async def test_list_user_sessions_warning(self, chat_logger, mock_storage_backend):
        """Test that list_user_sessions shows warning for cloud storage."""
        sessions = await chat_logger.list_user_sessions("test_user")
        
        # Should return empty list and log warning
        assert sessions == []
    
    @pytest.mark.asyncio
    async def test_storage_error_handling(self, chat_logger, mock_storage_backend):
        """Test error handling when storage operations fail."""
        mock_storage_backend.append_to_log.side_effect = StorageError("Storage failed")
        
        with pytest.raises(StorageError, match="Storage failed"):
            await chat_logger.start_session(
                user_id="test_user",
                participant_name="John",
                scenario_id="scenario_1",
                scenario_name="Test",
                character_id="char_1",
                character_name="Character"
            )


class TestChatLoggerFileStorageIntegration:
    """Integration tests with real FileStorage."""
    
    @pytest.mark.asyncio
    async def test_complete_session_flow(self):
        """Test complete session flow with real FileStorage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            logger = ChatLogger(storage_backend=storage)
            
            # Start session
            session_id = await logger.start_session(
                user_id="integration_user",
                participant_name="Integration Test",
                scenario_id="scenario_1",
                scenario_name="Integration Scenario",
                character_id="char_1",
                character_name="Integration Character"
            )
            
            # Log some messages
            await logger.log_message(session_id, "integration_user", "participant", "Hello!", 1)
            await logger.log_message(session_id, "integration_user", "character", "Hi there!", 2)
            await logger.log_message(session_id, "integration_user", "participant", "How are you?", 3)
            
            # End session
            await logger.end_session(session_id, "integration_user", 3, 60.0, "Test complete")
            
            # Export session
            transcript = await logger.export_session_text(session_id, "integration_user")
            
            # Verify transcript
            assert "Integration Test" in transcript
            assert "Integration Scenario" in transcript
            assert "Hello!" in transcript
            assert "Hi there!" in transcript
            assert "How are you?" in transcript
            assert "SESSION ENDED" in transcript
            assert "Total Messages: 3" in transcript
            
            # Verify log file exists in storage
            log_key = f"chat_sessions/integration_user_{session_id}"
            assert await storage.log_exists(log_key)
            
            # Read raw log data
            entries = await storage.read_log(log_key)
            assert len(entries) == 5  # start + 3 messages + end
            assert entries[0]["type"] == "session_start"
            assert entries[1]["type"] == "message"
            assert entries[2]["type"] == "message"
            assert entries[3]["type"] == "message"
            assert entries[4]["type"] == "session_end"
    
    @pytest.mark.asyncio
    async def test_concurrent_message_logging(self):
        """Test concurrent message logging with FileStorage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FileStorage(temp_dir)
            logger = ChatLogger(storage_backend=storage)
            
            # Start session
            session_id = await logger.start_session(
                user_id="concurrent_user",
                participant_name="Concurrent Test",
                scenario_id="scenario_1",
                scenario_name="Concurrent Scenario",
                character_id="char_1",
                character_name="Concurrent Character"
            )
            
            # Log messages concurrently
            tasks = []
            for i in range(10):
                task = logger.log_message(
                    session_id, "concurrent_user", "participant", f"Message {i}", i + 1
                )
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            # End session
            await logger.end_session(session_id, "concurrent_user", 10, 30.0)
            
            # Verify all messages were logged
            log_key = f"chat_sessions/concurrent_user_{session_id}"
            entries = await storage.read_log(log_key)
            
            # Should have: start + 10 messages + end = 12 entries
            assert len(entries) == 12
            
            # Count message entries
            message_entries = [e for e in entries if e["type"] == "message"]
            assert len(message_entries) == 10
            
            # Verify all message numbers are present
            message_numbers = [e["message_number"] for e in message_entries]
            assert set(message_numbers) == set(range(1, 11))


if __name__ == "__main__":
    pytest.main([__file__])