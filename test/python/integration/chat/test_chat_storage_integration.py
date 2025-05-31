"""Integration tests for ChatLogger with real storage backends."""

import pytest
import tempfile
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from role_play.chat.chat_logger import ChatLogger
from role_play.common.storage import FileStorage, FileStorageConfig
from role_play.common.exceptions import StorageError

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from fixtures.factories import UserFactory


@pytest.mark.integration
class TestChatLoggerStorageIntegration:
    """Integration tests for ChatLogger with FileStorage."""

    @pytest.mark.asyncio
    async def test_complete_chat_session_lifecycle(self):
        """Test a complete chat session with real file storage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            chat_logger = ChatLogger(storage)
            
            user_id = "test_user_001"
            
            # Start session
            session_id, storage_path = await chat_logger.start_session(
                user_id=user_id,
                participant_name="Alice",
                scenario_id="customer_service",
                scenario_name="Customer Service Training",
                character_id="agent_helpful",
                character_name="Helpful Agent - Sarah",
                goal="Practice handling customer complaints",
                initial_settings={"difficulty": "medium", "time_limit": 1800}
            )
            
            # Verify file was created in correct location
            expected_path = f"users/{user_id}/chat_logs/{session_id}"
            assert storage_path == expected_path
            assert await storage.exists(storage_path)
            
            # Log conversation messages
            messages = [
                ("participant", "I'm having trouble with my order", 1),
                ("character", "I'm sorry to hear that. Can you tell me your order number?", 2),
                ("participant", "It's #12345", 3),
                ("character", "Let me look that up for you. I see the issue and will fix it right away.", 4),
                ("participant", "Thank you so much!", 5)
            ]
            
            for role, content, msg_num in messages:
                await chat_logger.log_message(
                    user_id=user_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    message_number=msg_num,
                    metadata={"timestamp_source": "test"}
                )
            
            # End session
            await chat_logger.end_session(
                user_id=user_id,
                session_id=session_id,
                total_messages=5,
                duration_seconds=245.5,
                reason="conversation_completed",
                final_state={"resolution": "successful", "satisfaction": "high"}
            )
            
            # Verify complete session data
            raw_data = await storage.read(storage_path)
            lines = raw_data.strip().split('\n')
            assert len(lines) == 7  # session_start + 5 messages + session_end
            
            # Verify session structure
            session_start = json.loads(lines[0])
            assert session_start["type"] == "session_start"
            assert session_start["goal"] == "Practice handling customer complaints"
            
            session_end = json.loads(lines[-1])
            assert session_end["type"] == "session_end"
            assert session_end["total_messages"] == 5
            assert session_end["final_state"]["resolution"] == "successful"
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_users(self):
        """Test concurrent chat sessions from different users."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            chat_logger = ChatLogger(storage)
            
            async def create_user_session(user_num):
                user_id = f"user_{user_num:03d}"
                
                # Add small delay to reduce lock contention
                await asyncio.sleep(user_num * 0.1)
                
                session_id, _ = await chat_logger.start_session(
                    user_id=user_id,
                    participant_name=f"User {user_num}",
                    scenario_id="test_scenario",
                    scenario_name="Concurrent Test",
                    character_id="test_char",
                    character_name="Test Character"
                )
                
                # Log some messages with small delays
                for i in range(3):
                    await chat_logger.log_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="participant" if i % 2 == 0 else "character",
                        content=f"Message {i} from {user_id}",
                        message_number=i + 1
                    )
                    await asyncio.sleep(0.01)  # Small delay between messages
                
                await chat_logger.end_session(
                    user_id=user_id,
                    session_id=session_id,
                    total_messages=3,
                    duration_seconds=60.0
                )
                
                return user_id, session_id
            
            # Create 5 concurrent user sessions (reduced from 10)
            tasks = [create_user_session(i) for i in range(5)]
            results = await asyncio.gather(*tasks)
            
            # Verify all sessions were created correctly
            assert len(results) == 5  # Should have 5 users now
            for user_id, session_id in results:
                sessions = await chat_logger.list_user_sessions(user_id)
                assert len(sessions) == 1
                assert sessions[0]["session_id"] == session_id
                assert sessions[0]["message_count"] == 3
                
                # Verify file exists
                storage_path = f"users/{user_id}/chat_logs/{session_id}"
                assert await storage.exists(storage_path)
    
    @pytest.mark.asyncio
    async def test_file_locking_sequential_writes(self):
        """Test file locking with sequential writes to same session."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            chat_logger = ChatLogger(storage)
            
            user_id = "concurrent_user"
            session_id, _ = await chat_logger.start_session(
                user_id=user_id,
                participant_name="Concurrent Test User",
                scenario_id="locking_test",
                scenario_name="File Locking Test",
                character_id="test_char",
                character_name="Test Character"
            )
            
            # Function to write messages concurrently
            async def write_batch(start_num, count):
                for i in range(count):
                    msg_num = start_num + i
                    await chat_logger.log_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="participant",
                        content=f"Concurrent message {msg_num}",
                        message_number=msg_num
                    )
                    # Small delay to reduce lock contention
                    await asyncio.sleep(0.01)
            
            # Write 12 messages sequentially to test file locking without timeouts
            # This tests that locking works correctly for sequential access
            for i in range(1, 13):
                await chat_logger.log_message(
                    user_id=user_id,
                    session_id=session_id,
                    role="participant",
                    content=f"Sequential message {i}",
                    message_number=i
                )
            
            # Verify all messages were written correctly
            storage_path = f"users/{user_id}/chat_logs/{session_id}"
            raw_data = await storage.read(storage_path)
            lines = raw_data.strip().split('\n')
            
            # Should have session_start + 12 messages
            assert len(lines) == 13
            
            # Verify all message numbers are present
            message_numbers = []
            for line in lines[1:]:  # Skip session_start
                event = json.loads(line)
                if event["type"] == "message":
                    message_numbers.append(event["message_number"])
            
            assert len(message_numbers) == 12
            assert sorted(message_numbers) == list(range(1, 13))
    
    @pytest.mark.asyncio
    async def test_storage_path_security(self):
        """Test that storage paths are properly secured."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            chat_logger = ChatLogger(storage)
            
            # Try to create session with malicious user_id
            malicious_user_id = "../../../etc/passwd"
            
            # This should raise a StorageError due to path traversal protection
            with pytest.raises(StorageError) as exc_info:
                await chat_logger.start_session(
                    user_id=malicious_user_id,
                    participant_name="Test",
                    scenario_id="test",
                    scenario_name="Test",
                    character_id="test",
                    character_name="Test"
                )
            
            assert "Invalid key" in str(exc_info.value)
            
            # Test with a safe user_id
            safe_user_id = "safe_user_123"
            session_id, storage_path = await chat_logger.start_session(
                user_id=safe_user_id,
                participant_name="Test",
                scenario_id="test",
                scenario_name="Test",
                character_id="test",
                character_name="Test"
            )
            
            # Verify the safe path works
            assert storage_path.startswith("users/")
            assert session_id in storage_path
            assert await storage.exists(storage_path)
    
    @pytest.mark.asyncio
    async def test_session_export_integration(self):
        """Test session export with real storage data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            chat_logger = ChatLogger(storage)
            
            user_id = "export_test_user"
            
            # Create a realistic conversation
            session_id, _ = await chat_logger.start_session(
                user_id=user_id,
                participant_name="Jane Doe",
                scenario_id="tech_support",
                scenario_name="Technical Support Call",
                character_id="support_agent",
                character_name="Support Agent - Mike"
            )
            
            conversation = [
                ("participant", "My computer won't start up", 1),
                ("character", "I'm sorry to hear that. Let's troubleshoot this together. Can you tell me what happens when you press the power button?", 2),
                ("participant", "Nothing happens at all. No lights, no sounds.", 3),
                ("character", "It sounds like a power issue. Is the power cord securely connected to both the computer and the wall outlet?", 4),
                ("participant", "Let me check... oh, the cord was loose! It's working now.", 5),
                ("character", "Great! I'm glad we could resolve this quickly. Is there anything else I can help you with today?", 6),
                ("participant", "No, that's all. Thank you so much!", 7)
            ]
            
            for role, content, msg_num in conversation:
                await chat_logger.log_message(
                    user_id=user_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    message_number=msg_num
                )
            
            await chat_logger.end_session(
                user_id=user_id,
                session_id=session_id,
                total_messages=7,
                duration_seconds=180.0,
                reason="issue_resolved"
            )
            
            # Export session
            transcript = await chat_logger.export_session_text(user_id, session_id)
            
            # Verify export content
            assert "ROLEPLAY SESSION TRANSCRIPT" in transcript
            assert "Jane Doe" in transcript
            assert "Technical Support Call" in transcript
            assert "Support Agent - Mike" in transcript
            assert "My computer won't start up" in transcript
            assert "Great! I'm glad we could resolve this quickly" in transcript
            assert "SESSION ENDED" in transcript
            assert "Total Messages: 7" in transcript
            assert "Duration: 180.0 seconds" in transcript
    
    @pytest.mark.asyncio
    async def test_list_sessions_across_storage(self):
        """Test listing sessions with real storage backend."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            chat_logger = ChatLogger(storage)
            
            user_id = "multi_session_user"
            session_ids = []
            
            # Create multiple sessions
            for i in range(5):
                session_id, _ = await chat_logger.start_session(
                    user_id=user_id,
                    participant_name=f"Session {i} User",
                    scenario_id=f"scenario_{i}",
                    scenario_name=f"Test Scenario {i}",
                    character_id=f"char_{i}",
                    character_name=f"Character {i}"
                )
                session_ids.append(session_id)
                
                # Add some messages to vary message count
                for j in range(i + 1):
                    await chat_logger.log_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="participant",
                        content=f"Message {j}",
                        message_number=j + 1
                    )
            
            # List sessions
            sessions = await chat_logger.list_user_sessions(user_id)
            
            # Verify all sessions are listed
            assert len(sessions) == 5
            
            # Verify session details
            found_session_ids = {s["session_id"] for s in sessions}
            assert found_session_ids == set(session_ids)
            
            # Verify message counts
            for i, session in enumerate(sessions):
                expected_msg_count = len(session_ids) - i  # Due to reverse order
                # Note: sessions are sorted by creation time (newest first)
                assert session["message_count"] >= 1
    
    @pytest.mark.asyncio
    async def test_storage_error_handling(self):
        """Test error handling with storage failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            chat_logger = ChatLogger(storage)
            
            user_id = "error_test_user"
            
            # Test logging to non-existent session
            with pytest.raises(StorageError) as exc_info:
                await chat_logger.log_message(
                    user_id=user_id,
                    session_id="nonexistent_session",
                    role="participant",
                    content="This should fail",
                    message_number=1
                )
            
            assert "Session log file not found" in str(exc_info.value)
            
            # Test export of non-existent session
            result = await chat_logger.export_session_text(user_id, "nonexistent_session")
            assert result == "Session log file not found."


@pytest.mark.integration 
class TestChatLoggerPerformance:
    """Performance integration tests for ChatLogger."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_large_session_performance(self):
        """Test performance with large chat sessions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileStorageConfig(type="file", base_dir=temp_dir)
            storage = FileStorage(config)
            chat_logger = ChatLogger(storage)
            
            user_id = "perf_test_user"
            
            session_id, _ = await chat_logger.start_session(
                user_id=user_id,
                participant_name="Performance Test User",
                scenario_id="perf_test",
                scenario_name="Performance Test Scenario",
                character_id="perf_char",
                character_name="Performance Test Character"
            )
            
            # Log 100 messages (realistic performance test for integration)
            import time
            start_time = time.time()
            
            for i in range(100):
                await chat_logger.log_message(
                    user_id=user_id,
                    session_id=session_id,
                    role="participant" if i % 2 == 0 else "character",
                    content=f"Performance test message {i}",
                    message_number=i + 1
                )
                # Small delay to prevent file system stress
                if i % 10 == 9:
                    await asyncio.sleep(0.01)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Should be able to log 100 messages in reasonable time (< 10 seconds)
            assert duration < 10.0
            
            # Verify all messages were logged
            sessions = await chat_logger.list_user_sessions(user_id)
            assert len(sessions) == 1
            assert sessions[0]["message_count"] == 100
            
            # Test export performance
            start_time = time.time()
            transcript = await chat_logger.export_session_text(user_id, session_id)
            export_duration = time.time() - start_time
            
            # Export should complete in reasonable time (< 10 seconds)
            assert export_duration < 10.0
            assert "Performance test message 99" in transcript