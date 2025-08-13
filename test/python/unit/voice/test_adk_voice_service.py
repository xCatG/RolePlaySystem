import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# The test file is inside test/python/unit/voice, so we need to adjust the path
# to import from src/python/role_play/voice
import sys
from pathlib import Path

# Add the src/python directory to the Python path
# This is a common pattern in this project's tests
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'src' / 'python'))

from role_play.voice.adk_voice_service import ADKVoiceService

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture
def voice_service():
    """Provides an instance of ADKVoiceService for testing."""
    return ADKVoiceService()

class TestADKVoiceService:

    @patch('role_play.voice.adk_voice_service.get_production_agent', new_callable=AsyncMock)
    @patch('role_play.voice.adk_voice_service.InMemoryRunner')
    @patch('role_play.voice.adk_voice_service.LiveRequestQueue')
    @patch('role_play.voice.adk_voice_service.RunConfig')
    async def test_create_voice_session_success(
        self,
        MockRunConfig,
        MockLiveRequestQueue,
        MockInMemoryRunner,
        mock_get_agent,
        voice_service
    ):
        """
        Tests that create_voice_session successfully creates and configures a session
        when the agent is found.
        """
        # Arrange
        mock_agent = MagicMock()
        mock_get_agent.return_value = mock_agent

        mock_runner_instance = MockInMemoryRunner.return_value
        mock_runner_instance.session_service.create_session = AsyncMock()
        mock_live_events = "mock_live_events"
        mock_runner_instance.run_live.return_value = mock_live_events

        mock_queue_instance = MockLiveRequestQueue.return_value

        # Act
        live_events, live_request_queue = await voice_service.create_voice_session(
            session_id="test_session",
            user_id="test_user",
            character_id="test_char",
            scenario_id="test_scenario",
            language="en"
        )

        # Assert
        mock_get_agent.assert_called_once_with(
            character_id="test_char",
            scenario_id="test_scenario",
            language="en",
            scripted=False
        )
        MockInMemoryRunner.assert_called_once_with(app_name="roleplay_voice", agent=mock_agent)

        mock_runner_instance.session_service.create_session.assert_called_once()

        MockRunConfig.assert_called_once() # Verify that run config is being created

        mock_runner_instance.run_live.assert_called_once()

        assert live_events == mock_live_events
        assert live_request_queue == mock_queue_instance

    @patch('role_play.voice.adk_voice_service.get_production_agent', new_callable=AsyncMock)
    async def test_create_voice_session_agent_creation_fails(self, mock_get_agent, voice_service):
        """
        Tests that create_voice_session raises a ValueError if the agent cannot be created.
        """
        # Arrange
        mock_get_agent.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Could not create agent for character 'test_char' and scenario 'test_scenario'"):
            await voice_service.create_voice_session(
                session_id="test_session",
                user_id="test_user",
                character_id="test_char",
                scenario_id="test_scenario",
                language="en"
            )

        mock_get_agent.assert_called_once_with(
            character_id="test_char",
            scenario_id="test_scenario",
            language="en",
            scripted=False
        )
