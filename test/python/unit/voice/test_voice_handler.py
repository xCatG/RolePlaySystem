import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'src' / 'python'))

from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from role_play.voice.handler import VoiceChatHandler
from role_play.common.models import User, UserRole
from role_play.common.exceptions import AuthenticationError, TokenExpiredError
from role_play.server import dependencies

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

# --- Fixtures ---

@pytest.fixture
def mock_auth_manager():
    """Mock AuthManager."""
    mock = AsyncMock()
    mock.get_user_by_token.return_value = User(
        id="test_user",
        username="test",
        role=UserRole.USER,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    return mock

@pytest.fixture
def mock_adk_session_service():
    """Mock InMemorySessionService."""
    mock = AsyncMock()
    mock.get_session.return_value = MagicMock(state={
        "character_id": "char1",
        "scenario_id": "scene1",
        "script_data": None,
        "language": "en"
    })
    return mock

@pytest.fixture
def mock_voice_service():
    """Mock ADKVoiceService."""
    mock = AsyncMock()

    # This generator will wait forever, keeping the agent_to_client task alive
    # until it's cancelled at the end of the test.
    async def indefinite_generator():
        await asyncio.Event().wait()
        if False: yield

    mock_queue = AsyncMock()
    mock_queue.close = MagicMock()

    mock.create_voice_session.return_value = (indefinite_generator(), mock_queue)
    return mock

@pytest.fixture
def app(mock_auth_manager, mock_adk_session_service, mock_voice_service):
    """Create a FastAPI app with the VoiceChatHandler for testing."""
    with patch('role_play.voice.handler.ADKVoiceService', return_value=mock_voice_service):
        app = FastAPI()
        handler = VoiceChatHandler()
        app.include_router(handler.router, prefix=handler.prefix)

        app.dependency_overrides[dependencies.get_auth_manager] = lambda: mock_auth_manager
        app.dependency_overrides[dependencies.get_adk_session_service] = lambda: mock_adk_session_service

        yield app

        app.dependency_overrides.clear()

@pytest.fixture
def client(app):
    """Provides a TestClient for the app."""
    with TestClient(app) as c:
        yield c

# --- Test Class ---

class TestVoiceChatHandler:

    async def test_successful_connection(self, client, mock_auth_manager, mock_adk_session_service, mock_voice_service):
        """Test that a WebSocket connection is accepted with valid credentials."""
        with client.websocket_connect("/voice/ws/test_session?token=valid_token") as websocket:
            assert mock_auth_manager.get_user_by_token.called
            assert mock_adk_session_service.get_session.called
            mock_voice_service.create_voice_session.assert_called_once()
            websocket.close()

    async def test_authentication_failure(self, client, mock_auth_manager):
        """Test that the connection is rejected if the token is invalid."""
        mock_auth_manager.get_user_by_token.side_effect = AuthenticationError("Invalid token")

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/voice/ws/test_session?token=invalid_token") as websocket:
                # The server should close the connection, which receive() will detect.
                websocket.receive_text()

        assert exc_info.value.code == 4000

    async def test_token_expired_failure(self, client, mock_auth_manager):
        """Test that the connection is rejected if the token is expired."""
        mock_auth_manager.get_user_by_token.side_effect = TokenExpiredError("Token expired")

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/voice/ws/test_session?token=expired_token") as websocket:
                websocket.receive_text()

        assert exc_info.value.code == 4000

    async def test_missing_chat_session(self, client, mock_adk_session_service):
        """Test connection rejection if the initial chat session is not found."""
        mock_adk_session_service.get_session.return_value = None

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/voice/ws/nonexistent_session?token=valid_token") as websocket:
                websocket.receive_text()

        assert exc_info.value.code == 4000

    @patch('role_play.voice.handler.base64.b64decode')
    async def test_client_to_agent_audio(self, mock_b64decode, client, mock_voice_service):
        """Test that audio messages from the client are forwarded to the agent queue."""
        _, mock_queue = mock_voice_service.create_voice_session.return_value

        mock_called_event = asyncio.Event()

        def side_effect(data):
            mock_called_event.set()
            return b'decoded_audio'

        mock_b64decode.side_effect = side_effect

        with client.websocket_connect("/voice/ws/test_session?token=valid_token") as websocket:
            websocket.send_json({"type": "audio", "data": "encoded_audio"})

            try:
                await asyncio.wait_for(mock_called_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pytest.fail("mock_b64decode was not called within timeout.")

        mock_b64decode.assert_called_once_with("encoded_audio")
        mock_queue.send_realtime.assert_called_once_with(b'decoded_audio')

    async def test_agent_to_client_events(self, client, mock_voice_service):
        """Test that events from the agent are correctly sent to the client."""
        async def mock_event_generator():
            yield MagicMock(spec=[], turn_complete=True, interrupted=False, content=None, partial=False, input_transcription=None, output_transcription=None)
            await asyncio.sleep(0.01)
            yield MagicMock(spec=['input_transcription'], turn_complete=False, interrupted=False, content=None, partial=False, input_transcription=MagicMock(text="hello user"), output_transcription=None)

        mock_queue = AsyncMock()
        mock_queue.close = MagicMock()
        mock_voice_service.create_voice_session.return_value = (mock_event_generator(), mock_queue)

        with client.websocket_connect("/voice/ws/test_session?token=valid_token") as websocket:
            data1 = websocket.receive_json()
            assert data1 == {"type": "turn_status", "turn_complete": True, "interrupted": False}

            data2 = websocket.receive_json()
            assert data2 == {"type": "transcript", "role": "user", "text": "hello user"}

    async def test_cleanup_on_disconnect(self, client, mock_adk_session_service, mock_voice_service):
        """Test that resources are cleaned up when the client disconnects."""
        _, mock_queue = mock_voice_service.create_voice_session.return_value

        with client.websocket_connect("/voice/ws/test_session?token=valid_token") as websocket:
            # Connect and immediately disconnect by exiting the 'with' block
            pass

        await asyncio.sleep(0.05)

        mock_queue.close.assert_called_once()
        mock_adk_session_service.delete_session.assert_called_once_with(
            app_name="roleplay_voice",
            user_id="test_user",
            session_id="test_session"
        )
