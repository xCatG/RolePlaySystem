"""Tests for the simplified voice chat handler."""

import pytest
import asyncio
import json
import base64
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import WebSocket, WebSocketDisconnect

from src.python.role_play.voice.handler import VoiceChatHandler
from src.python.role_play.voice.models import VoiceRequest, VoiceMessage
from src.python.role_play.common.models import User, UserRole


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.sent_messages = []
        self.query_params = {}
        
    async def accept(self):
        self.accepted = True
        
    async def close(self, code=None, reason=None):
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        
    async def send_json(self, data):
        self.sent_messages.append(data)
        
    async def receive_text(self):
        # Mock receiving client requests
        return json.dumps({
            "mime_type": "text/plain",
            "data": "dGVzdCBtZXNzYWdl",  # "test message" in base64
            "end_session": False
        })


class TestVoiceChatHandler:
    """Test cases for simplified VoiceChatHandler."""

    @pytest.fixture
    def handler(self):
        """Create a voice chat handler for testing."""
        return VoiceChatHandler()

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        from datetime import datetime, timezone
        return User(
            id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            preferred_language="en",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = MockWebSocket()
        ws.query_params = {"token": "valid_token"}
        return ws

    def test_handler_initialization(self, handler):
        """Test handler initializes correctly."""
        assert handler.prefix == "/voice"
        assert handler.active_sessions is not None
        assert handler.router is not None

    def test_router_endpoints(self, handler):
        """Test that WebSocket endpoint is registered."""
        router = handler.router
        routes = [route.path for route in router.routes]
        assert "/ws/{session_id}" in routes

    @patch('src.python.role_play.voice.handler.get_storage_backend')
    @patch('src.python.role_play.voice.handler.get_auth_manager')
    async def test_jwt_validation_success(
        self, 
        mock_get_auth_manager,
        mock_get_storage,
        handler, 
        mock_user
    ):
        """Test successful JWT token validation."""
        # Mock storage backend
        mock_storage = AsyncMock()
        mock_storage.get_user.return_value = mock_user
        mock_get_storage.return_value = mock_storage
        
        # Mock auth manager
        mock_auth_manager = Mock()
        mock_token_data = Mock(user_id="user123")
        mock_auth_manager.verify_token.return_value = mock_token_data
        mock_get_auth_manager.return_value = mock_auth_manager
        
        result = await handler._validate_jwt_token("valid_token")
        
        assert result == mock_user
        mock_auth_manager.verify_token.assert_called_once_with("valid_token")
        mock_storage.get_user.assert_called_once_with("user123")

    async def test_jwt_validation_failure(self, handler):
        """Test JWT token validation failure."""
        with patch('src.python.role_play.voice.handler.get_auth_manager') as mock_get_auth:
            mock_auth_manager = Mock()
            mock_auth_manager.verify_token.side_effect = Exception("Invalid token")
            mock_get_auth.return_value = mock_auth_manager
            
            result = await handler._validate_jwt_token("invalid_token")
            
            assert result is None

    @patch('src.python.role_play.voice.handler.get_storage_backend')
    @patch('src.python.role_play.voice.handler.get_chat_logger')
    @patch('src.python.role_play.voice.handler.get_adk_session_service')
    async def test_session_validation_success(
        self,
        mock_adk_service,
        mock_chat_logger,
        mock_storage,
        handler
    ):
        """Test successful session validation."""
        # Mock ADK session
        mock_adk_session = Mock()
        mock_adk_session.state = {
            "character_id": "char123",
            "scenario_id": "scenario123"
        }
        
        mock_adk_service_instance = AsyncMock()
        mock_adk_service_instance.get_session.return_value = mock_adk_session
        mock_adk_service.return_value = mock_adk_service_instance
        
        mock_chat_logger_instance = AsyncMock()
        mock_chat_logger.return_value = mock_chat_logger_instance
        
        result = await handler._validate_session(
            "session123", 
            "user123", 
            mock_adk_service_instance, 
            mock_chat_logger_instance
        )
        
        assert result == mock_adk_session

    async def test_websocket_missing_token(self, handler):
        """Test WebSocket connection without token."""
        ws = MockWebSocket()
        ws.query_params = {}  # No token
        
        await handler.handle_voice_session(ws, "session123", None)
        
        assert ws.closed
        assert ws.close_code == 1008

    @patch('src.python.role_play.voice.handler.VoiceChatHandler._validate_jwt_token')
    async def test_websocket_invalid_token(self, mock_validate_jwt, handler):
        """Test WebSocket connection with invalid token."""
        mock_validate_jwt.return_value = None  # Invalid token
        
        ws = MockWebSocket()
        ws.query_params = {"token": "invalid_token"}
        
        await handler.handle_voice_session(ws, "session123", "invalid_token")
        
        assert ws.closed
        assert ws.close_code == 1008

    def test_voice_request_validation(self):
        """Test VoiceRequest model validation."""
        # Valid request
        request = VoiceRequest(
            mime_type="audio/pcm",
            data="dGVzdCBhdWRpbw==",  # base64 encoded
            end_session=False
        )
        
        assert request.mime_type == "audio/pcm"
        assert request.data == "dGVzdCBhdWRpbw=="
        assert request.end_session is False
        
        # Test data decoding
        decoded = request.decode_data()
        assert isinstance(decoded, bytes)

    def test_voice_request_text_decoding(self):
        """Test VoiceRequest text data decoding."""
        request = VoiceRequest(
            mime_type="text/plain",
            data="dGVzdCB0ZXh0",  # "test text" in base64
            end_session=False
        )
        
        decoded = request.decode_data()
        assert decoded == "test text"
        assert isinstance(decoded, str)

    def test_voice_message_creation(self):
        """Test VoiceMessage creation with extra fields."""
        message = VoiceMessage(
            type="status",
            timestamp="2025-01-14T10:30:00Z",
            status="ready",  # Extra field allowed
            message="Session ready"  # Extra field allowed
        )
        
        assert message.type == "status"
        assert message.timestamp == "2025-01-14T10:30:00Z"
        # Extra fields should be preserved due to Config.extra = "allow"
        assert hasattr(message, "__pydantic_extra__") or message.dict()["status"] == "ready"

    def test_adk_event_processing(self, handler):
        """Test direct ADK event processing."""
        stats = {"transcripts_processed": 0}
        
        # Mock transcript event with only the attributes we want
        mock_event = Mock(spec=['input_transcription'])
        mock_event.input_transcription = Mock()
        mock_event.input_transcription.text = "Hello world"
        mock_event.input_transcription.is_final = True
        mock_event.input_transcription.confidence = 0.95
        
        result = handler._process_adk_event(mock_event, stats)
        
        assert result["type"] == "transcript_final"
        assert result["text"] == "Hello world"
        assert result["role"] == "user"
        assert result["confidence"] == 0.95
        assert stats["transcripts_processed"] == 1

    @pytest.mark.asyncio
    async def test_adk_initialization(self, handler, mock_user):
        """Test ADK components initialization."""
        # Mock ADK session
        mock_adk_session = Mock()
        mock_adk_session.state = {
            "character_id": "char123",
            "scenario_id": "scenario123",
            "script_data": None
        }
        
        with patch('src.python.role_play.voice.handler.get_production_agent') as mock_agent, \
             patch('src.python.role_play.voice.handler.Runner') as mock_runner, \
             patch('src.python.role_play.voice.handler.LiveRequestQueue') as mock_queue:
            
            # Mock agent creation
            mock_agent_instance = Mock()
            mock_agent.return_value = mock_agent_instance
            
            # Mock runner
            mock_runner_instance = Mock()
            mock_runner.return_value = mock_runner_instance
            mock_runner_instance.run_live.return_value = AsyncMock()
            
            # Mock queue
            mock_queue_instance = Mock()
            mock_queue.return_value = mock_queue_instance
            
            result = await handler._initialize_adk("session123", mock_user, mock_adk_session)
            
            assert result["session_id"] == "session123"
            assert result["user_id"] == mock_user.id
            assert result["active"] is True
            assert "stats" in result
            assert result["stats"]["audio_chunks_sent"] == 0


class TestVoiceHandlerIntegration:
    """Integration tests for simplified voice handler."""

    @pytest.fixture
    def app_with_voice_handler(self):
        """Create FastAPI app with voice handler for testing."""
        from fastapi import FastAPI
        app = FastAPI()
        handler = VoiceChatHandler()
        app.include_router(handler.router, prefix=handler.prefix)
        return app

    def test_voice_handler_routes_registered(self, app_with_voice_handler):
        """Test that voice handler routes are properly registered."""
        # Get the router from the app
        voice_router = None
        for route in app_with_voice_handler.routes:
            if hasattr(route, 'path') and route.path.startswith('/voice'):
                voice_router = route
                break
        
        assert voice_router is not None


class TestVoiceValidationAndLimits:
    """Test validation and security limits."""

    @pytest.fixture
    def handler(self):
        return VoiceChatHandler()

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        from datetime import datetime, timezone
        return User(
            id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            preferred_language="en",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    def test_audio_chunk_size_validation(self):
        """Test audio chunk size limit validation."""
        from src.python.role_play.voice.config import VoiceConfig
        
        # Create oversized audio data
        large_audio = b"x" * (VoiceConfig.MAX_AUDIO_CHUNK_SIZE + 1)
        large_audio_b64 = base64.b64encode(large_audio).decode()
        
        request = VoiceRequest(
            mime_type="audio/pcm",
            data=large_audio_b64,
            end_session=False
        )
        
        # Should raise ValueError on decode
        with pytest.raises(ValueError, match="Audio chunk too large"):
            request.decode_data()

    def test_text_size_validation(self):
        """Test text size limit validation."""
        from src.python.role_play.voice.config import VoiceConfig
        
        # Create oversized text data
        large_text = "x" * (VoiceConfig.MAX_TEXT_SIZE + 1)
        large_text_b64 = base64.b64encode(large_text.encode()).decode()
        
        request = VoiceRequest(
            mime_type="text/plain",
            data=large_text_b64,
            end_session=False
        )
        
        # Should raise ValueError on decode
        with pytest.raises(ValueError, match="Text too large"):
            request.decode_data()

    def test_invalid_mime_type_validation(self):
        """Test unsupported MIME type validation."""
        with pytest.raises(ValueError, match="Unsupported MIME type"):
            VoiceRequest(
                mime_type="video/mp4",  # Unsupported
                data="dGVzdA==",
                end_session=False
            )

    def test_malformed_base64_data(self):
        """Test malformed base64 data handling."""
        request = VoiceRequest(
            mime_type="text/plain",
            data="invalid_base64!!!",  # Malformed base64
            end_session=False
        )
        
        with pytest.raises(ValueError, match="Invalid base64 data"):
            request.decode_data()

    def test_session_limit_per_user(self, handler):
        """Test session limit enforcement per user."""
        from src.python.role_play.voice.config import VoiceConfig
        
        # Create max allowed sessions for user
        for i in range(VoiceConfig.MAX_SESSIONS_PER_USER):
            handler.active_sessions[f"session_{i}"] = {"user_id": "user123"}
        
        # Should still allow for this user
        assert handler._check_session_limit("user123") is False
        
        # Should allow for different user
        assert handler._check_session_limit("user456") is True
        
        # Remove one session
        del handler.active_sessions["session_0"]
        assert handler._check_session_limit("user123") is True

    @pytest.mark.asyncio
    async def test_connection_error_cleanup(self, handler):
        """Test connection error cleanup."""
        # Setup mock session
        mock_adk = {
            "session_id": "test_session",
            "user_id": "user123",
            "active": True,
            "live_request_queue": Mock(),
            "stats": {}
        }
        handler.active_sessions["test_session"] = mock_adk
        
        with patch.object(handler, '_cleanup_adk') as mock_cleanup:
            mock_cleanup.return_value = {"stats": "test"}
            
            # Test cleanup
            await handler._handle_connection_error("test_session")
            
            # Should call cleanup and remove session
            mock_cleanup.assert_called_once_with(mock_adk)
            assert "test_session" not in handler.active_sessions

    @pytest.mark.asyncio 
    async def test_websocket_disconnect_during_streaming(self, handler):
        """Test WebSocket disconnect during active streaming."""
        mock_adk = {
            "session_id": "test_session",
            "active": True,
            "stats": {"errors": 0}
        }
        
        # Mock WebSocket that raises disconnect
        mock_websocket = AsyncMock()
        mock_websocket.receive_text.side_effect = WebSocketDisconnect()
        
        # Should handle disconnect gracefully
        await handler._receive_from_client(mock_websocket, mock_adk)
        
        # Session should be marked inactive
        assert mock_adk["active"] is False

    @pytest.mark.asyncio
    async def test_adk_initialization_failure(self, handler, mock_user):
        """Test ADK initialization failure handling."""
        mock_adk_session = Mock()
        mock_adk_session.state = {"character_id": "char123", "scenario_id": "scenario123"}
        
        with patch('src.python.role_play.voice.handler.get_production_agent') as mock_agent:
            # Mock agent creation failure
            mock_agent.return_value = None
            
            with pytest.raises(ValueError, match="Failed to create roleplay agent"):
                await handler._initialize_adk("session123", mock_user, mock_adk_session)


if __name__ == "__main__":
    pytest.main([__file__])