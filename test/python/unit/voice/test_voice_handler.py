"""Tests for the voice chat handler."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import WebSocket

from src.python.role_play.voice.handler import VoiceChatHandler
from src.python.role_play.voice.models import (
    VoiceClientRequest,
    VoiceConfigMessage,
    VoiceStatusMessage,
    TranscriptPartialMessage,
    TranscriptFinalMessage
)
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
    """Test cases for VoiceChatHandler."""

    @pytest.fixture
    def handler(self):
        """Create a voice chat handler for testing."""
        return VoiceChatHandler()

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        return User(
            id="user123",
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            preferred_language="en"
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
        assert handler.voice_service is not None
        assert handler.router is not None

    def test_router_endpoints(self, handler):
        """Test that all expected routes are registered."""
        router = handler.router
        routes = [route.path for route in router.routes]
        
        # Check that WebSocket and REST endpoints are registered
        assert "/ws/{session_id}" in routes
        assert "/session/{session_id}/info" in routes
        assert "/session/{session_id}/stats" in routes
        assert "/test" in routes

    @patch('src.python.role_play.voice.handler.get_storage_backend')
    @patch('src.python.role_play.voice.handler.get_chat_logger')
    @patch('src.python.role_play.voice.handler.get_adk_session_service')
    @patch('src.python.role_play.voice.handler.get_resource_loader')
    async def test_jwt_validation_success(
        self, 
        mock_resource_loader,
        mock_adk_service,
        mock_chat_logger,
        mock_storage,
        handler, 
        mock_user
    ):
        """Test successful JWT token validation."""
        # Mock dependencies
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        
        mock_auth_manager = Mock()
        mock_auth_manager.verify_token.return_value = Mock(user_id="user123")
        mock_storage_instance.get_user.return_value = mock_user
        
        with patch('src.python.role_play.voice.handler.get_auth_manager', return_value=mock_auth_manager):
            result = await handler._validate_jwt_token("valid_token")
            
            assert result == mock_user
            mock_auth_manager.verify_token.assert_called_once_with("valid_token")

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
        
        mock_adk_service_instance = Mock()
        mock_adk_service_instance.get_session.return_value = mock_adk_session
        mock_adk_service.return_value = mock_adk_service_instance
        
        mock_chat_logger_instance = Mock()
        mock_chat_logger.return_value = mock_chat_logger_instance
        
        result = await handler._validate_session(
            "session123", 
            "user123", 
            mock_adk_service_instance, 
            mock_chat_logger_instance
        )
        
        assert result == mock_adk_session

    @patch('src.python.role_play.voice.handler.get_storage_backend')
    @patch('src.python.role_play.voice.handler.get_chat_logger')
    @patch('src.python.role_play.voice.handler.get_adk_session_service')
    async def test_session_validation_not_found(
        self,
        mock_adk_service,
        mock_chat_logger,
        mock_storage,
        handler
    ):
        """Test session validation when session not found."""
        mock_adk_service_instance = Mock()
        mock_adk_service_instance.get_session.return_value = None
        mock_adk_service.return_value = mock_adk_service_instance
        
        mock_chat_logger_instance = Mock()
        mock_chat_logger_instance.get_session_end_info.side_effect = Exception("Not found")
        mock_chat_logger.return_value = mock_chat_logger_instance
        
        result = await handler._validate_session(
            "session123", 
            "user123", 
            mock_adk_service_instance, 
            mock_chat_logger_instance
        )
        
        assert result is None

    async def test_websocket_missing_token(self, handler):
        """Test WebSocket connection without token."""
        ws = MockWebSocket()
        ws.query_params = {}  # No token
        
        await handler.handle_voice_session(ws, "session123", None)
        
        assert ws.closed
        assert ws.close_code == 1008
        assert "Missing token parameter" in str(ws.close_reason)

    @patch('src.python.role_play.voice.handler.VoiceChatHandler._validate_jwt_token')
    async def test_websocket_invalid_token(self, mock_validate_jwt, handler):
        """Test WebSocket connection with invalid token."""
        mock_validate_jwt.return_value = None  # Invalid token
        
        ws = MockWebSocket()
        ws.query_params = {"token": "invalid_token"}
        
        await handler.handle_voice_session(ws, "session123", "invalid_token")
        
        assert ws.closed
        assert ws.close_code == 1008
        assert "Invalid authentication token" in str(ws.close_reason)

    def test_voice_client_request_validation(self):
        """Test VoiceClientRequest model validation."""
        # Valid request
        request = VoiceClientRequest(
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

    def test_voice_client_request_text_decoding(self):
        """Test VoiceClientRequest text data decoding."""
        request = VoiceClientRequest(
            mime_type="text/plain",
            data="dGVzdCB0ZXh0",  # "test text" in base64
            end_session=False
        )
        
        decoded = request.decode_data()
        assert decoded == "test text"
        assert isinstance(decoded, str)

    def test_voice_config_message(self):
        """Test VoiceConfigMessage creation."""
        config = VoiceConfigMessage(
            audio_format="pcm",
            sample_rate=16000,
            channels=1,
            bit_depth=16,
            language="en",
            voice_name="Aoede"
        )
        
        assert config.type == "config"
        assert config.audio_format == "pcm"
        assert config.sample_rate == 16000
        assert config.language == "en"

    def test_voice_status_message(self):
        """Test VoiceStatusMessage creation."""
        status = VoiceStatusMessage(
            status="connected",
            message="Voice session connected"
        )
        
        assert status.type == "status"
        assert status.status == "connected"
        assert status.message == "Voice session connected"

    def test_transcript_partial_message(self):
        """Test TranscriptPartialMessage creation."""
        partial = TranscriptPartialMessage(
            text="Hello world",
            role="user",
            stability=0.85,
            timestamp="2025-01-14T10:30:00Z"
        )
        
        assert partial.type == "transcript_partial"
        assert partial.text == "Hello world"
        assert partial.role == "user"
        assert partial.stability == 0.85

    def test_transcript_final_message(self):
        """Test TranscriptFinalMessage creation."""
        final = TranscriptFinalMessage(
            text="Hello world final",
            role="assistant",
            duration_ms=2500,
            confidence=0.92,
            metadata={"test": "data"},
            timestamp="2025-01-14T10:30:00Z"
        )
        
        assert final.type == "transcript_final"
        assert final.text == "Hello world final"
        assert final.role == "assistant"
        assert final.duration_ms == 2500
        assert final.confidence == 0.92
        assert final.metadata["test"] == "data"

    @patch('src.python.role_play.voice.handler.VoiceChatHandler._validate_jwt_token')
    @patch('src.python.role_play.voice.handler.VoiceChatHandler._validate_session')
    @patch('src.python.role_play.voice.handler.get_storage_backend')
    @patch('src.python.role_play.voice.handler.get_chat_logger')
    @patch('src.python.role_play.voice.handler.get_adk_session_service')
    @patch('src.python.role_play.voice.handler.get_resource_loader')
    async def test_websocket_connection_flow(
        self,
        mock_resource_loader,
        mock_adk_service,
        mock_chat_logger,
        mock_storage,
        mock_validate_session,
        mock_validate_jwt,
        handler,
        mock_user
    ):
        """Test the complete WebSocket connection flow."""
        # Setup mocks
        mock_validate_jwt.return_value = mock_user
        
        mock_adk_session = Mock()
        mock_adk_session.state = {
            "character_id": "char123",
            "scenario_id": "scenario123",
            "script_data": None
        }
        mock_validate_session.return_value = mock_adk_session
        
        # Mock voice service
        mock_voice_session = Mock()
        mock_voice_session.active = False  # Will exit streaming loop immediately
        mock_voice_session.cleanup.return_value = {"stats": "test"}
        
        with patch.object(handler.voice_service, 'create_voice_session', return_value=mock_voice_session):
            ws = MockWebSocket()
            ws.query_params = {"token": "valid_token"}
            
            # This should complete without errors
            await handler.handle_voice_session(ws, "session123", "valid_token")
            
            # Check that WebSocket was accepted and messages were sent
            assert ws.accepted
            assert len(ws.sent_messages) >= 2  # At least status and config messages
            
            # Check message types
            message_types = [msg.get("type") for msg in ws.sent_messages]
            assert "status" in message_types

    @pytest.mark.asyncio
    async def test_receive_from_client_text_message(self, handler):
        """Test receiving text message from client."""
        mock_voice_session = Mock()
        mock_voice_session.active = True
        mock_voice_session.send_text = AsyncMock()
        mock_voice_session.end_session = AsyncMock()
        
        # Mock WebSocket that returns a text message then ends
        ws = Mock()
        text_request = {
            "mime_type": "text/plain",
            "data": "dGVzdCBtZXNzYWdl",  # "test message" in base64
            "end_session": False
        }
        end_request = {
            "mime_type": "text/plain",
            "data": "",
            "end_session": True
        }
        
        ws.receive_text.side_effect = [
            json.dumps(text_request),
            json.dumps(end_request)
        ]
        
        await handler._receive_from_client(ws, mock_voice_session)
        
        # Verify text was sent to voice session
        mock_voice_session.send_text.assert_called_once_with("test message")
        mock_voice_session.end_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_from_client_audio_message(self, handler):
        """Test receiving audio message from client."""
        mock_voice_session = Mock()
        mock_voice_session.active = True
        mock_voice_session.send_audio = AsyncMock()
        mock_voice_session.end_session = AsyncMock()
        
        # Mock WebSocket that returns an audio message then ends
        ws = Mock()
        audio_request = {
            "mime_type": "audio/pcm",
            "data": "dGVzdCBhdWRpbw==",  # "test audio" in base64
            "end_session": False
        }
        end_request = {
            "mime_type": "audio/pcm",
            "data": "",
            "end_session": True
        }
        
        ws.receive_text.side_effect = [
            json.dumps(audio_request),
            json.dumps(end_request)
        ]
        
        await handler._receive_from_client(ws, mock_voice_session)
        
        # Verify audio was sent to voice session
        mock_voice_session.send_audio.assert_called_once()
        call_args = mock_voice_session.send_audio.call_args
        assert call_args[0][1] == "audio/pcm"  # mime_type argument
        mock_voice_session.end_session.assert_called_once()


class TestVoiceHandlerIntegration:
    """Integration tests for voice handler."""

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
        client = TestClient(app_with_voice_handler)
        
        # Test the simple endpoint
        response = client.get("/voice/test")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__])