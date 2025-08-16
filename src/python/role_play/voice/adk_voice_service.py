import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any, Tuple, List, Annotated
from fastapi import HTTPException, Depends, APIRouter, Query
from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.sessions import InMemorySessionService
from google.genai.types import (
    Content, Part, Blob,
    AudioTranscriptionConfig,
    AudioChunk
)

from ..dev_agents.roleplay_agent.agent import get_production_agent
from ..chat.chat_logger import ChatLogger
from ..common.time_utils import utc_now_isoformat
from ..server.dependencies import get_adk_session_service

# from .transcript_manager import (
#     SessionTranscriptManager,
#     TranscriptSegment,
#     BufferedTranscript
# )

logger = logging.getLogger(__name__)


class ADKVoiceService:

    def __init__(self):
        self.active_sessions: Dict[str, 'VoiceSession'] = {}

    async def create_voice_session(
        self,
        session_id: str,
        user_id: str,
        character_id: str,
        scenario_id: str,
        language: str,
        adk_session_service: InMemorySessionService, # this is passed from actual handler, don't do DI here
        script_data: Optional[dict] = None,
    ) -> Tuple[AsyncGenerator, LiveRequestQueue]:

        agent = await get_production_agent(
            character_id=character_id,
            scenario_id=scenario_id,
            language=language,
            scripted=bool(script_data),
        )

        runner = Runner()

        #runner.run_live()

        pass


class VoiceSession:
    """
    Represents an active voice session with ADK live streaming.

    Manages the lifecycle of a voice conversation including audio streaming,
    transcript management, and cleanup.
    """

    def __init__(
            self,
            session_id: str,
            user_id: str,
            runner: Runner,
            live_events: AsyncGenerator,
            live_request_queue: LiveRequestQueue,
            #transcript_manager: SessionTranscriptManager,
            adk_session: Optional[Any] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.runner = runner
        self.live_events = live_events
        self.live_request_queue = live_request_queue
        #self.transcript_manager = transcript_manager
        self.adk_session = adk_session

        # Session state
        self.active = True
        self.event_handlers: Dict[str, callable] = {}

        # Statistics
        self.stats = {
            "started_at": utc_now_isoformat(),
            "audio_chunks_sent": 0,
            "audio_chunks_received": 0,
            "transcripts_processed": 0,
            "errors": 0
        }




