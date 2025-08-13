# src/python/role_play/voice/adk_voice_service.py

from typing import AsyncGenerator, Tuple
from google.adk.runners import InMemoryRunner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.genai.types import AudioTranscriptionConfig, Content, Part, Blob

# Reuse your existing agent retrieval logic
from ..dev_agents.roleplay_agent.agent import get_production_agent

class ADKVoiceService:
    """Manages ADK live streaming sessions for voice chat."""

    async def create_voice_session(
        self,
        session_id: str,
        user_id: str,
        character_id: str,
        scenario_id: str,
        language: str,
        script_data: dict | None = None,
    ) -> Tuple[AsyncGenerator, LiveRequestQueue]:
        """Creates and starts an ADK live session."""

        agent = await get_production_agent(
            character_id=character_id,
            scenario_id=scenario_id,
            language=language,
            scripted=bool(script_data)
        )

        if not agent:
            raise ValueError(f"Could not create agent for character '{character_id}' and scenario '{scenario_id}'.")

        runner = InMemoryRunner(app_name="roleplay_voice", agent=agent)

        initial_state = {
            "character_id": character_id,
            "scenario_id": scenario_id,
            "script_data": script_data,
            "language": language,
        }

        session = await runner.session_service.create_session(
            app_name="roleplay_voice",
            user_id=user_id,
            session_id=session_id,
            state=initial_state
        )

        # Configure for audio response and enable transcriptions
        run_config = RunConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=AudioTranscriptionConfig(),
            input_audio_transcription=AudioTranscriptionConfig()
        )

        live_request_queue = LiveRequestQueue()

        live_events = runner.run_live(
            session=session,
            live_request_queue=live_request_queue,
            run_config=run_config
        )

        return live_events, live_request_queue
