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

    # New tests for read-only session history functionality

    @pytest.mark.asyncio
    async def test_get_session_end_info_active_session(self, chat_logger, mock_storage):
        """Test getting session end info for an active session."""
        user_id = "test_user"
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Alice",
            scenario_id="s1",
            scenario_name="Test Scenario",
            character_id="c1",
            character_name="Test Character"
        )

        # Get session end info for active session
        end_info = await chat_logger.get_session_end_info(user_id, app_session_id)
        
        # Should return empty dict for active session
        assert end_info == {}

    @pytest.mark.asyncio
    async def test_get_session_end_info_ended_session(self, chat_logger, mock_storage):
        """Test getting session end info for an ended session."""
        user_id = "test_user"
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Bob",
            scenario_id="s2",
            scenario_name="Test Scenario 2",
            character_id="c2",
            character_name="Test Character 2"
        )

        # End the session
        await chat_logger.end_session(
            user_id=user_id,
            session_id=app_session_id,
            total_messages=3,
            duration_seconds=150.0,
            reason="User ended session",
            final_state={"last_action": "completed_task"}
        )

        # Get session end info
        end_info = await chat_logger.get_session_end_info(user_id, app_session_id)
        
        assert end_info["total_messages"] == 3
        assert end_info["duration_seconds"] == 150.0
        assert end_info["reason"] == "User ended session"
        assert "ended_at" in end_info

    @pytest.mark.asyncio
    async def test_get_session_end_info_nonexistent_session(self, chat_logger):
        """Test getting session end info for a session that doesn't exist."""
        end_info = await chat_logger.get_session_end_info("fake_user", "fake_session_id")
        assert end_info == {}

    @pytest.mark.asyncio
    async def test_get_session_messages_with_messages(self, chat_logger, mock_storage):
        """Test getting session messages when messages exist."""
        user_id = "test_user"
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Charlie",
            scenario_id="s3",
            scenario_name="Message Test",
            character_id="c3",
            character_name="Test Character 3"
        )

        # Log some messages
        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="participant",
            content="Hello there!",
            message_number=1
        )

        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="character",
            content="Hello! How can I help you?",
            message_number=2
        )

        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="participant",
            content="I need some assistance.",
            message_number=3
        )

        # Get messages
        messages = await chat_logger.get_session_messages(user_id, app_session_id)
        
        assert len(messages) == 3
        
        # Check first message
        assert messages[0]["role"] == "participant"
        assert messages[0]["content"] == "Hello there!"
        assert messages[0]["message_number"] == 1
        assert "timestamp" in messages[0]
        
        # Check second message
        assert messages[1]["role"] == "character"
        assert messages[1]["content"] == "Hello! How can I help you?"
        assert messages[1]["message_number"] == 2
        
        # Check third message
        assert messages[2]["role"] == "participant"
        assert messages[2]["content"] == "I need some assistance."
        assert messages[2]["message_number"] == 3

    @pytest.mark.asyncio
    async def test_get_session_messages_empty_session(self, chat_logger, mock_storage):
        """Test getting messages from a session with no messages."""
        user_id = "test_user"
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="David",
            scenario_id="s4",
            scenario_name="Empty Test",
            character_id="c4",
            character_name="Test Character 4"
        )

        # Get messages (should be empty)
        messages = await chat_logger.get_session_messages(user_id, app_session_id)
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_session_messages_nonexistent_session(self, chat_logger):
        """Test getting messages from a session that doesn't exist."""
        with pytest.raises(StorageError):
            await chat_logger.get_session_messages("fake_user", "fake_session_id")

    @pytest.mark.asyncio
    async def test_get_session_messages_with_malformed_json(self, chat_logger, mock_storage):
        """Test getting messages when JSONL contains malformed JSON lines."""
        user_id = "test_user"
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Eve",
            scenario_id="s5",
            scenario_name="Malformed Test",
            character_id="c5",
            character_name="Test Character 5"
        )

        # Log a valid message
        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="participant",
            content="Valid message",
            message_number=1
        )

        # Manually corrupt the JSONL file by adding malformed JSON
        storage_path = f"users/{user_id}/chat_logs/{app_session_id}"
        current_content = await mock_storage.read(storage_path)
        corrupted_content = current_content + "\n{invalid json line}\n"
        await mock_storage.write(storage_path, corrupted_content)

        # Log another valid message
        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="character",
            content="Another valid message",
            message_number=2
        )

        # Get messages - should only return valid ones
        messages = await chat_logger.get_session_messages(user_id, app_session_id)
        
        assert len(messages) == 2
        assert messages[0]["content"] == "Valid message"
        assert messages[1]["content"] == "Another valid message"

    @pytest.mark.asyncio
    async def test_delete_session_existing_session(self, chat_logger, mock_storage):
        """Test deleting an existing session."""
        user_id = "test_user"
        app_session_id, storage_path = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Frank",
            scenario_id="s6",
            scenario_name="Delete Test",
            character_id="c6",
            character_name="Test Character 6"
        )

        # Verify session exists
        assert await mock_storage.exists(storage_path)

        # Delete the session
        await chat_logger.delete_session(user_id, app_session_id)
        
        # Verify session is deleted
        assert not await mock_storage.exists(storage_path)

    @pytest.mark.asyncio
    async def test_delete_session_nonexistent_session(self, chat_logger):
        """Test deleting a session that doesn't exist (should not raise error)."""
        # Should complete without raising an error
        await chat_logger.delete_session("fake_user", "fake_session_id")

    @pytest.mark.asyncio
    async def test_delete_session_with_messages(self, chat_logger, mock_storage):
        """Test deleting a session that contains messages."""
        user_id = "test_user"
        app_session_id, storage_path = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Grace",
            scenario_id="s7",
            scenario_name="Delete Messages Test",
            character_id="c7",
            character_name="Test Character 7"
        )

        # Add some messages
        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="participant",
            content="Message to be deleted",
            message_number=1
        )

        await chat_logger.end_session(
            user_id=user_id,
            session_id=app_session_id,
            total_messages=1,
            duration_seconds=30.0
        )

        # Verify session exists with content
        assert await mock_storage.exists(storage_path)
        content = await mock_storage.read(storage_path)
        assert "Message to be deleted" in content

        # Delete the session
        await chat_logger.delete_session(user_id, app_session_id)
        
        # Verify session is completely deleted
        assert not await mock_storage.exists(storage_path)

    @pytest.mark.asyncio
    async def test_session_messages_ordering(self, chat_logger, mock_storage):
        """Test that session messages are returned in the correct order."""
        user_id = "test_user"
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Henry",
            scenario_id="s8",
            scenario_name="Order Test",
            character_id="c8",
            character_name="Test Character 8"
        )

        # Log messages in specific order
        for i in range(5):
            role = "participant" if i % 2 == 0 else "character"
            await chat_logger.log_message(
                user_id=user_id,
                session_id=app_session_id,
                role=role,
                content=f"Message {i+1}",
                message_number=i+1
            )

        # Get messages
        messages = await chat_logger.get_session_messages(user_id, app_session_id)
        
        # Verify order and content
        assert len(messages) == 5
        for i, message in enumerate(messages):
            assert message["content"] == f"Message {i+1}"
            assert message["message_number"] == i+1
            expected_role = "participant" if i % 2 == 0 else "character"
            assert message["role"] == expected_role

    @pytest.mark.asyncio
    async def test_read_only_session_history_integration(self, chat_logger, mock_storage):
        """Integration test for the complete read-only session history workflow."""
        user_id = "integration_user"
        
        # 1. Start session
        app_session_id, _ = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Integration Test User",
            scenario_id="integration_scenario",
            scenario_name="Integration Test Scenario",
            character_id="integration_character",
            character_name="Integration Test Character",
            goal="Test complete workflow"
        )
        
        # 2. Add conversation messages
        conversation = [
            ("participant", "Hello, I need help with integration testing."),
            ("character", "I'd be happy to help you with integration testing!"),
            ("participant", "Can you explain the read-only session feature?"),
            ("character", "The read-only feature allows users to view historical sessions without editing them."),
            ("participant", "That's very helpful, thank you!")
        ]
        
        for i, (role, content) in enumerate(conversation, 1):
            await chat_logger.log_message(
                user_id=user_id,
                session_id=app_session_id,
                role=role,
                content=content,
                message_number=i
            )
        
        # 3. End session
        await chat_logger.end_session(
            user_id=user_id,
            session_id=app_session_id,
            total_messages=len(conversation),
            duration_seconds=245.5,
            reason="Integration test completed",
            final_state={"test_status": "passed"}
        )
        
        # 4. Test session end info retrieval
        end_info = await chat_logger.get_session_end_info(user_id, app_session_id)
        assert end_info["total_messages"] == 5
        assert end_info["duration_seconds"] == 245.5
        assert end_info["reason"] == "Integration test completed"
        assert "ended_at" in end_info
        
        # 5. Test message history retrieval
        messages = await chat_logger.get_session_messages(user_id, app_session_id)
        assert len(messages) == 5
        
        # Verify conversation content
        for i, (expected_role, expected_content) in enumerate(conversation):
            assert messages[i]["role"] == expected_role
            assert messages[i]["content"] == expected_content
            assert messages[i]["message_number"] == i + 1
        
        # 6. Test export functionality
        export_text = await chat_logger.export_session_text(user_id, app_session_id)
        assert "Integration Test User" in export_text
        assert "Integration Test Scenario" in export_text
        assert "Integration Test Character" in export_text
        assert "Hello, I need help with integration testing." in export_text
        assert "SESSION ENDED" in export_text
        assert "Total Messages: 5" in export_text
        
        # 7. Test session deletion
        await chat_logger.delete_session(user_id, app_session_id)
        
        # Verify session is gone
        storage_path = f"users/{user_id}/chat_logs/{app_session_id}"
        assert not await mock_storage.exists(storage_path)
        
        # Verify operations on deleted session
        end_info_after_delete = await chat_logger.get_session_end_info(user_id, app_session_id)
        assert end_info_after_delete == {}
        
        with pytest.raises(StorageError):
            await chat_logger.get_session_messages(user_id, app_session_id)

    @pytest.mark.asyncio
    async def test_export_session_json_format_with_content_loader(self, mock_storage):
        """Test JSON export functionality with content_loader providing complete data."""
        # Create mock content loader
        from unittest.mock import MagicMock
        mock_content_loader = MagicMock()
        
        # Mock scenario and character data
        mock_content_loader.get_scenario_by_id.return_value = {
            "id": "scenario_1",
            "name": "Test Scenario",
            "description": "A test scenario for evaluation"
        }
        mock_content_loader.get_character_by_id.return_value = {
            "id": "char_1", 
            "name": "Test Character",
            "description": "A test character for evaluation"
        }
        
        chat_logger = ChatLogger(mock_storage, content_loader=mock_content_loader)
        
        # Start a session
        user_id = "test_user_json"
        app_session_id, storage_path = await chat_logger.start_session(
            user_id=user_id,
            participant_name="Test Participant",
            scenario_id="scenario_1", 
            scenario_name="Test Scenario",
            character_id="char_1",
            character_name="Test Character",
            goal="Test JSON export functionality",
            session_language="en"
        )
        
        # Add some messages
        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="participant",
            content="Hello, how are you?",
            message_number=1
        )
        
        await chat_logger.log_message(
            user_id=user_id,
            session_id=app_session_id,
            role="character",
            content="I'm doing well, thank you!",
            message_number=2
        )
        
        # Export as JSON
        json_export = await chat_logger.export_session_text(user_id, app_session_id, export_format="json")
        
        # Parse the JSON
        import json
        chat_info = json.loads(json_export)
        
        # Verify the structure
        assert chat_info["chat_session_id"] == app_session_id
        assert chat_info["chat_language"] == "English"  # Mapped from "en"
        assert chat_info["participant_name"] == "Test Participant"
        assert chat_info["goal"] == "Test JSON export functionality"
        
        # Verify scenario info includes description from content_loader
        assert chat_info["scenario_info"]["id"] == "scenario_1"
        assert chat_info["scenario_info"]["name"] == "Test Scenario"
        assert chat_info["scenario_info"]["description"] == "A test scenario for evaluation"
        
        # Verify character info includes description from content_loader
        assert chat_info["char_info"]["id"] == "char_1"
        assert chat_info["char_info"]["name"] == "Test Character"
        assert chat_info["char_info"]["description"] == "A test character for evaluation"
        
        # Verify transcript
        expected_transcript = "Test Participant: Hello, how are you?\nTest Character: I'm doing well, thank you!"
        assert chat_info["transcript_text"] == expected_transcript
        
        # Verify content_loader was called with correct parameters
        mock_content_loader.get_scenario_by_id.assert_called_with("scenario_1", "en")
        mock_content_loader.get_character_by_id.assert_called_with("char_1", "en")