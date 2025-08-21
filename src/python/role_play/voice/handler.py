"""Direct ADK integration voice handler - radically simplified."""

import asyncio
import logging
import base64
from typing import Optional, Dict, Any, Tuple
from fastapi import WebSocket, WebSocketDisconnect, Query, HTTPException, APIRouter
from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.genai.types import AudioTranscriptionConfig, Content, Part, Blob

from ..server.base_handler import BaseHandler
from ..server.dependencies import (
    get_chat_logger, get_adk_session_service, get_storage_backend, get_auth_manager
)
from ..common.models import User
from ..common.time_utils import utc_now_isoformat
from ..chat.chat_logger import ChatLogger
from ..dev_agents.roleplay_agent.agent import get_production_agent
from google.adk.sessions import InMemorySessionService

from .models import VoiceRequest, VoiceMessage

logger = logging.getLogger(__name__)

class VoiceChatHandler(BaseHandler):
    """Direct ADK integration for voice chat."""

    def __init__(self):
        super().__init__()
        # Store active ADK components directly
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()
            self._router.websocket("/ws/{session_id}")(self.voice_websocket_endpoint)
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
        """Handle voice chat with direct ADK integration."""
        user, adk_components = None, None
        try:
            logger.info(f"Voice WebSocket connection for session {session_id}")
            
            # Validate user and session
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

            # Send initial status
            await websocket.send_json({
                "type": "status",
                "status": "connecting",
                "message": "Initializing voice session"
            })
            
            # Initialize ADK components directly
            adk_components = await self._initialize_adk(session_id, user, adk_session)
            self.active_sessions[session_id] = adk_components

            # Send configuration
            await websocket.send_json({
                "type": "config",
                "audio_format": "pcm",
                "sample_rate": 16000,
                "channels": 1,
                "bit_depth": 16,
                "language": getattr(user, 'preferred_language', 'en')
            })
            
            # Log session start
            await chat_logger.log_voice_session_start(user.id, session_id, voice_config={
                "language": getattr(user, 'preferred_language', 'en')
            })
            
            await websocket.send_json({
                "type": "status",
                "status": "ready",
                "message": "Voice session ready"
            })

            # Handle bidirectional streaming
            await self._handle_streaming(websocket, adk_components, chat_logger, user.id)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"Voice session error: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                    "timestamp": utc_now_isoformat()
                })
            except:
                pass
        finally:
            if adk_components:
                stats = await self._cleanup_adk(adk_components)
                if user:
                    storage = get_storage_backend()
                    chat_logger = get_chat_logger(storage)
                    await chat_logger.log_voice_session_end(user.id, session_id, voice_stats=stats)
                self.active_sessions.pop(session_id, None)
                logger.info(f"Voice session {session_id} cleanup completed")

    async def _initialize_adk(self, session_id: str, user: User, adk_session: Any) -> Dict[str, Any]:
        """Initialize ADK components directly."""
        # Create agent
        agent = await get_production_agent(
            character_id=adk_session.state.get("character_id"),
            scenario_id=adk_session.state.get("scenario_id"),
            language=getattr(user, 'preferred_language', 'en'),
            scripted=bool(adk_session.state.get("script_data"))
        )
        if not agent:
            raise ValueError("Failed to create roleplay agent")

        # Create runner and start live streaming
        runner = Runner(app_name="roleplay_voice", agent=agent)
        run_config = RunConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=AudioTranscriptionConfig(),
            input_audio_transcription=AudioTranscriptionConfig()
        )
        live_request_queue = LiveRequestQueue()
        live_events = runner.run_live(
            session=adk_session,
            live_request_queue=live_request_queue,
            run_config=run_config
        )
        
        return {
            "session_id": session_id,
            "user_id": user.id,
            "runner": runner,
            "live_events": live_events,
            "live_request_queue": live_request_queue,
            "adk_session": adk_session,
            "active": True,
            "stats": {
                "started_at": utc_now_isoformat(),
                "audio_chunks_sent": 0,
                "audio_chunks_received": 0,
                "transcripts_processed": 0,
                "errors": 0
            }
        }

    async def _handle_streaming(self, websocket: WebSocket, adk: Dict[str, Any], chat_logger: ChatLogger, user_id: str):
        """Handle bidirectional streaming with direct ADK integration."""
        receive_task = asyncio.create_task(self._receive_from_client(websocket, adk))
        send_task = asyncio.create_task(self._send_to_client(websocket, adk, chat_logger, user_id))
        
        done, pending = await asyncio.wait([receive_task, send_task], return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()

    async def _receive_from_client(self, websocket: WebSocket, adk: Dict[str, Any]):
        """Receive from client and send directly to ADK."""
        while adk["active"]:
            data = await websocket.receive_text()
            request = VoiceRequest.model_validate_json(data)
            
            if request.end_session:
                adk["active"] = False
                adk["live_request_queue"].close()
                break
            
            # Send directly to ADK
            if request.mime_type == "audio/pcm":
                blob = Blob(mime_type=request.mime_type, data=request.decode_data())
                await adk["live_request_queue"].send_realtime(blob)
                adk["stats"]["audio_chunks_sent"] += 1
            elif request.mime_type == "text/plain":
                content = Content(parts=[Part(text=request.decode_data())])
                await adk["live_request_queue"].send_content(content)

    async def _send_to_client(self, websocket: WebSocket, adk: Dict[str, Any], chat_logger: ChatLogger, user_id: str):
        """Process ADK events directly and send to client."""
        message_counter = 0
        
        try:
            async for event in adk["live_events"]:
                if not adk["active"]:
                    break
                
                message = self._process_adk_event(event, adk["stats"])
                if message:
                    # Log final transcripts
                    if message["type"] == "transcript_final":
                        message_counter += 1
                        await chat_logger.log_voice_message(
                            user_id=user_id,
                            session_id=adk["session_id"],
                            role=message["role"],
                            transcript_text=message["text"],
                            duration_ms=0,
                            confidence=message.get("confidence", 1.0),
                            message_number=message_counter,
                            voice_metadata={}
                        )
                    
                    # Send to client
                    await websocket.send_json(message)
                    
        except asyncio.CancelledError:
            logger.info(f"Event processing cancelled for session {adk['session_id']}")
        except Exception as e:
            logger.error(f"Error processing events: {e}")
            adk["stats"]["errors"] += 1
            await websocket.send_json({
                "type": "error",
                "error": str(e),
                "timestamp": utc_now_isoformat()
            })

    def _process_adk_event(self, event: Any, stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single ADK event directly."""
        stats["transcripts_processed"] += 1
        
        # Turn status events
        if hasattr(event, 'turn_complete') or hasattr(event, 'interrupted'):
            return {
                "type": "turn_status",
                "turn_complete": getattr(event, 'turn_complete', False),
                "interrupted": getattr(event, 'interrupted', False),
                "timestamp": utc_now_isoformat()
            }
        
        # Transcript events
        if hasattr(event, 'input_transcription') and event.input_transcription:
            return self._process_transcript(event.input_transcription, "user")
        if hasattr(event, 'output_transcription') and event.output_transcription:
            return self._process_transcript(event.output_transcription, "assistant")
        
        # Audio events
        if hasattr(event, 'content') and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    stats["audio_chunks_received"] += 1
                    return {
                        "type": "audio",
                        "data": base64.b64encode(part.inline_data.data).decode('utf-8'),
                        "mime_type": part.inline_data.mime_type,
                        "timestamp": utc_now_isoformat()
                    }
        
        return None

    def _process_transcript(self, transcription: Any, role: str) -> Dict[str, Any]:
        """Process transcript from ADK."""
        is_final = getattr(transcription, 'is_final', True)
        
        if is_final:
            return {
                "type": "transcript_final",
                "text": transcription.text,
                "role": role,
                "confidence": getattr(transcription, 'confidence', 1.0),
                "timestamp": utc_now_isoformat()
            }
        else:
            return {
                "type": "transcript_partial",
                "text": transcription.text,
                "role": role,
                "stability": getattr(transcription, 'stability', 1.0),
                "timestamp": utc_now_isoformat()
            }

    async def _cleanup_adk(self, adk: Dict[str, Any]) -> Dict[str, Any]:
        """Cleanup ADK components."""
        adk["active"] = False
        if adk["live_request_queue"]:
            adk["live_request_queue"].close()
        
        stats = {**adk["stats"], "ended_at": utc_now_isoformat()}
        logger.info(f"Session {adk['session_id']} stats: {stats}")
        return stats

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