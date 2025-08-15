"""ADK voice service for managing live streaming sessions."""

from __future__ import annotations

from typing import AsyncGenerator, Tuple, Optional

from google.adk.runners import InMemoryRunner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.genai.types import AudioTranscriptionConfig

from ..dev_agents.roleplay_agent.agent import get_production_agent


class ADKVoiceService:
    """Service that creates and manages ADK live sessions for voice chat."""

    async def create_voice_session(
        self,
        session_id: str,
        user_id: str,
        character_id: str,
        scenario_id: str,
        language: str,
        script_data: Optional[dict] = None,
    ) -> Tuple[AsyncGenerator, LiveRequestQueue]:
        """Create and start an ADK live session.

        Args:
            session_id: Identifier for the conversation session.
            user_id: Identifier of the connected user.
            character_id: Character identifier for the role play.
            scenario_id: Scenario identifier for the role play.
            language: Language code for the interaction.
            script_data: Optional script information if the session is scripted.

        Returns:
            Tuple containing an async generator of live events and the request queue
            used to send messages to the agent.
        """
        agent = await get_production_agent(
            character_id=character_id,
            scenario_id=scenario_id,
            language=language,
            scripted=bool(script_data),
        )

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
            state=initial_state,
        )

        run_config = RunConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=AudioTranscriptionConfig(),
            input_audio_transcription=AudioTranscriptionConfig(),
        )

        live_request_queue = LiveRequestQueue()

        live_events = runner.run_live(
            session=session,
            live_request_queue=live_request_queue,
            run_config=run_config,
        )

        return live_events, live_request_queue
