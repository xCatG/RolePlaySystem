import asyncio
import base64
import logging
from typing import Optional, Dict, Any, Protocol, Annotated

from fastapi import WebSocket, HTTPException, APIRouter, Depends
from google.adk import Runner
from google.adk.agents import RunConfig, LiveRequestQueue
from google.adk.sessions import BaseSessionService
from google.genai import types
from google.genai.types import AudioTranscriptionConfig, Blob, Part, Content
from starlette.websockets import WebSocketDisconnect

from .models import VoiceRequest
from .voice_config import VoiceConfig
from ..chat.chat_logger import ChatLogger
from ..common.exceptions import TokenExpiredError, AuthenticationError
from ..common.models import User, EnvironmentInfo
from ..common.storage import StorageBackend
from ..common.time_utils import utc_now_isoformat
from ..dev_agents.roleplay_agent.agent import get_production_agent
from ..server.base_handler import BaseHandler
from ..server.dependencies import (
    get_chat_logger,
    get_adk_session_service,
    get_storage_backend, get_auth_manager, get_environment_info,
)

logger = logging.getLogger(__name__)

class ADKEvent(Protocol):
    """Protocol for ADK live event types."""
    author: str
    turn_complete: Optional[bool]
    interrupted: Optional[bool]
    partial: Optional[bool]
    content: Optional[Any]

class VoiceHandler(BaseHandler):
    """Handler for voice chat.

    /voice/ws needs a valid session_id to work; call /chat/session to create a new session
    and use its session_id for voice chat

    """

    def __init__(self):
        super().__init__()

    # All dependencies (ResourceLoader, ChatLogger, InMemorySessionService)
    # will be injected via FastAPI's Depends in the route methods.

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

            # WebSocket endpoint for voice chat
            @self._router.websocket("/ws/{session_id}")
            async def voice_websocket_endpoint(
                    websocket: WebSocket,
                    session_id: str,
                    environment_info: Annotated[EnvironmentInfo, Depends(get_environment_info)]
            ):
                # Accept the WebSocket connection first
                await websocket.accept()

                # Extract token from query parameters
                token = websocket.query_params.get("token")
                if not token:
                    await websocket.close(code=VoiceConfig.WS_MISSING_TOKEN, reason="Missing token parameter")
                    return

                await self.handle_voice_session(websocket, session_id, token, environment_info)

        return self._router

    @property
    def prefix(self) -> str:
        return "/voice"

    async def handle_voice_session(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        env_info: EnvironmentInfo,
    ):
        user, adk_components = None, None
        try:
            storage = get_storage_backend()
            """Handle a voice chat WebSocket connection."""
            user = await self._validate_jwt_token(token, storage)
            if user is None:
                logger.error(f"Invalid token for session {session_id}")
                await websocket.close(code=VoiceConfig.WS_INVALID_TOKEN, reason="Invalid token")
                return

            # Check session limits per user
            if not self._check_session_limit(user.id, storage):
                await websocket.close(code=VoiceConfig.WS_INVALID_TOKEN, reason="Maximum sessions per user exceeded")
                return
            adk_session_service: BaseSessionService = get_adk_session_service()
            adk_session = await adk_session_service.get_session(
                app_name="roleplay_chat", user_id=user.id, session_id=session_id
            )
            if not adk_session:
                logger.error(f"Session not found {session_id}")
                await websocket.close(code=VoiceConfig.WS_SESSION_NOT_FOUND, reason="Session not found")
                return

            chat_logger = get_chat_logger(storage)
            logger.info(f"Voice WebSocket connected for session {session_id}, user {user.id}")

            # Send initial status
            await websocket.send_json({
                "type": "status",
                "status": "connecting",
                "message": "Initializing voice session"
            })

            adk_components = await self._initialize_adk(session_id=session_id, user=user, adk_session=adk_session, adk_session_service=adk_session_service)

            user_lang = getattr(user, 'preferred_language', 'en')
            # Send configuration
            await websocket.send_json({
                "type": "config",
                "audio_format": VoiceConfig.AUDIO_FORMAT,
                "sample_rate": VoiceConfig.AUDIO_SAMPLE_RATE,
                "channels": VoiceConfig.AUDIO_CHANNELS,
                "bit_depth": VoiceConfig.AUDIO_BIT_DEPTH,
                "language": user_lang
            })

            await chat_logger.log_voice_session_start(user.id, session_id, voice_config={
                "language": user_lang
            })

            await websocket.send_json({
                "type": "status",
                "status": "ready",
                "message": "Voice session ready"
            })

            # Handle bidirectional streaming
            await self._handle_streaming(websocket, adk_components, chat_logger, user.id, env_info)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
            await self._handle_connection_error(session_id, adk_components)
        except ConnectionError as e:
            logger.error(f"Connection error for session {session_id}: {e}")
            await self._handle_connection_error(session_id, adk_components)
        except Exception as e:
            logger.error(f"Unexpected error for session {session_id}: {e}", exc_info=True)
            await self._handle_connection_error(session_id, adk_components)
            try:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                    "timestamp": utc_now_isoformat()
                })
            except:
                pass  # Connection might be closed
        finally:
            # Note: We only clean up adk component, and log a voice_session_end message to the log
            # the actual chat session is still "active" until chat_logger.end_session() is called!
            if adk_components is not None:
                stats = await self._cleanup_adk(adk_components)
                if user:
                    storage = get_storage_backend()
                    chat_logger = get_chat_logger(storage)
                    await chat_logger.log_voice_session_end(user.id, session_id, voice_stats=stats)
                logger.info(f"Voice session {session_id} cleanup completed")

    async def _handle_streaming(self, websocket: WebSocket, adk: Dict[str, Any], chat_logger: ChatLogger, user_id: str,
                                env_info):
        """Handle bidirectional streaming with direct ADK integration."""
        receive_task = asyncio.create_task(self._receive_from_client(websocket, adk, chat_logger, env_info))
        send_task = asyncio.create_task(self._send_to_client(websocket, adk, chat_logger, user_id, env_info))

        done, pending = await asyncio.wait([receive_task, send_task], return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()

    async def _receive_from_client(self, websocket: WebSocket, adk: Dict[str, Any], chat_logger, env_info):
        """Receive from client and send directly to ADK."""

        try:
            while adk["active"]:
                data = await websocket.receive_text()

                try:
                    request = VoiceRequest.model_validate_json(data)
                except ValueError as e:
                    logger.warning(f"Received invalid JSON: {e}")
                    adk["stats"]["errors"] += 1
                    continue

                if request.end_session:
                    adk["active"] = False
                    adk["live_request_queue"].close()
                    break

                try:
                    if request.mime_type == "audio/pcm":
                        try:
                            audio_data = request.decode_data()
                            if audio_data is None:
                                logger.warning("Audio decode returned None")
                                adk["stats"]["errors"] += 1
                                continue
                            
                            # In dev/beta environments, log the incoming PCM audio for debugging.
                            if not env_info.is_production:
                                try:
                                    # This assumes a new method `log_pcm_audio` exists in ChatLogger
                                    await chat_logger.log_pcm_audio(
                                        user_id=adk["user_id"],
                                        session_id=adk["session_id"],
                                        audio_data=audio_data
                                    )
                                except AttributeError:
                                    logger.warning("chat_logger.log_pcm_audio not implemented, skipping audio logging.")
                                except Exception as e:
                                    logger.error(f"Failed to log PCM audio for session {adk['session_id']}: {e}")
                            
                            blob = Blob(mime_type=request.mime_type, data=audio_data)
                            adk["live_request_queue"].send_realtime(blob)
                            adk["stats"]["audio_chunks_sent"] += 1
                            
                            # Send acknowledgment that audio was received and forwarded
                            audio_ack = {
                                "type": "audio_received",
                                "size_bytes": len(audio_data),
                                "timestamp": utc_now_isoformat()
                            }
                            await websocket.send_json(audio_ack)
                            logger.debug(f"Sent audio acknowledgment: {len(audio_data)} bytes")
                            
                        except Exception as decode_error:
                            logger.exception(f"Audio decode error: {decode_error}")
                            adk["stats"]["errors"] += 1
                            continue
                        
                    elif request.mime_type == "text/plain":
                        try:
                            text_data = request.decode_data()
                            if text_data is None:
                                logger.warning("Text decode returned None")
                                adk["stats"]["errors"] += 1
                                continue
                            # log user's text message (if they type), this should be fine but we don't have message_number as we don't
                            # track that in a websocket session
                            await chat_logger.log_message(
                                user_id=adk["user_id"], session_id=adk["session_id"],role="user",content=text_data, message_number=-1
                            )
                            content = Content(parts=[Part(text=text_data)])
                            adk["live_request_queue"].send_content(content)
                            adk["stats"]["text_chunks_sent"] += 1
                        except Exception as decode_error:
                            logger.error(f"Text decode error: {decode_error}")
                            adk["stats"]["errors"] += 1
                            continue
                except ValueError as e:
                    logger.warning(f"Data Validation Error: {e}")
                    adk["stats"]["errors"] += 1
                except Exception as e:
                    logger.error(f"Unexpected error when sending to ADK: {e}")
                    adk["stats"]["errors"] += 1

        except WebSocketDisconnect:
            logger.info(f"Client disconnected from session {adk['session_id']}")
            adk["active"] = False
        except Exception as e:
            logger.error(f"Error receiving from client: {e}")
            adk["active"] = False

    async def _send_to_client(self, websocket: WebSocket, adk: Dict[str, Any], chat_logger: ChatLogger, user_id: str,
                              env_info):
        """Process ADK events directly and send to client."""
        message_counter = 0
        try:
            # adk["live_events"] is of type AsyncGenerator[Event, None]
            async for event in adk["live_events"]:
                if not adk["active"]:
                    break

                message_counter += 1
                logger.debug(f"Processing event #{message_counter} from ADK live stream")
                message = self._process_adk_event(event, adk["stats"])

                if message is not None:
                    # log transcript final, we will also want to log the input PCM eventually?
                    if message["type"] == "transcript_final":
                        await chat_logger.log_voice_message(
                            user_id=adk["user_id"], session_id=adk["session_id"],
                            role=message["role"], transcript_text=message["text"], duration_ms=0,message_number=-1,
                            confidence=0,
                            voice_metadata=message
                        )
                    logger.debug(f"Sending message to client: {message['type']}")
                    await websocket.send_json(message)
                else:
                    logger.debug(f"Event #{message_counter} produced no message to send")

        except asyncio.CancelledError:
            logger.info(f"Event processing cancelled for session {adk['session_id']}")
        except ConnectionError as e:
            logger.error(f"Connection error during event processing: {e}")
            adk["stats"]["errors"] += 1
        except Exception as e:
            logger.error(f"Unexpected error processing events: {e}", exc_info=True)
            adk["stats"]["errors"] += 1
            try:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                    "timestamp": utc_now_isoformat()
                })
            except:
                pass  # Connection might be closed

    def _process_adk_event(self, event: ADKEvent, stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        stats["transcripts_processed"] += 1
        
        # Debug logging to track event types
        event_type = type(event).__name__
        event_attrs = [attr for attr in ["partial", "turn_complete", "interrupted", "content"] if hasattr(event, attr)]
        logger.debug(f"Processing ADK event: {event_type}, attributes: {event_attrs}")

        if hasattr(event, "content") and (event.content is not None) and (event.content.parts is not None):
            for part in event.content.parts:
                # Check for text content (transcripts)
                if hasattr(part, "text") and part.text:
                    # This is a transcript embedded in content
                    is_partial = getattr(event, "partial", False)
                    role = "assistant" if hasattr(event.content, "role") and event.content.role == "model" else "user"
                    
                    logger.debug(f"Processing content text as transcript: role={role}, partial={is_partial}, text='{part.text[:50]}...'")
                    
                    if is_partial:
                        return {
                            "type": "transcript_partial",
                            "text": part.text,
                            "role": role,
                            "stability": 1.0,
                            "timestamp": utc_now_isoformat()
                        }
                    else:

                        return {
                            "type": "transcript_final",
                            "text": part.text,
                            "role": role,
                            "confidence": 1.0,
                            "timestamp": utc_now_isoformat()
                        }
                        
                # Check for audio content
                elif hasattr(part, "inline_data") and part.inline_data is not None:
                    # inline_data is a Blob object with .data (bytes) and .mime_type (str)
                    audio_data = getattr(part.inline_data, "data", None)
                    mime_type = getattr(part.inline_data, "mime_type", "audio/pcm")
                    
                    if audio_data and len(audio_data) > 0:
                        stats["audio_chunks_received"] += 1
                        logger.debug(f"Received audio chunk: {len(audio_data)} bytes, type: {mime_type}")
                        return {
                            "type": "audio",
                            "data": base64.b64encode(audio_data).decode("utf-8"),
                            "mime_type": mime_type,
                            "timestamp": utc_now_isoformat()
                        }

        # Process turn status last, only if no content was processed
        if hasattr(event, "turn_complete") or hasattr(event, "interrupted") or hasattr(event, "partial"):
            return {
                "type": "turn_status",
                "partial": getattr(event, "partial"),
                "turn_complete": getattr(event, "turn_complete"),
                "interrupted": getattr(event, "interrupted"),
                "timestamp": utc_now_isoformat()
            }

        # event contained nothing we can process
        return None

    async def _initialize_adk(self, session_id: str, user: User, adk_session: Any,
                              adk_session_service: BaseSessionService) -> Dict[str, Any]:
        """Initialize ADK components directly."""
        # Create agent
        agent = await get_production_agent(
            character_id=adk_session.state.get("character_id"),
            scenario_id=adk_session.state.get("scenario_id"),
            language=getattr(user, 'preferred_language', 'en'),
            scripted=bool(adk_session.state.get("script_data")),
            agent_model="gemini-2.5-flash-live-preview",
        )
        if not agent:
            raise ValueError("Failed to create roleplay agent")

        # Create runner and start live streaming
        runner = Runner(app_name="roleplay_chat", agent=agent, session_service=adk_session_service)
        run_config = RunConfig(
            response_modalities=[types.Modality.AUDIO],
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

    async def _handle_connection_error(self, session_id: str, adk_components: Optional[Dict] = None):
        """Clean up resources on connection error."""
        if adk_components:
            try:
                await self._cleanup_adk(adk_components)
            except Exception as e:
                logger.error(f"Error during cleanup for {session_id}: {e}")
            finally:
                logger.info(f"Cleaned up session {session_id} after connection error")

    @staticmethod
    async def _cleanup_adk(adk: Dict[str, Any]) -> Dict[str, Any]:
        """Cleanup ADK components."""
        adk["active"] = False
        if adk["live_request_queue"]:
            adk["live_request_queue"].close()

        stats = {**adk["stats"], "ended_at": utc_now_isoformat()}
        logger.info(f"Session {adk['session_id']} stats: {stats}")
        return stats

    @staticmethod
    async def _validate_jwt_token(token: str, storage: StorageBackend) -> Optional[User]:
        """Validate JWT token and return user."""
        try:
            auth_manager = get_auth_manager(storage)
            token_data = auth_manager.verify_token(token)
            user = await storage.get_user(token_data.user_id)
            if user is None:
                raise HTTPException(status_code=401, detail="User not found")
            return user
        except TokenExpiredError as exc:
            raise HTTPException(status_code=401, detail="Token expired") from exc
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            raise HTTPException(status_code=401, detail="Unknown error during validation") from e

    def _check_session_limit(self, user_id: str, storage: StorageBackend) -> bool:
        """
        Check if user hasn't exceeded session limit.

        TODO: Implement distributed session tracking via storage backend
        For now, always return True (no limit enforcement).

        Future implementation:
        - Store active sessions in storage: voice_sessions/{user_id}/active/{session_id}
        - Include server_id, started_at timestamp
        - Clean up stale sessions (>1 hour old)
        - Count active sessions across all servers
        - Enforce MAX_SESSIONS_PER_USER limit

        Example:
            active_sessions = await storage.list_keys(f"voice_sessions/{user_id}/active/")
            # Filter stale sessions older than 1 hour
            # Return len(active_sessions) < VoiceConfig.MAX_SESSIONS_PER_USER
        """
        return True
