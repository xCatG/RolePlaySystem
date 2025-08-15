"""Voice chat handler for real-time voice interactions with intelligent transcript management."""

import asyncio
import logging
import base64
import json
import os
from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect, Query, HTTPException, APIRouter, Depends
from fastapi.responses import JSONResponse

from ..server.base_handler import BaseHandler
from ..server.dependencies import (
    get_chat_logger,
    get_adk_session_service,
    get_resource_loader,
    get_storage_backend,
    get_auth_manager,
)
from ..common.models import User
from ..common.time_utils import utc_now_isoformat
from ..common.storage import StorageBackend
from ..chat.chat_logger import ChatLogger
from ..common.resource_loader import ResourceLoader
from google.adk.sessions import InMemorySessionService

from .models import (
    VoiceClientRequest,
    VoiceSessionInfo,
    TranscriptPartialMessage,
    TranscriptFinalMessage,
    VoiceConfigMessage,
    VoiceStatusMessage,
    VoiceErrorMessage,
    AudioChunkMessage,
    TurnStatusMessage,
    VoiceSessionResponse,
    VoiceTranscriptConfig,
    VoiceSessionStats
)
from .adk_voice_service import ADKVoiceService
from .transcript_manager import TranscriptSegment

logger = logging.getLogger(__name__)


class VoiceChatHandler(BaseHandler):
    """Handler for voice chat WebSocket connections with intelligent transcript management."""

    def __init__(self):
        super().__init__()
        self.voice_service = ADKVoiceService()

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()
            
            # WebSocket endpoint for voice chat
            @self._router.websocket("/ws/{session_id}")
            async def voice_websocket_endpoint(
                websocket: WebSocket,
                session_id: str,
                token: str | None = Query(None, description="JWT token (preferred via header/subprotocol)"),
            ):
                # Pre-accept auth check to avoid upgrading unauthenticated connections
                token_param = token or websocket.query_params.get("token")
                if not token_param:
                    await websocket.close(code=1008, reason="Missing token parameter")
                    return

                user = await self._prevalidate_token(token_param)
                if not user:
                    await websocket.close(code=1008, reason="Invalid authentication token")
                    return

                # Now accept the connection
                await websocket.accept()

                # Delegate to main handler (will re-validate quickly for defense in depth)
                await self.handle_voice_session(websocket, session_id, token_param)
            
            # REST endpoints for voice session management
            @self._router.get("/session/{session_id}/info")
            async def get_voice_session_info(
                session_id: str,
                token: str = Query(..., description="JWT authentication token"),
            ) -> VoiceSessionResponse:
                return await self.get_session_info(session_id, token)
            
            @self._router.get("/session/{session_id}/stats")
            async def get_voice_session_stats(
                session_id: str,
                token: str = Query(..., description="JWT authentication token"),
            ) -> VoiceSessionResponse:
                return await self.get_session_stats(session_id, token)
            
            # Simple test endpoint
            @self._router.get("/test")
            async def voice_test():
                return {"message": "Voice handler is working", "status": "ok"}
        
        return self._router

    @property
    def prefix(self) -> str:
        return "/voice"

    async def handle_voice_session(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
    ):
        """Handle a voice chat WebSocket connection with intelligent transcript management."""
        user = None
        voice_session = None
        message_counter = 0
        audio_seq = 0
        MAX_AUDIO_CHUNK_BYTES = 256 * 1024  # 256KB per chunk
        PING_INTERVAL_SEC = 20
        
        try:
            logger.info(f"Voice WebSocket connection attempt for session {session_id}")
            
            # 1. Check for missing token
            if not token:
                logger.error(f"Missing token for session {session_id}")
                await websocket.close(code=1008, reason="Missing token parameter")
                return
            
            # 2. Validate JWT token
            user = await self._validate_jwt_token(token)
            if not user:
                logger.error(f"JWT validation failed for session {session_id}")
                await websocket.close(code=1008, reason="Invalid authentication token")
                return
            
            logger.info(f"JWT validation successful for user {user.username}")
            
            # Get dependencies
            storage = get_storage_backend()
            chat_logger = get_chat_logger(storage)
            adk_session_service = get_adk_session_service()
            resource_loader = get_resource_loader()
            
            # 2. Validate session exists and belongs to user
            adk_session = await self._validate_session(
                session_id, user.id, adk_session_service, chat_logger
            )
            if not adk_session:
                await websocket.close(code=1008, reason="Session not found or access denied")
                return
            
            logger.info(f"Voice WebSocket connected for session {session_id}, user {user.id}")
            
            # Send initial status
            await websocket.send_json(
                VoiceStatusMessage(status="connecting", message="Initializing voice session").dict()
            )
            
            # 3. Create voice session with transcript configuration
            transcript_config = VoiceTranscriptConfig().dict()
            
            voice_session = await self.voice_service.create_voice_session(
                session_id=session_id,
                user_id=user.id,
                character_id=adk_session.state.get("character_id"),
                scenario_id=adk_session.state.get("scenario_id"),
                language=getattr(user, 'preferred_language', 'en'),
                script_data=adk_session.state.get("script_data"),
                adk_session_service=adk_session_service,
                transcript_config=transcript_config
            )
            
            # 4. Send voice configuration to client
            voice_config = VoiceConfigMessage(
                audio_format="pcm",
                sample_rate=16000,
                channels=1,
                bit_depth=16,
                language=getattr(user, 'preferred_language', 'en'),
                voice_name="Aoede"  # Default voice, could be character-specific
            )
            await websocket.send_json(voice_config.dict())
            
            # 5. Log voice session start
            await chat_logger.log_voice_session_start(
                user_id=user.id,
                session_id=session_id,
                voice_config=voice_config.dict()
            )
            
            # Send ready status
            await websocket.send_json(
                VoiceStatusMessage(status="ready", message="Voice session ready").dict()
            )
            
            # 6. Start bidirectional streaming with backpressure and heartbeat
            queue: asyncio.Queue = asyncio.Queue(maxsize=32)

            async def producer():
                try:
                    async for event in voice_session.process_events():
                        if event.get("type") == "transcript_partial" and queue.full():
                            # Drop partials under pressure
                            continue
                        await queue.put(event)
                except Exception as e:
                    logger.error(f"Producer error for session {session_id}: {e}")

            async def sender():
                nonlocal audio_seq, message_counter
                try:
                    while voice_session.active:
                        event = await queue.get()
                        et = event.get("type")
                        if et == "audio_chunk":
                            audio_seq += 1
                            audio_msg = AudioChunkMessage(
                                data=base64.b64encode(event["data"]).decode('utf-8'),
                                mime_type=event["mime_type"],
                                sequence=audio_seq,
                                timestamp=event["timestamp"],
                            )
                            await websocket.send_json(audio_msg.dict())
                        elif et == "transcript_partial":
                            partial_msg = TranscriptPartialMessage(
                                text=event["text"],
                                role=event["role"],
                                stability=event["stability"],
                                timestamp=event["timestamp"],
                            )
                            await websocket.send_json(partial_msg.dict())
                        elif et == "transcript_final":
                            final_msg = TranscriptFinalMessage(
                                text=event["text"],
                                role=event["role"],
                                duration_ms=event["duration_ms"],
                                confidence=event["confidence"],
                                metadata=event["metadata"],
                                timestamp=event["timestamp"],
                            )
                            await websocket.send_json(final_msg.dict())
                            # Log finalized transcript to ChatLogger
                            message_counter += 1
                            await chat_logger.log_voice_message(
                                user_id=user.id,
                                session_id=session_id,
                                role=event["role"],
                                transcript_text=event["text"],
                                duration_ms=event["duration_ms"],
                                confidence=event["confidence"],
                                message_number=message_counter,
                                voice_metadata=event["metadata"],
                            )
                        elif et == "turn_status":
                            status_msg = TurnStatusMessage(
                                turn_complete=event["turn_complete"],
                                interrupted=event.get("interrupted", False),
                                timestamp=event["timestamp"],
                            )
                            await websocket.send_json(status_msg.dict())
                        elif et == "error":
                            error_msg = VoiceErrorMessage(
                                error=event["error"],
                                timestamp=event["timestamp"],
                            )
                            await websocket.send_json(error_msg.dict())
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected in sender for session {session_id}")
                except Exception as e:
                    logger.error(f"Sender error in session {session_id}: {e}")

            async def receiver():
                try:
                    while voice_session.active:
                        frame = await websocket.receive()
                        if "bytes" in frame and frame["bytes"] is not None:
                            audio_bytes = frame["bytes"]
                            if len(audio_bytes) > MAX_AUDIO_CHUNK_BYTES:
                                await websocket.send_json(VoiceErrorMessage(error="Audio chunk too large").dict())
                                await websocket.close(code=1009)
                                break
                            await voice_session.send_audio(audio_bytes, "audio/pcm")
                        elif "text" in frame and frame["text"] is not None:
                            data = frame["text"]
                            request = VoiceClientRequest.model_validate_json(data)
                            if request.end_session:
                                logger.info(f"Client requested end of voice session {voice_session.session_id}")
                                await voice_session.end_session()
                                break
                            if request.mime_type == "audio/pcm":
                                audio_bytes = request.decode_data()
                                if isinstance(audio_bytes, bytes) and len(audio_bytes) > MAX_AUDIO_CHUNK_BYTES:
                                    await websocket.send_json(VoiceErrorMessage(error="Audio chunk too large").dict())
                                    await websocket.close(code=1009)
                                    break
                                await voice_session.send_audio(audio_bytes, request.mime_type)
                            elif request.mime_type == "text/plain":
                                text = request.decode_data()
                                await voice_session.send_text(text)
                        else:
                            # Ignore control frames other than close/ping handled by server
                            continue
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected from voice session {voice_session.session_id}")
                    await voice_session.end_session()
                except Exception as e:
                    logger.error(f"Error receiving from client in session {voice_session.session_id}: {e}")
                    await voice_session.end_session()
                    raise

            async def heartbeat():
                try:
                    while voice_session.active:
                        await asyncio.sleep(PING_INTERVAL_SEC)
                        await websocket.send_json({"type": "ping", "timestamp": utc_now_isoformat()})
                except Exception:
                    # Ignore ping send failures; sender/receiver will handle closure
                    pass

            tasks = [
                asyncio.create_task(producer()),
                asyncio.create_task(sender()),
                asyncio.create_task(receiver()),
                asyncio.create_task(heartbeat()),
            ]

            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"Voice session error for {session_id}: {e}", exc_info=True)
            try:
                await websocket.send_json(
                    VoiceErrorMessage(
                        error=str(e), 
                        timestamp=utc_now_isoformat()
                    ).dict()
                )
            except:
                pass  # Connection might be closed
        finally:
            # Cleanup
            if voice_session:
                try:
                    final_stats = await voice_session.cleanup()
                    
                    # Log voice session end
                    if user:
                        storage = get_storage_backend()
                        chat_logger = get_chat_logger(storage)
                        await chat_logger.log_voice_session_end(
                            user_id=user.id,
                            session_id=session_id,
                            voice_stats=final_stats
                        )
                        
                    logger.info(f"Voice session {session_id} cleanup completed")
                except Exception as cleanup_error:
                    logger.error(f"Error during voice session cleanup: {cleanup_error}")

    async def _prevalidate_token(self, token: str) -> Optional[User]:
        """Lightweight token validation before accepting WebSocket upgrade."""
        try:
            storage = get_storage_backend()
            auth_manager = get_auth_manager(storage)
            token_data = auth_manager.verify_token(token)
            user = await storage.get_user(token_data.user_id)
            return user
        except Exception:
            return None

    async def _handle_bidirectional_streaming(
        self,
        websocket: WebSocket,
        voice_session,
        chat_logger: ChatLogger,
        user_id: str,
        session_id: str,
        message_counter: int
    ):
        """Handle bidirectional audio streaming with transcript management."""
        
        # Create tasks for concurrent streaming
        receive_task = asyncio.create_task(
            self._receive_from_client(websocket, voice_session)
        )
        
        send_task = asyncio.create_task(
            self._send_to_client(websocket, voice_session, chat_logger, user_id, session_id, message_counter)
        )
        
        try:
            # Wait for either task to complete (usually due to disconnection)
            done, pending = await asyncio.wait(
                [receive_task, send_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in bidirectional streaming: {e}")
            raise

    async def _receive_from_client(self, websocket: WebSocket, voice_session):
        """Receive audio/text from client and forward to voice session."""
        try:
            while voice_session.active:
                # Receive data from WebSocket
                data = await websocket.receive_text()
                request = VoiceClientRequest.model_validate_json(data)

                if request.end_session:
                    logger.info(f"Client requested end of voice session {voice_session.session_id}")
                    await voice_session.end_session()
                    break

                # Handle based on MIME type
                if request.mime_type == "audio/pcm":
                    # Decode and send audio to voice session
                    audio_bytes = request.decode_data()
                    await voice_session.send_audio(audio_bytes, request.mime_type)
                    
                elif request.mime_type == "text/plain":
                    # Send text input
                    text = request.decode_data()
                    await voice_session.send_text(text)
                    
        except WebSocketDisconnect:
            logger.info(f"Client disconnected from voice session {voice_session.session_id}")
            await voice_session.end_session()
        except Exception as e:
            logger.error(f"Error receiving from client in session {voice_session.session_id}: {e}")
            await voice_session.end_session()
            raise

    async def _send_to_client(
        self, 
        websocket: WebSocket, 
        voice_session, 
        chat_logger: ChatLogger,
        user_id: str,
        session_id: str,
        message_counter: int
    ):
        """Send audio/transcripts to client and manage logging."""
        try:
            async for event in voice_session.process_events():
                if not voice_session.active:
                    break
                    
                event_type = event.get("type")
                
                if event_type == "audio_chunk":
                    # Send audio data to client
                    audio_msg = AudioChunkMessage(
                        data=base64.b64encode(event["data"]).decode('utf-8'),
                        mime_type=event["mime_type"],
                        timestamp=event["timestamp"]
                    )
                    await websocket.send_json(audio_msg.dict())
                    
                elif event_type == "transcript_partial":
                    # Send partial transcript for live display
                    partial_msg = TranscriptPartialMessage(
                        text=event["text"],
                        role=event["role"],
                        stability=event["stability"],
                        timestamp=event["timestamp"]
                    )
                    await websocket.send_json(partial_msg.dict())
                    
                elif event_type == "transcript_final":
                    # Send final transcript and log to ChatLogger
                    final_msg = TranscriptFinalMessage(
                        text=event["text"],
                        role=event["role"],
                        duration_ms=event["duration_ms"],
                        confidence=event["confidence"],
                        metadata=event["metadata"],
                        timestamp=event["timestamp"]
                    )
                    await websocket.send_json(final_msg.dict())
                    
                    # Log finalized transcript to ChatLogger
                    message_counter += 1
                    await chat_logger.log_voice_message(
                        user_id=user_id,
                        session_id=session_id,
                        role=event["role"],
                        transcript_text=event["text"],
                        duration_ms=event["duration_ms"],
                        confidence=event["confidence"],
                        message_number=message_counter,
                        voice_metadata=event["metadata"]
                    )
                    
                elif event_type == "turn_status":
                    # Send turn status updates
                    status_msg = TurnStatusMessage(
                        turn_complete=event["turn_complete"],
                        interrupted=event.get("interrupted", False),
                        timestamp=event["timestamp"]
                    )
                    await websocket.send_json(status_msg.dict())
                    
                elif event_type == "error":
                    # Send error message
                    error_msg = VoiceErrorMessage(
                        error=event["error"],
                        timestamp=event["timestamp"]
                    )
                    await websocket.send_json(error_msg.dict())
                    
        except WebSocketDisconnect:
            logger.info(f"Client disconnected while sending in session {voice_session.session_id}")
        except Exception as e:
            logger.error(f"Error sending to client in session {voice_session.session_id}: {e}")
            raise

    async def _validate_jwt_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return user."""
        try:
            storage = get_storage_backend()
            auth_manager = get_auth_manager(storage)
            token_data = auth_manager.verify_token(token)
            user = await storage.get_user(token_data.user_id)
            return user
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            return None

    async def _validate_session(
        self, 
        session_id: str, 
        user_id: str,
        adk_session_service: InMemorySessionService,
        chat_logger: ChatLogger
    ):
        """Validate that session exists and belongs to user."""
        # Check ADK session first
        adk_session = await adk_session_service.get_session(
            app_name="roleplay_chat", user_id=user_id, session_id=session_id
        )
        
        if adk_session:
            return adk_session
            
        # If not in ADK memory, check if it's an ended session
        try:
            end_info = await chat_logger.get_session_end_info(user_id, session_id)
            if end_info:
                logger.warning(f"Attempted to connect to ended session {session_id}")
                return None
        except:
            pass
            
        logger.warning(f"Session {session_id} not found for user {user_id}")
        return None

    async def get_session_info(self, session_id: str, token: str) -> VoiceSessionResponse:
        """Get voice session information."""
        user = await self._validate_jwt_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        voice_session = await self.voice_service.get_session(session_id)
        if not voice_session or voice_session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Voice session not found")
            
        session_info = VoiceSessionInfo(
            session_id=session_id,
            user_id=user.id,
            character_id=voice_session.adk_session.state.get("character_id") if voice_session.adk_session else None,
            scenario_id=voice_session.adk_session.state.get("scenario_id") if voice_session.adk_session else None,
            language=voice_session.adk_session.state.get("language", "en") if voice_session.adk_session else "en",
            started_at=voice_session.stats.get("started_at"),
            transcript_available=True
        )
        
        return VoiceSessionResponse(success=True, session_info=session_info)

    async def get_session_stats(self, session_id: str, token: str) -> VoiceSessionResponse:
        """Get voice session statistics."""
        user = await self._validate_jwt_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        voice_session = await self.voice_service.get_session(session_id)
        if not voice_session or voice_session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Voice session not found")
            
        stats = VoiceSessionStats(
            session_id=session_id,
            **voice_session.get_stats()
        )
        
        return VoiceSessionResponse(success=True, stats=stats)
