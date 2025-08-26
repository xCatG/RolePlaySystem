import pytest
import asyncio
import base64
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException

from role_play.common.exceptions import AuthenticationError, TokenExpiredError
from role_play.voice.handler import VoiceHandler
from role_play.voice.models import VoiceRequest
from role_play.common.models import User, EnvironmentInfo


@pytest.fixture
def voice_handler() -> VoiceHandler:
    """Creates a VoiceHandler instance for testing."""
    return VoiceHandler()


@pytest.mark.asyncio
async def test_process_adk_event_transcript(voice_handler):
    stats = {"transcripts_processed": 0}

    # Test final transcript
    event = MagicMock()
    event.content.parts = [MagicMock(text="Hello world")]
    event.partial = False
    event.content.role = "model"
    result = voice_handler._process_adk_event(event, stats)
    assert result["type"] == "transcript_final"
    assert result["text"] == "Hello world"
    assert result["role"] == "assistant"

    # Test partial transcript
    event.partial = True
    result = voice_handler._process_adk_event(event, stats)
    assert result["type"] == "transcript_partial"


@pytest.mark.asyncio
async def test_process_adk_event_audio(voice_handler):
    stats = {"transcripts_processed": 0, "audio_chunks_received": 0}
    audio_data = b"\x01\x02\x03"

    # Create a mock part that only has inline_data
    part = MagicMock()
    part.inline_data = MagicMock(data=audio_data, mime_type="audio/pcm")
    del part.text # Ensure text attribute is not present

    event = MagicMock()
    event.content.parts = [part]
    result = voice_handler._process_adk_event(event, stats)

    assert result["type"] == "audio"
    assert result["mime_type"] == "audio/pcm"
    assert stats["audio_chunks_received"] == 1


@pytest.mark.asyncio
async def test_validate_jwt_token_logic(voice_handler, monkeypatch):
    mock_auth_manager = MagicMock()
    mock_storage = AsyncMock()

    monkeypatch.setattr("role_play.voice.handler.get_auth_manager", lambda x: mock_auth_manager)
    monkeypatch.setattr("role_play.voice.handler.get_storage_backend", lambda: mock_storage)

    # Test valid token
    mock_auth_manager.verify_token.return_value = MagicMock(user_id="test_user")
    mock_storage.get_user.return_value = MagicMock(id="test_user")
    user = await voice_handler._validate_jwt_token("valid_token", mock_storage)
    assert user.id == "test_user"

    # Test invalid token
    mock_auth_manager.verify_token.side_effect = AuthenticationError("Invalid token")
    with pytest.raises(HTTPException):
        await voice_handler._validate_jwt_token("invalid_token", mock_storage)

    # Test expired token
    mock_auth_manager.verify_token.side_effect = TokenExpiredError("Token expired")
    with pytest.raises(HTTPException):
        await voice_handler._validate_jwt_token("expired_token", mock_storage)


@pytest.mark.asyncio
async def test_process_adk_event_turn_status(voice_handler):
    """Test processing turn status events."""
    stats = {"transcripts_processed": 0}
    
    # Mock turn completion event
    event = MagicMock()
    event.content = None
    event.turn_complete = True
    event.interrupted = False
    event.partial = False
    
    result = voice_handler._process_adk_event(event, stats)
    
    assert result["type"] == "turn_status"
    assert result["turn_complete"] is True
    assert result["interrupted"] is False
    assert result["partial"] is False
    assert stats["transcripts_processed"] == 1


@pytest.mark.asyncio
async def test_check_session_limit(voice_handler):
    """Test session limit checking."""
    mock_storage = AsyncMock()
    
    # Test within limit
    result = voice_handler._check_session_limit("user123", mock_storage)
    assert result is True  # Should always return True for now (no limit implemented)


@pytest.mark.asyncio
async def test_handler_properties(voice_handler):
    """Test basic handler properties."""
    assert voice_handler.prefix == "/voice"
    assert voice_handler.router is not None
    # Router should be cached
    assert voice_handler.router is voice_handler.router


@pytest.mark.asyncio 
async def test_voice_request_processing():
    """Test VoiceRequest model processing."""
    # Test text request
    text_data = "Hello world"
    encoded_text = base64.b64encode(text_data.encode()).decode()
    text_request = VoiceRequest(mime_type="text/plain", data=encoded_text, end_session=False)
    
    decoded_data = text_request.decode_data()
    assert decoded_data == text_data
    
    # Test audio request
    audio_data = b"\x01\x02\x03\x04"
    encoded_audio = base64.b64encode(audio_data).decode()
    audio_request = VoiceRequest(mime_type="audio/pcm", data=encoded_audio, end_session=False)
    
    decoded_audio = audio_request.decode_data()
    assert decoded_audio == audio_data


@pytest.mark.asyncio
async def test_process_adk_event_with_no_content(voice_handler):
    """Test processing ADK events with no content."""
    stats = {"transcripts_processed": 0}
    
    # Event with no content
    event = MagicMock()
    event.content = None
    event.turn_complete = False
    event.interrupted = False
    event.partial = False
    
    # Should still process and increment counter
    result = voice_handler._process_adk_event(event, stats)
    assert result["type"] == "turn_status"
    assert stats["transcripts_processed"] == 1


@pytest.mark.asyncio
async def test_process_adk_event_empty_parts(voice_handler):
    """Test processing ADK events with empty parts."""
    stats = {"transcripts_processed": 0}
    
    # Event with empty parts list
    event = MagicMock()
    event.content.parts = []
    event.turn_complete = False
    event.interrupted = False
    event.partial = False
    
    result = voice_handler._process_adk_event(event, stats)
    assert result["type"] == "turn_status"
    assert stats["transcripts_processed"] == 1


@pytest.mark.asyncio
async def test_voice_config_constants():
    """Test voice configuration constants are accessible."""
    from role_play.voice.voice_config import VoiceConfig
    
    assert VoiceConfig.AUDIO_FORMAT == "pcm"
    assert VoiceConfig.AUDIO_SAMPLE_RATE == 16000
    assert VoiceConfig.AUDIO_CHANNELS == 1
    assert VoiceConfig.AUDIO_BIT_DEPTH == 16