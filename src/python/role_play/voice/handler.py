"""Simplified voice chat handler for real-time interactions."""

import asyncio
import logging
import base64
from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect, Query, HTTPException, APIRouter
from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.genai.types import AudioTranscriptionConfig

from ..server.base_handler import BaseHandler
from ..server.dependencies import (
    get_chat_logger, get_adk_session_service, get_storage_backend, get_auth_manager
)
from ..common.models import User
from ..common.time_utils import utc_now_isoformat
from ..chat.chat_logger import ChatLogger
from ..dev_agents.roleplay_agent.agent import get_production_agent
from google.adk.sessions import InMemorySessionService

from .models import (
    VoiceClientRequest, VoiceSessionInfo, TranscriptPartialMessage,
    TranscriptFinalMessage, VoiceConfigMessage, VoiceStatusMessage,
    VoiceErrorMessage, AudioChunkMessage, TurnStatusMessage,
    VoiceSessionResponse, VoiceSessionStats
)
from .adk_voice_service import LiveVoiceSession

logger = logging.getLogger(__name__)

class VoiceChatHandler(BaseHandler):
    """Handler for voice chat WebSocket connections."""

    def __init__(self):
        super().__init__()
        self.active_sessions: Dict[str, LiveVoiceSession] = {}

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()
            self._router.websocket("/ws/{session_id}")(self.voice_websocket_endpoint)
            self._router.get("/session/{session_id}/info")(self.get_session_info)
            self._router.get("/session/{session_id}/stats")(self.get_session_stats)
        return self._router

    @property
    def prefix(self) -> str:
        return "/voice"

    async def voice_websocket_endpoint(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="Missing token parameter")
            return
        await self.handle_voice_session(websocket, session_id, token)

    async def handle_voice_session(self, websocket: WebSocket, session_id: str, token: str):
        """Handle the entire lifecycle of a voice chat WebSocket connection."""
        user, voice_session = None, None
        try:
            logger.info(f"Voice WebSocket connection attempt for session {session_id}")
            user = await self._validate_jwt_token(token)
            if not user:
                await websocket.close(code=1008, reason="Invalid authentication token")
                return

            storage = get_storage_backend()
            chat_logger = get_chat_logger(storage)
            adk_session_service = get_adk_session_service()
            
            adk_session = await self._validate_session(session_id, user.id, adk_session_service, chat_logger)
            if not adk_session:
                await websocket.close(code=1008, reason="Session not found or access denied")
                return

            await websocket.send_json(VoiceStatusMessage(status="connecting", message="Initializing voice session").dict())
            
            voice_session = await self._create_live_session(session_id, user, adk_session, adk_session_service)
            self.active_sessions[session_id] = voice_session

            await self._send_voice_config(websocket, user)
            await chat_logger.log_voice_session_start(user.id, session_id, voice_config=voice_session.adk_session.state.get("voice_config"))
            await websocket.send_json(VoiceStatusMessage(status="ready", message="Voice session ready").dict())

            await self._handle_bidirectional_streaming(websocket, voice_session, chat_logger)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"Voice session error for {session_id}: {e}", exc_info=True)
            try:
                await websocket.send_json(VoiceErrorMessage(error=str(e), timestamp=utc_now_isoformat()).dict())
            except:
                pass  # Connection might be closed
        finally:
            if voice_session:
                final_stats = await voice_session.cleanup()
                if user:
                    storage = get_storage_backend()
                    chat_logger = get_chat_logger(storage)
                    await chat_logger.log_voice_session_end(user.id, session_id, voice_stats=final_stats)
                self.active_sessions.pop(session_id, None)
                logger.info(f"Voice session {session_id} cleanup completed.")

    async def _create_live_session(self, session_id: str, user: User, adk_session: Any, adk_session_service: InMemorySessionService) -> LiveVoiceSession:
        """Create and configure a new LiveVoiceSession."""
        agent = await get_production_agent(
            character_id=adk_session.state.get("character_id"),
            scenario_id=adk_session.state.get("scenario_id"),
            language=getattr(user, 'preferred_language', 'en'),
            scripted=bool(adk_session.state.get("script_data"))
        )
        if not agent:
            raise ValueError("Failed to create roleplay agent")

        runner = Runner(app_name="roleplay_voice", agent=agent)
        run_config = RunConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=AudioTranscriptionConfig(),
            input_audio_transcription=AudioTranscriptionConfig()
        )
        live_request_queue = LiveRequestQueue()
        live_events = runner.run_live(session=adk_session, live_request_queue=live_request_queue, run_config=run_config)
        
        return LiveVoiceSession(session_id, user.id, runner, live_events, live_request_queue, adk_session)

    async def _send_voice_config(self, websocket: WebSocket, user: User):
        """Send voice configuration to the client."""
        voice_config = VoiceConfigMessage(
            audio_format="pcm", sample_rate=16000, channels=1, bit_depth=16,
            language=getattr(user, 'preferred_language', 'en'), voice_name="Aoede"
        )
        await websocket.send_json(voice_config.dict())

    async def _handle_bidirectional_streaming(self, websocket: WebSocket, voice_session: LiveVoiceSession, chat_logger: ChatLogger):
        """Manage concurrent send and receive tasks for the WebSocket connection."""
        receive_task = asyncio.create_task(self._receive_from_client(websocket, voice_session))
        send_task = asyncio.create_task(self._send_to_client(websocket, voice_session, chat_logger))
        
        done, pending = await asyncio.wait([receive_task, send_task], return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()

    async def _receive_from_client(self, websocket: WebSocket, voice_session: LiveVoiceSession):
        """Receive messages from the client and forward them to the voice session."""
        while voice_session.active:
            data = await websocket.receive_text()
            request = VoiceClientRequest.model_validate_json(data)
            if request.end_session:
                await voice_session.end_session()
                break
            if request.mime_type == "audio/pcm":
                await voice_session.send_audio(request.decode_data(), request.mime_type)
            elif request.mime_type == "text/plain":
                await voice_session.send_text(request.decode_data())

    async def _send_to_client(self, websocket: WebSocket, voice_session: LiveVoiceSession, chat_logger: ChatLogger):
        """Process events from the voice session and send them to the client."""
        message_counter = 0
        async for event in voice_session.process_events():
            if not voice_session.active:
                break
            
            event_type = event.get("type")
            message_to_send = None

            if event_type == "audio_chunk":
                # Base64 encode audio data for WebSocket transmission
                event_copy = event.copy()
                event_copy["data"] = base64.b64encode(event["data"]).decode('utf-8')
                message_to_send = AudioChunkMessage(**event_copy).dict()
            elif event_type == "transcript_partial":
                message_to_send = TranscriptPartialMessage(**event).dict()
            elif event_type == "transcript_final":
                message_to_send = TranscriptFinalMessage(**event).dict()
                message_counter += 1
                await chat_logger.log_voice_message(
                    user_id=voice_session.user_id, session_id=voice_session.session_id,
                    role=event["role"], transcript_text=event["text"],
                    duration_ms=event["duration_ms"], confidence=event["confidence"],
                    message_number=message_counter, voice_metadata=event["metadata"]
                )
            elif event_type == "turn_status":
                message_to_send = TurnStatusMessage(**event).dict()
            elif event_type == "error":
                message_to_send = VoiceErrorMessage(**event).dict()

            if message_to_send:
                await websocket.send_json(message_to_send)

    async def _validate_jwt_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return user."""
        try:
            storage = get_storage_backend()
            auth_manager = get_auth_manager(storage)
            token_data = auth_manager.verify_token(token)
            return await storage.get_user(token_data.user_id)
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            return None

    async def _validate_session(self, session_id: str, user_id: str, adk_session_service: InMemorySessionService, chat_logger: ChatLogger) -> Optional[Any]:
        """Validate that a chat session exists and belongs to the user."""
        adk_session = await adk_session_service.get_session("roleplay_chat", user_id, session_id)
        if adk_session:
            return adk_session
        if await chat_logger.get_session_end_info(user_id, session_id):
            logger.warning(f"Attempted to connect to ended session {session_id}")
            return None
        logger.warning(f"Session {session_id} not found for user {user_id}")
        return None

    async def get_session_info(self, session_id: str, token: str = Query(...)) -> VoiceSessionResponse:
        """Get voice session information."""
        user = await self._validate_jwt_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        voice_session = self.active_sessions.get(session_id)
        if not voice_session or voice_session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Voice session not found")
            
        adk_state = voice_session.adk_session.state if voice_session.adk_session else {}
        session_info = VoiceSessionInfo(
            session_id=session_id, user_id=user.id,
            character_id=adk_state.get("character_id"),
            scenario_id=adk_state.get("scenario_id"),
            language=adk_state.get("language", "en"),
            started_at=voice_session.stats.get("started_at"),
            transcript_available=True
        )
        return VoiceSessionResponse(success=True, session_info=session_info)

    async def get_session_stats(self, session_id: str, token: str = Query(...)) -> VoiceSessionResponse:
        """Get voice session statistics."""
        user = await self._validate_jwt_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        voice_session = self.active_sessions.get(session_id)
        if not voice_session or voice_session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Voice session not found")
            
        stats = VoiceSessionStats(session_id=session_id, **voice_session.get_stats())
        return VoiceSessionResponse(success=True, stats=stats)