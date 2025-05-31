"""Unit tests for ChatLogger service."""
import pytest
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

# Add fixtures to path
sys.path.append(str(Path(__file__).parent.parent.parent))
from fixtures.helpers import MockStorageBackend

from role_play.chat.chat_logger import ChatLogger
from role_play.common.exceptions import StorageError


class TestChatLogger:
    """Test cases for ChatLogger."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage backend."""
        return MockStorageBackend()

    @pytest.fixture
    def chat_logger(self, mock_storage):
        """Create a ChatLogger instance with mock storage."""
        return ChatLogger(mock_storage)

    @pytest.mark.asyncio
    async def test_init_creates_chat_logger(self, mock_storage):
        """Test that ChatLogger initializes with storage backend."""
        logger = ChatLogger(mock_storage)
        assert logger.storage == mock_storage

    @pytest.mark.asyncio
    async def test_start_session_creates_jsonl_entry(self, chat_logger, mock_storage):
        """Test that start_session creates a JSONL entry with session_start event."""
        user_id = "test_user_123"
        app_session_id, storage_path = await chat_logger.start_session(
            user_id=user_id,
            participant_name="John Doe",
            scenario_id="scenario_1",
            scenario_name="Test Scenario",
            character_id="char_1",
            character_name="Test Character",
            goal="Test the system",
            initial_settings={"setting1": "value1"}
        )

        assert app_session_id
        assert storage_path == f"users/{user_id}/chat_logs/{app_session_id}"
        
        # Verify the session_start event was written
        stored_data = await mock_storage.read(storage_path)
        event = json.loads(stored_data.strip())
        
        assert event["type"] == "session_start"
        assert event["app_session_id"] == app_session_id
        assert event["user_id"] == user_id
        assert event["participant_name"] == "John Doe"
        assert event["scenario_id"] == "scenario_1"
        assert event["goal"] == "Test the system"
        assert event["initial_settings"] == {"setting1": "value1"}

    @pytest.mark.asyncio
    async def test_log_message(self, chat_logger, mock_storage):
        """Test logging messages to a session."""
        # Start a session
        user_id = "test_user"
        app_session_id, storage_path = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Jane",
            scenario_id="s1",
            scenario_name="Scenario 1",
            character_id="c1",
            character_name="Character 1"
        )

        # Log messages
        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="participant",
            content="Hello!",
            message_number=1,
            metadata={"emotion": "happy"}
        )

        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="character",
            content="Hi there!",
            message_number=2
        )

        # Verify messages were logged
        stored_data = await mock_storage.read(storage_path)
        lines = stored_data.strip().split('\n')
        assert len(lines) == 3  # session_start + 2 messages

        # Check first message
        msg1 = json.loads(lines[1])
        assert msg1["type"] == "message"
        assert msg1["role"] == "participant"
        assert msg1["content"] == "Hello!"
        assert msg1["message_number"] == 1
        assert msg1["metadata"]["emotion"] == "happy"

        # Check second message
        msg2 = json.loads(lines[2])
        assert msg2["type"] == "message"
        assert msg2["role"] == "character"
        assert msg2["content"] == "Hi there!"
        assert msg2["message_number"] == 2

    @pytest.mark.asyncio
    async def test_log_message_file_not_found(self, chat_logger):
        """Test that log_message raises error if session doesn't exist."""
        with pytest.raises(StorageError) as exc_info:
            await chat_logger.log_message(
                user_id="fake_user",
                session_id="fake_id",
                role="participant",
                content="Test",
                message_number=1
            )
        
        assert "Session log file not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_end_session(self, chat_logger, mock_storage):
        """Test ending a session."""
        # Start a session
        user_id = "test_user"
        app_session_id, storage_path = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Bob",
            scenario_id="s2",
            scenario_name="Scenario 2",
            character_id="c2",
            character_name="Character 2"
        )

        # End the session
        await chat_logger.end_session(
            user_id=user_id,
            session_id=app_session_id,
            total_messages=5,
            duration_seconds=120.5,
            reason="User closed window",
            final_state={"last_topic": "weather"}
        )

        # Verify session_end event
        stored_data = await mock_storage.read(storage_path)
        lines = stored_data.strip().split('\n')
        last_line = json.loads(lines[-1])
        
        assert last_line["type"] == "session_end"
        assert last_line["total_messages"] == 5
        assert last_line["duration_seconds"] == 120.5
        assert last_line["reason"] == "User closed window"
        assert last_line["final_state"]["last_topic"] == "weather"

    @pytest.mark.asyncio
    async def test_list_user_sessions(self, chat_logger, mock_storage):
        """Test listing sessions for a user."""
        user_id = "test_user"
        
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            app_session_id, _ = await chat_logger.start_session(
                user_id=user_id,
                participant_name=f"User{i}",
                scenario_id=f"s{i}",
                scenario_name=f"Scenario {i}",
                character_id=f"c{i}",
                character_name=f"Character {i}"
            )
            session_ids.append(app_session_id)

        # List sessions
        sessions = await chat_logger.list_user_sessions(user_id)
        
        assert len(sessions) == 3
        # Should be sorted by created_at (newest first)
        for i, session in enumerate(sessions):
            assert session["user_id"] == user_id
            assert session["session_id"] in session_ids
            assert session["message_count"] == 0  # No messages logged

    @pytest.mark.asyncio
    async def test_export_session_text(self, chat_logger, mock_storage):
        """Test exporting a session as text."""
        # Create a complete session
        user_id = "test_user"
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Alice",
            scenario_id="s1",
            scenario_name="Customer Service",
            character_id="c1",
            character_name="Support Agent - Friendly"
        )

        # Log some messages
        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="participant",
            content="I need help with my order",
            message_number=1
        )

        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="character",
            content="I'd be happy to help you with your order!",
            message_number=2
        )

        # End session
        await chat_logger.end_session(
            user_id=user_id,
            session_id=app_session_id,
            total_messages=2,
            duration_seconds=60.0
        )

        # Export as text
        text = await chat_logger.export_session_text(user_id, app_session_id)
        
        assert "ROLEPLAY SESSION TRANSCRIPT" in text
        assert "Alice" in text
        assert "Customer Service" in text
        assert "Support Agent" in text
        assert "I need help with my order" in text
        assert "I'd be happy to help you with your order!" in text
        assert "SESSION ENDED" in text
        assert "Total Messages: 2" in text

    @pytest.mark.asyncio
    async def test_export_nonexistent_session(self, chat_logger):
        """Test exporting a session that doesn't exist."""
        text = await chat_logger.export_session_text("fake_user", "nonexistent_id")
        assert text == "Session log file not found."

    @pytest.mark.asyncio
    async def test_concurrent_writes_to_same_session(self, chat_logger, mock_storage):
        """Test that concurrent writes to the same session are handled correctly."""
        # Start a session
        user_id = "test_user"
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="ConcurrentUser",
            scenario_id="s1",
            scenario_name="Concurrent Test",
            character_id="c1",
            character_name="Test Character"
        )

        # Function to write a message asynchronously
        async def write_message(msg_num):
            await chat_logger.log_message(
                user_id=user_id,
                session_id=app_session_id,
                role="participant",
                content=f"Message {msg_num}",
                message_number=msg_num
            )

        # Write 10 messages concurrently
        tasks = [write_message(i) for i in range(1, 11)]
        await asyncio.gather(*tasks)

        # Verify all messages were written
        storage_path = f"users/{user_id}/chat_logs/{app_session_id}"
        stored_data = await mock_storage.read(storage_path)
        lines = stored_data.strip().split('\n')
        
        # Should have session_start + 10 messages
        assert len(lines) == 11
        
        # Extract message numbers
        message_numbers = []
        for line in lines[1:]:  # Skip session_start
            event = json.loads(line)
            if event["type"] == "message":
                message_numbers.append(event["message_number"])
        
        # All messages should be present
        assert sorted(message_numbers) == list(range(1, 11))

    @pytest.mark.asyncio
    async def test_async_concurrent_operations(self, chat_logger):
        """Test async concurrent operations on different sessions."""
        async def create_and_use_session(user_num):
            user_id = f"user_{user_num}"
            app_session_id, _ = await chat_logger.start_session(
                user_id=user_id,
                participant_name=f"User {user_num}",
                scenario_id="s1",
                scenario_name="Async Test",
                character_id="c1",
                character_name="Test Character"
            )
            
            # Log a few messages
            for i in range(3):
                await chat_logger.log_message(
                    user_id=user_id,
                    session_id=app_session_id,
                    role="participant" if i % 2 == 0 else "character",
                    content=f"Message {i} from user {user_num}",
                    message_number=i + 1
                )
            
            return user_id, app_session_id

        # Create 5 sessions concurrently
        tasks = [create_and_use_session(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Verify each session
        for user_id, session_id in results:
            sessions = await chat_logger.list_user_sessions(user_id)
            assert len(sessions) == 1
            assert sessions[0]["session_id"] == session_id
            assert sessions[0]["message_count"] == 3