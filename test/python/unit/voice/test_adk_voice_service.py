import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from role_play.voice.adk_voice_service import ADKVoiceService


@pytest.mark.asyncio
async def test_create_voice_session_sets_up_runner():
    service = ADKVoiceService()

    with (
        patch("role_play.voice.adk_voice_service.get_production_agent", AsyncMock(return_value="agent")) as get_agent,
        patch("role_play.voice.adk_voice_service.InMemoryRunner") as RunnerMock,
        patch("role_play.voice.adk_voice_service.RunConfig") as RunConfigMock,
        patch("role_play.voice.adk_voice_service.LiveRequestQueue") as QueueMock,
        patch("role_play.voice.adk_voice_service.AudioTranscriptionConfig") as ATConfigMock,
    ):
        session_service = AsyncMock()
        session_service.create_session.return_value = SimpleNamespace()
        runner_instance = Mock()
        runner_instance.session_service = session_service
        runner_instance.run_live.return_value = "events"
        RunnerMock.return_value = runner_instance

        queue_instance = Mock()
        QueueMock.return_value = queue_instance
        run_config_instance = Mock()
        RunConfigMock.return_value = run_config_instance

        events, queue = await service.create_voice_session(
            session_id="sess", user_id="user", character_id="char", scenario_id="scen", language="en"
        )

        assert events == "events"
        assert queue is queue_instance
        get_agent.assert_awaited_with(
            character_id="char", scenario_id="scen", language="en", scripted=False
        )
        RunnerMock.assert_called_with(app_name="roleplay_voice", agent="agent")
        session_service.create_session.assert_awaited_with(
            app_name="roleplay_voice", user_id="user", session_id="sess", state={
                "character_id": "char",
                "scenario_id": "scen",
                "script_data": None,
                "language": "en",
            }
        )
        runner_instance.run_live.assert_called_with(
            session=session_service.create_session.return_value,
            live_request_queue=queue_instance,
            run_config=run_config_instance,
        )
