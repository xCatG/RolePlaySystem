"""Unit tests for ChatHandler system prompt generation."""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from role_play.chat.handler import ChatHandler


@pytest.fixture
def mock_resource_loader():
    """Mock ResourceLoader."""
    return AsyncMock()

class TestChatHandlerSystemPrompt:
    """Test cases for ChatHandler system prompt generation."""

    @pytest.fixture
    def chat_handler(self):
        """Create ChatHandler instance."""
        return ChatHandler()

    @pytest.fixture
    def sample_english_character(self):
        """Sample English character data."""
        return {
            "id": "patient_en",
            "language": "en",
            "name": "Sarah - Patient",
            "description": "English speaking patient",
            "system_prompt": "You are Sarah, a 65-year-old woman with chronic back pain. You're anxious about new symptoms and need reassurance."
        }

    @pytest.fixture
    def sample_chinese_character(self):
        """Sample Traditional Chinese character data."""
        return {
            "id": "patient_zh_tw", 
            "language": "zh-TW",
            "name": "李小姐 - 患者",
            "description": "繁體中文患者",
            "system_prompt": "你是李小姐，一位65歲患有慢性背痛的女性。你對新症狀感到焦慮，需要安慰。"
        }

    @pytest.fixture
    def sample_japanese_character(self):
        """Sample Japanese character data."""
        return {
            "id": "patient_ja",
            "language": "ja", 
            "name": "田中さん - 患者",
            "description": "日本語を話す患者",
            "system_prompt": "あなたは田中さん、65歳の慢性的な腰痛を持つ女性です。新しい症状に不安を感じており、安心感が必要です。"
        }

    @pytest.fixture
    def sample_scenario(self):
        """Sample scenario data."""
        return {
            "id": "medical_interview",
            "name": "Medical Patient Interview",
            "description": "Practice taking medical history from a patient"
        }

    def test_system_prompt_english_character(self, sample_english_character, sample_scenario):
        """Test system prompt generation for English character."""
        chat_handler = ChatHandler()
        agent = chat_handler._create_roleplay_agent(sample_english_character, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        assert agent.name == "roleplay_patient_en_medical_interview"
        
        # Check system prompt contains English language instruction
        instruction = agent.instruction
        assert "You are Sarah, a 65-year-old woman with chronic back pain" in instruction
        assert "Practice taking medical history from a patient" in instruction
        assert "Respond in English language" in instruction
        assert "Stay fully in character" in instruction
        assert "Do NOT break character" in instruction

    def test_system_prompt_chinese_character(self, sample_chinese_character, sample_scenario):
        """Test system prompt generation for Traditional Chinese character."""
        chat_handler = ChatHandler()
        agent = chat_handler._create_roleplay_agent(sample_chinese_character, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        assert agent.name == "roleplay_patient_zh_tw_medical_interview"
        
        # Check system prompt contains Traditional Chinese language instruction
        instruction = agent.instruction
        assert "你是李小姐，一位65歲患有慢性背痛的女性" in instruction
        assert "Practice taking medical history from a patient" in instruction
        assert "Respond in Traditional Chinese language" in instruction
        assert "Stay fully in character" in instruction

    def test_system_prompt_japanese_character(self, sample_japanese_character, sample_scenario):
        """Test system prompt generation for Japanese character."""
        chat_handler = ChatHandler()
        agent = chat_handler._create_roleplay_agent(sample_japanese_character, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        assert agent.name == "roleplay_patient_ja_medical_interview"
        
        # Check system prompt contains Japanese language instruction
        instruction = agent.instruction
        assert "あなたは田中さん、65歳の慢性的な腰痛を持つ女性です" in instruction
        assert "Practice taking medical history from a patient" in instruction
        assert "Respond in Japanese language" in instruction
        assert "Stay fully in character" in instruction

    def test_system_prompt_character_without_language_defaults_to_english(self, sample_scenario):
        """Test system prompt generation for character without language field (defaults to English)."""
        chat_handler = ChatHandler()
        character_no_lang = {
            "id": "patient_no_lang",
            "name": "Test Patient", 
            "description": "Patient without language field",
            "system_prompt": "You are a test patient."
        }
        
        agent = chat_handler._create_roleplay_agent(character_no_lang, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        
        # Check system prompt defaults to English
        instruction = agent.instruction
        assert "You are a test patient." in instruction
        assert "Respond in English language" in instruction

    def test_system_prompt_unsupported_language_defaults_to_english(self, sample_scenario):
        """Test system prompt generation for character with unsupported language (defaults to English)."""
        chat_handler = ChatHandler()
        character_unsupported = {
            "id": "patient_fr",
            "language": "fr",  # Unsupported language
            "name": "Patient français",
            "description": "French speaking patient", 
            "system_prompt": "Vous êtes un patient français."
        }
        
        agent = chat_handler._create_roleplay_agent(character_unsupported, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        
        # Check system prompt defaults to English for unsupported language
        instruction = agent.instruction
        assert "Vous êtes un patient français." in instruction
        assert "Respond in English language" in instruction  # Should default to English

    def test_system_prompt_structure(self, sample_english_character, sample_scenario):
        """Test the overall structure of the generated system prompt."""
        chat_handler = ChatHandler()
        agent = chat_handler._create_roleplay_agent(sample_english_character, sample_scenario)
        instruction = agent.instruction
        
        # Check that all required sections are present
        assert "**Current Scenario:**" in instruction
        assert "**Roleplay Instructions:**" in instruction
        
        # Check all roleplay instructions are present
        assert "Stay fully in character" in instruction
        assert "Do NOT break character or mention you are an AI" in instruction
        assert "Respond naturally based on your character's personality" in instruction
        assert "IMPORTANT: Respond in" in instruction  # Language instruction
        assert "Engage with the user's messages within the roleplay context" in instruction

    def test_system_prompt_with_missing_fields(self):
        """Test system prompt generation with minimal character and scenario data."""
        chat_handler = ChatHandler()
        minimal_character = {"id": "min_char"}
        minimal_scenario = {"id": "min_scenario"}
        
        agent = chat_handler._create_roleplay_agent(minimal_character, minimal_scenario)
        
        # Should handle missing fields gracefully
        assert agent is not None
        instruction = agent.instruction
        assert "You are a helpful assistant." in instruction  # Default system prompt
        assert "No specific scenario description." in instruction  # Default scenario description
        assert "Respond in English language" in instruction  # Default language


class TestChatHandlerReadOnlySession:
    """Test cases for ChatHandler read-only session history functionality."""

    @pytest.fixture
    def mock_user(self):
        """Mock user object."""
        user = Mock()
        user.id = "test_user_123"
        user.email = "test@example.com"
        user.preferred_language = "en"
        return user

    @pytest.fixture
    def mock_adk_session_service(self):
        """Mock ADK session service."""
        mock = AsyncMock()
        mock.get_session = AsyncMock()
        mock.delete_session = AsyncMock()
        return mock

    @pytest.fixture
    def mock_chat_logger(self):
        """Mock chat logger."""
        mock = AsyncMock()
        mock.get_session_end_info = AsyncMock()
        mock.get_session_messages = AsyncMock()
        mock.delete_session = AsyncMock()
        return mock

    @pytest.fixture
    def chat_handler(self):
        """Create ChatHandler instance."""
        return ChatHandler()

    @pytest.mark.asyncio
    async def test_get_session_status_active_session(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Test getting status for an active session."""
        chat_handler = ChatHandler()
        # Mock active session
        mock_session = Mock()
        mock_adk_session_service.get_session.return_value = mock_session

        response = await chat_handler.get_session_status(
            session_id="active_session_123",
            current_user=mock_user,
            adk_session_service=mock_adk_session_service,
            chat_logger=mock_chat_logger
        )

        assert response.success is True
        assert response.status == "active"
        assert response.ended_at is None
        assert response.ended_reason is None

        # Verify ADK session service was called correctly
        mock_adk_session_service.get_session.assert_called_once_with(
            app_name="roleplay_chat", 
            user_id="test_user_123", 
            session_id="active_session_123"
        )

    @pytest.mark.asyncio
    async def test_get_session_status_ended_session(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Test getting status for an ended session."""
        chat_handler = ChatHandler()
        # Mock no active session
        mock_adk_session_service.get_session.return_value = None
        
        # Mock ended session info
        mock_chat_logger.get_session_end_info.return_value = {
            "ended_at": "2023-12-15T10:30:00Z",
            "reason": "User ended session",
            "total_messages": 5,
            "duration_seconds": 120.0
        }

        response = await chat_handler.get_session_status(
            session_id="ended_session_456",
            current_user=mock_user,
            adk_session_service=mock_adk_session_service,
            chat_logger=mock_chat_logger
        )

        assert response.success is True
        assert response.status == "ended"
        assert response.ended_at == "2023-12-15T10:30:00Z"
        assert response.ended_reason == "User ended session"

        # Verify services were called correctly
        mock_adk_session_service.get_session.assert_called_once()
        mock_chat_logger.get_session_end_info.assert_called_once_with(
            user_id="test_user_123", 
            session_id="ended_session_456"
        )

    @pytest.mark.asyncio
    async def test_get_session_status_ended_session_no_reason(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Test getting status for an ended session without specific reason."""
        chat_handler = ChatHandler()
        # Mock no active session
        mock_adk_session_service.get_session.return_value = None
        
        # Mock ended session info without reason
        mock_chat_logger.get_session_end_info.return_value = {
            "ended_at": "2023-12-15T10:30:00Z",
            "total_messages": 3,
            "duration_seconds": 60.0
        }

        response = await chat_handler.get_session_status(
            session_id="ended_session_789",
            current_user=mock_user,
            adk_session_service=mock_adk_session_service,
            chat_logger=mock_chat_logger
        )

        assert response.success is True
        assert response.status == "ended"
        assert response.ended_at == "2023-12-15T10:30:00Z"
        assert response.ended_reason == "Session ended"  # Default reason

    @pytest.mark.asyncio
    async def test_get_session_status_service_error(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Test error handling in get_session_status."""
        chat_handler = ChatHandler()
        # Mock exception in ADK service
        mock_adk_session_service.get_session.side_effect = Exception("ADK service error")

        with pytest.raises(Exception):  # HTTPException from FastAPI
            await chat_handler.get_session_status(
                session_id="error_session",
                current_user=mock_user,
                adk_session_service=mock_adk_session_service,
                chat_logger=mock_chat_logger
            )

    @pytest.mark.asyncio
    async def test_get_session_messages_success(self, mock_user, mock_chat_logger):
        """Test successfully getting session messages."""
        chat_handler = ChatHandler()
        # Mock message data
        mock_messages = [
            {
                "role": "participant",
                "content": "Hello, I need help.",
                "timestamp": "2023-12-15T10:00:00Z",
                "message_number": 1
            },
            {
                "role": "character",
                "content": "I'm here to help you!",
                "timestamp": "2023-12-15T10:00:30Z",
                "message_number": 2
            },
            {
                "role": "participant",
                "content": "Thank you very much.",
                "timestamp": "2023-12-15T10:01:00Z",
                "message_number": 3
            }
        ]
        mock_chat_logger.get_session_messages.return_value = mock_messages

        response = await chat_handler.get_session_messages(
            session_id="session_with_messages",
            current_user=mock_user,
            chat_logger=mock_chat_logger
        )

        assert response.success is True
        assert response.session_id == "session_with_messages"
        assert len(response.messages) == 3
        
        # Check first message
        assert response.messages[0].role == "participant"
        assert response.messages[0].content == "Hello, I need help."
        assert response.messages[0].message_number == 1
        
        # Check last message
        assert response.messages[2].role == "participant"
        assert response.messages[2].content == "Thank you very much."
        
        # Verify chat logger was called correctly
        mock_chat_logger.get_session_messages.assert_called_once_with(
            user_id="test_user_123",
            session_id="session_with_messages"
        )

    @pytest.mark.asyncio
    async def test_get_session_messages_empty_session(self, mock_user, mock_chat_logger):
        """Test getting messages from an empty session."""
        chat_handler = ChatHandler()
        # Mock empty message list
        mock_chat_logger.get_session_messages.return_value = []

        response = await chat_handler.get_session_messages(
            session_id="empty_session",
            current_user=mock_user,
            chat_logger=mock_chat_logger
        )

        assert response.success is True
        assert response.session_id == "empty_session"
        assert len(response.messages) == 0

    @pytest.mark.asyncio
    async def test_get_session_messages_service_error(self, mock_user, mock_chat_logger):
        """Test error handling in get_session_messages."""
        chat_handler = ChatHandler()
        # Mock exception in chat logger
        mock_chat_logger.get_session_messages.side_effect = Exception("Chat logger error")

        with pytest.raises(Exception):  # HTTPException from FastAPI
            await chat_handler.get_session_messages(
                session_id="error_session",
                current_user=mock_user,
                chat_logger=mock_chat_logger
            )

    @pytest.mark.asyncio
    async def test_delete_session_active_session(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Test deleting an active session."""
        chat_handler = ChatHandler()
        # Mock active session
        mock_session = Mock()
        mock_adk_session_service.get_session.return_value = mock_session
        mock_adk_session_service.delete_session.return_value = None
        mock_chat_logger.delete_session.return_value = None

        # Should not raise exception
        await chat_handler.delete_session(
            session_id="active_session_to_delete",
            current_user=mock_user,
            adk_session_service=mock_adk_session_service,
            chat_logger=mock_chat_logger
        )

        # Verify ADK session was deleted
        mock_adk_session_service.delete_session.assert_called_once_with(
            app_name="roleplay_chat",
            user_id="test_user_123",
            session_id="active_session_to_delete"
        )

        # Verify JSONL log was deleted
        mock_chat_logger.delete_session.assert_called_once_with(
            user_id="test_user_123",
            session_id="active_session_to_delete"
        )

    @pytest.mark.asyncio
    async def test_delete_session_ended_session(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Test deleting an ended session (not in ADK memory)."""
        chat_handler = ChatHandler()
        # Mock no active session
        mock_adk_session_service.get_session.return_value = None
        mock_chat_logger.delete_session.return_value = None

        # Should not raise exception
        await chat_handler.delete_session(
            session_id="ended_session_to_delete",
            current_user=mock_user,
            adk_session_service=mock_adk_session_service,
            chat_logger=mock_chat_logger
        )

        # Verify ADK session delete was not called (no active session)
        mock_adk_session_service.delete_session.assert_not_called()

        # Verify JSONL log was still deleted
        mock_chat_logger.delete_session.assert_called_once_with(
            user_id="test_user_123",
            session_id="ended_session_to_delete"
        )

    @pytest.mark.asyncio
    async def test_delete_session_adk_error_continues_to_file_deletion(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Test that file deletion continues even if ADK deletion fails."""
        chat_handler = ChatHandler()
        # Mock active session but deletion fails
        mock_session = Mock()
        mock_adk_session_service.get_session.return_value = mock_session
        mock_adk_session_service.delete_session.side_effect = Exception("ADK delete error")
        mock_chat_logger.delete_session.return_value = None

        with pytest.raises(Exception):  # Should raise HTTPException
            await chat_handler.delete_session(
                session_id="problematic_session",
                current_user=mock_user,
                adk_session_service=mock_adk_session_service,
                chat_logger=mock_chat_logger
            )

    @pytest.mark.asyncio
    async def test_delete_session_file_error(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Test error handling when file deletion fails."""
        chat_handler = ChatHandler()
        # Mock no active session
        mock_adk_session_service.get_session.return_value = None
        # Mock file deletion error
        mock_chat_logger.delete_session.side_effect = Exception("File deletion error")

        with pytest.raises(Exception):  # HTTPException from FastAPI
            await chat_handler.delete_session(
                session_id="file_error_session",
                current_user=mock_user,
                adk_session_service=mock_adk_session_service,
                chat_logger=mock_chat_logger
            )

    @pytest.mark.asyncio
    async def test_send_message_to_ended_session_blocked(self, mock_user, mock_adk_session_service, mock_chat_logger, mock_resource_loader):
        """Test that sending messages to ended sessions is blocked."""
        chat_handler = ChatHandler()
        # Mock no active session
        mock_adk_session_service.get_session.return_value = None
        
        # Mock ended session info (session exists in logs but is ended)
        mock_chat_logger.get_session_end_info.return_value = {
            "ended_at": "2023-12-15T10:30:00Z",
            "reason": "User ended session"
        }

        # Mock message request
        message_request = Mock()
        message_request.message = "This should be blocked"

        with pytest.raises(Exception):  # Should raise HTTPException with 403 status
            await chat_handler.send_message(
                session_id="ended_session",
                request=message_request,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                adk_session_service=mock_adk_session_service,
                resource_loader=mock_resource_loader
            )

        # Verify session end info was checked (send_message uses positional args)
        mock_chat_logger.get_session_end_info.assert_called_once_with(
            "test_user_123",
            "ended_session"
        )

    @pytest.mark.asyncio
    async def test_read_only_session_integration_workflow(self, mock_user, mock_adk_session_service, mock_chat_logger):
        """Integration test for complete read-only session workflow."""
        chat_handler = ChatHandler()
        session_id = "integration_test_session"
        
        # 1. Test active session status
        mock_adk_session_service.get_session.return_value = Mock()  # Active session
        
        status_response = await chat_handler.get_session_status(
            session_id=session_id,
            current_user=mock_user,
            adk_session_service=mock_adk_session_service,
            chat_logger=mock_chat_logger
        )
        assert status_response.status == "active"
        
        # 2. Simulate session ending (no longer in ADK memory)
        mock_adk_session_service.get_session.return_value = None
        mock_chat_logger.get_session_end_info.return_value = {
            "ended_at": "2023-12-15T10:30:00Z",
            "reason": "Integration test completed"
        }
        
        # 3. Test ended session status
        status_response = await chat_handler.get_session_status(
            session_id=session_id,
            current_user=mock_user,
            adk_session_service=mock_adk_session_service,
            chat_logger=mock_chat_logger
        )
        assert status_response.status == "ended"
        assert status_response.ended_reason == "Integration test completed"
        
        # 4. Test getting messages from ended session
        mock_messages = [
            {"role": "participant", "content": "Test message", "timestamp": "2023-12-15T10:00:00Z", "message_number": 1},
            {"role": "character", "content": "Test response", "timestamp": "2023-12-15T10:00:30Z", "message_number": 2}
        ]
        mock_chat_logger.get_session_messages.return_value = mock_messages
        
        messages_response = await chat_handler.get_session_messages(
            session_id=session_id,
            current_user=mock_user,
            chat_logger=mock_chat_logger
        )
        assert len(messages_response.messages) == 2
        assert messages_response.messages[0].content == "Test message"
        
        # 5. Test session deletion
        mock_chat_logger.delete_session.return_value = None
        
        await chat_handler.delete_session(
            session_id=session_id,
            current_user=mock_user,
            adk_session_service=mock_adk_session_service,
            chat_logger=mock_chat_logger
        )
        
        # Verify all services were called appropriately
        assert mock_adk_session_service.get_session.call_count >= 2  # Called multiple times
        mock_chat_logger.delete_session.assert_called_once_with(
            user_id="test_user_123",
            session_id=session_id
        )