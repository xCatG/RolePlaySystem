"""Voice chat handler for real-time voice interactions with roleplay characters."""

from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect, Query, HTTPException, APIRouter, Depends
from fastapi.responses import JSONResponse
import logging
import asyncio
import json
import base64
import os
from datetime import datetime
import numpy as np
import subprocess
import io

# Correct imports for google-genai
from google import genai
from google.genai import types
from google.genai.types import AudioTranscriptionConfig

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
    TranscriptMessage,
    VoiceConfigMessage,
    VoiceErrorMessage,
    VoiceStatusMessage,
)

logger = logging.getLogger(__name__)


class VoiceChatHandler(BaseHandler):
    """Handler for voice chat WebSocket connections."""

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()
            
            # WebSocket endpoint for voice chat
            @self._router.websocket("/ws/{session_id}")
            async def voice_websocket_endpoint(
                websocket: WebSocket,
                session_id: str,
            ):
                # Accept the WebSocket connection first
                await websocket.accept()
                
                # Extract token from query parameters
                token = websocket.query_params.get("token")
                if not token:
                    await websocket.close(code=1008, reason="Missing token parameter")
                    return
                
                await self.handle_voice_session(websocket, session_id, token)
            
            # Simple test endpoint
            @self._router.get("/test")
            async def voice_test():
                return {"message": "Voice handler is working", "status": "ok"}
            
            # REST endpoint to get voice session info
            @self._router.get("/session/{session_id}/info")
            async def get_voice_session_info(
                session_id: str,
                token: str = Query(..., description="JWT authentication token"),
            ):
                return await self.get_session_info(session_id, token)
        
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
        """Handle a voice chat WebSocket connection."""
        user = None
        tasks = []
        
        try:
            logger.info(f"WebSocket connection attempt for session {session_id}")
            
            # 1. Validate JWT token
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
                VoiceStatusMessage(status="connected", message="Voice session connected").dict()
            )
            
            # 3. Load character and scenario context
            character_dict, scenario_dict = await self._load_session_content(
                adk_session, resource_loader
            )
            
            # 4. Create and run Gemini Live session
            use_mock = os.getenv("GEMINI_API_KEY") is None
            
            if use_mock:
                logger.warning("No GEMINI_API_KEY found, using mock session for development")
                await self._run_mock_session(
                    websocket, character_dict, scenario_dict, adk_session,
                    chat_logger, storage, user.id, session_id
                )
            else:
                await self._run_gemini_session(
                    websocket, character_dict, scenario_dict, adk_session,
                    chat_logger, storage, user.id, session_id
                )
            
        except WebSocketDisconnect:
            logger.info(f"Voice WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"Error in voice session {session_id}: {e}", exc_info=True)
            try:
                await websocket.send_json(
                    VoiceErrorMessage(
                        error=str(e),
                        code="VOICE_SESSION_ERROR"
                    ).dict()
                )
            except:
                pass
        finally:
            # Clean up
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            try:
                await websocket.close()
            except:
                pass
            
            logger.info(f"Voice session cleaned up for {session_id}")

    async def _run_gemini_session(
        self,
        websocket: WebSocket,
        character_dict: Dict,
        scenario_dict: Dict,
        adk_session: Any,
        chat_logger: ChatLogger,
        storage: StorageBackend,
        user_id: str,
        session_id: str
    ):
        """Run the actual Gemini Live session."""
        
        # Build system instruction with character context
        language = adk_session.state.get("language", "en")
        language_name = {
            "en": "English",
            "zh-TW": "Traditional Chinese",
            "ja": "Japanese"
        }.get(language, "English")
        
        system_instruction = f"""You are {character_dict['name']} in a voice conversation.
Character Description: {character_dict['description']}
Scenario: {scenario_dict['description']}
Participant: {adk_session.state.get('participant_name', 'User')}

IMPORTANT: You must respond in {language_name} language.
Stay in character at all times. Respond naturally as if in a real conversation.
{character_dict.get('system_prompt', '')}"""

        # Configure voice for the character
        voice_name = character_dict.get('voice_name', 'Aoede')  # Default voice
        
        # Create Gemini Live configuration
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
            output_audio_transcription=AudioTranscriptionConfig(),
            input_audio_transcription=AudioTranscriptionConfig(),
            system_instruction=system_instruction,
        )
        
        # Send configuration to client
        await websocket.send_json(
            VoiceConfigMessage(
                audio_format="pcm",  # Expecting PCM input from client
                language=language,
                voice_name=voice_name,
                output_audio_format="pcm", # Sending MP3 output to client
                #output_sample_rate=24000   # Gemini's default output sample rate
            ).dict()
        )
        
        # Send ready status
        await websocket.send_json(
            VoiceStatusMessage(status="ready", message="Voice session ready").dict()
        )
        
        try:
            # Initialize Gemini client
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            
            # Create session with async context manager
            async with client.aio.live.connect(
                model="gemini-2.0-flash-exp",
                config=config
            ) as session:
                # Create bidirectional streaming tasks
                receive_task = asyncio.create_task(
                    self._receive_audio_from_client(websocket, session, storage, user_id, session_id)
                )
                send_task = asyncio.create_task(
                    self._send_audio_to_client(websocket, session, chat_logger, user_id, session_id)
                )
                
                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    {receive_task, send_task},
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # If receive task completed (client ended session), wait briefly for send task
                if receive_task in done:
                    logger.info(f"Receive task completed for {session_id}, waiting for send task...")
                    try:
                        # Give send task 2 seconds to finish sending any remaining data
                        await asyncio.wait_for(send_task, timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.info(f"Send task timeout for {session_id}, cancelling...")
                        send_task.cancel()
                    except:
                        pass
                else:
                    # Send task completed first, cancel receive task
                    for task in pending:
                        task.cancel()
                    
        except Exception as e:
            logger.error(f"Gemini session error: {e}")
            raise

    async def _receive_audio_from_client(
        self,
        websocket: WebSocket,
        session: Any,  # Gemini Live session
        storage: StorageBackend,
        user_id: str,
        session_id: str
    ):
        """Receive audio from client and forward to Gemini Live."""
        try:
            while True:
                # Receive data from WebSocket
                data = await websocket.receive_text()
                request = VoiceClientRequest.model_validate_json(data)

                # Handle based on MIME type (ADK-style format)
                if request.mime_type == "audio/pcm":
                    # Decode base64 audio data
                    audio_bytes = request.decode_data()
                    
                    # Send audio to Gemini Live using send_realtime_input with proper Blob format
                    try:
                        # Create a Blob object with the audio data
                        audio_blob = types.Blob(
                            data=audio_bytes,
                            mime_type="audio/pcm;rate=16000"
                        )
                        await session.send_realtime_input(audio=audio_blob)
                    except Exception as audio_error:
                        logger.warning(f"Failed to send audio to Gemini: {audio_error}")
                        # For now, just log the error and continue
                    
                    # Optionally store for analysis
                    timestamp = utc_now_isoformat().replace(":", "_")
                    audio_path = f"users/{user_id}/voice_sessions/{session_id}/audio/user_{timestamp}.pcm"
                    await storage.write(audio_path, base64.b64encode(audio_bytes).decode())
                    
                elif request.mime_type == "text/plain":
                    # Decode and send text input
                    text = request.decode_data()
                    await session.send_realtime_input(text=text)
                    
                    # Also add to transcript
                    await websocket.send_json(
                        TranscriptMessage(
                            text=text,
                            role="user",
                            timestamp=utc_now_isoformat()
                        ).dict()
                    )
                
                if request.end_session:
                    logger.info(f"Client requested session end for {session_id}")
                    # Signal the Gemini session to stop by sending an empty message
                    # This will cause the send task to complete naturally
                    try:
                        await session.send_realtime_input(text="[Session ending]")
                    except:
                        pass
                    break
                    
        except WebSocketDisconnect:
            logger.info(f"Client disconnected from voice session {session_id}")
        except Exception as e:
            logger.error(f"Error receiving from client: {e}")
            raise

    async def _send_audio_to_client(
        self,
        websocket: WebSocket,
        session: Any,  # Gemini Live session
        chat_logger: ChatLogger,
        user_id: str,
        session_id: str
    ):
        """Receive from Gemini Live and forward to client."""
        try:
            message_count = 0
            storage = get_storage_backend()
            
            # Iterate over responses from Gemini
            async for response in session.receive():
                logger.info(f"GEMINI LIVE RESPONSE: {response}")
                # Handle different types of server messages
                if hasattr(response, 'server_content'):
                    server_content = response.server_content
                    
                    # 1. Handle user's transcribed speech
                    if hasattr(server_content, 'input_transcription') and server_content.input_transcription and server_content.input_transcription.text:
                        try:
                            await websocket.send_json(
                                TranscriptMessage(
                                    text=server_content.input_transcription.text,
                                    role="user",
                                    timestamp=utc_now_isoformat()
                                ).dict()
                            )
                        except (WebSocketDisconnect, ConnectionError):
                            logger.info(f"Client disconnected during user transcript send for session {session_id}")
                            return

                    # 2. Handle model's audio data
                    if hasattr(server_content, 'model_turn') and server_content.model_turn:
                        if hasattr(server_content.model_turn, 'parts') and server_content.model_turn.parts:
                            for part in server_content.model_turn.parts:
                                if hasattr(part, 'inline_data') and hasattr(part.inline_data, 'data'):
                                    audio_data = part.inline_data.data
                                    try:
                                        await websocket.send_bytes(audio_data)
                                    except (WebSocketDisconnect, ConnectionError):
                                        logger.info(f"Client disconnected during audio send for session {session_id}")
                                        return
                                    
                                    # Store audio
                                    timestamp = utc_now_isoformat().replace(":", "_")
                                    audio_path = f"users/{user_id}/voice_sessions/{session_id}/audio/char_{timestamp}.pcm"
                                    await storage.write(audio_path, base64.b64encode(audio_data).decode())

                    # 3. Handle model's transcribed speech
                    if hasattr(server_content, 'output_transcription') and server_content.output_transcription and server_content.output_transcription.text:
                        message_count += 1
                        text = server_content.output_transcription.text
                        
                        try:
                            await websocket.send_json(
                                TranscriptMessage(
                                    text=text,
                                    role="assistant",
                                    timestamp=utc_now_isoformat()
                                ).dict()
                            )
                        except (WebSocketDisconnect, ConnectionError):
                            logger.info(f"Client disconnected during assistant transcript send for session {session_id}")
                            return
                        
                        # Log to chat logger
                        await chat_logger.log_message(
                            user_id=user_id,
                            session_id=session_id,
                            role="character",
                            content=text,
                            message_number=message_count,
                            metadata={"source": "voice", "has_audio": True}
                        )

                # Also handle tool calls or other message types if needed
                if hasattr(response, 'tool_call'):
                    logger.debug(f"Received tool call: {response.tool_call}")
            
            # Send completion signal when done
            try:
                await websocket.send_json(
                    VoiceStatusMessage(
                        status="response_complete",
                        message="All responses have been sent"
                    ).dict()
                )
            except:
                pass  # Client may have already disconnected
        
        except asyncio.CancelledError:
            # Task was cancelled (normal during shutdown)
            logger.info(f"Send task cancelled for session {session_id}")
            raise
        except WebSocketDisconnect:
            # Client disconnected
            logger.info(f"WebSocket disconnected while sending for session {session_id}")
        except Exception as e:
            # Log other errors but don't raise if it's just a connection issue
            if "Connection" in str(e) or "WebSocket" in str(e):
                logger.info(f"Connection closed while sending: {e}")
            else:
                logger.error(f"Error sending to client: {e}")
                raise

    async def _run_mock_session(
        self,
        websocket: WebSocket,
        character_dict: Dict,
        scenario_dict: Dict,
        adk_session: Any,
        chat_logger: ChatLogger,
        storage: StorageBackend,
        user_id: str,
        session_id: str
    ):
        """Run a mock session for development without Gemini API."""
        
        # Send configuration
        await websocket.send_json(
            VoiceConfigMessage(
                audio_format="mock",
                language=adk_session.state.get("language", "en"),
                voice_name="mock"
            ).dict()
        )
        
        # Send ready status
        await websocket.send_json(
            VoiceStatusMessage(status="ready", message="Mock voice session ready (dev mode)").dict()
        )
        
        try:
            message_count = 0
            while True:
                # Receive from client
                data = await websocket.receive_text()
                request = VoiceClientRequest.model_validate_json(data)
                
                if request.end_session:
                    break
                
                # Handle based on MIME type
                if request.mime_type == "audio/pcm":
                    # Mock response - echo back transcript for audio
                    message_count += 1
                    mock_text = f"[Mock {character_dict['name']}]: I heard audio chunk {message_count}"
                    
                    # Send transcript
                    await websocket.send_json(
                        TranscriptMessage(
                            text=mock_text,
                            role="assistant",
                            timestamp=utc_now_isoformat()
                        ).dict()
                    )
                    
                    # Simulate audio response by sending mock PCM data
                    mock_audio = b'\x00' * 1600  # 100ms of silence at 16kHz
                    await websocket.send_bytes(mock_audio)
                    
                    # Log message
                    await chat_logger.log_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="character",
                        content=mock_text,
                        message_number=message_count,
                        metadata={"source": "voice_mock"}
                    )
                    
                elif request.mime_type == "text/plain":
                    # Handle text input
                    text = request.decode_data()
                    message_count += 1
                    mock_response = f"[Mock {character_dict['name']}]: You said '{text}'"
                    
                    # Send user transcript first
                    await websocket.send_json(
                        TranscriptMessage(
                            text=text,
                            role="user",
                            timestamp=utc_now_isoformat()
                        ).dict()
                    )
                    
                    # Then send assistant response
                    await websocket.send_json(
                        TranscriptMessage(
                            text=mock_response,
                            role="assistant",
                            timestamp=utc_now_isoformat()
                        ).dict()
                    )
                    
                    # Log messages
                    await chat_logger.log_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="user",
                        content=text,
                        message_number=message_count,
                        metadata={"source": "voice_mock"}
                    )
                        
        except WebSocketDisconnect:
            logger.info(f"Mock session disconnected")
        except Exception as e:
            logger.error(f"Mock session error: {e}")
            raise

    async def _validate_jwt_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return user."""
        try:
            logger.info(f"Validating JWT token: {token[:20]}...")
            
            # Get auth manager and validate token
            auth_manager = get_auth_manager(get_storage_backend())
            token_data = auth_manager.verify_token(token)
            logger.info(f"Token decoded successfully, user_id: {token_data.user_id}")
            
            # Get user from storage
            user = await auth_manager.storage.get_user(token_data.user_id)
            if not user or not user.is_active:
                logger.warning(f"User {token_data.user_id} not found or inactive")
                return None
            
            logger.info(f"User validated: {user.username}")
            return user
        except Exception as e:
            logger.error(f"JWT validation error: {e}", exc_info=True)
            return None

    async def _validate_session(
        self,
        session_id: str,
        user_id: str,
        adk_session_service: InMemorySessionService,
        chat_logger: ChatLogger
    ) -> Optional[Any]:
        """Validate that session exists and is active."""
        try:
            adk_session = await adk_session_service.get_session(
                app_name="roleplay_chat", user_id=user_id, session_id=session_id
            )
            if not adk_session:
                # Check if session was ended
                end_info = await chat_logger.get_session_end_info(user_id, session_id)
                if end_info:
                    logger.warning(f"Attempted to start voice for ended session {session_id}")
                return None
            return adk_session
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return None

    async def _load_session_content(
        self, adk_session: Any, resource_loader: ResourceLoader
    ) -> tuple[Dict, Dict]:
        """Load character and scenario content for the session."""
        character_dict = await resource_loader.get_character_by_id(
            adk_session.state.get("character_id"),
            adk_session.state.get("language", "en")
        )
        scenario_dict = await resource_loader.get_scenario_by_id(
            adk_session.state.get("scenario_id"),
            adk_session.state.get("language", "en")
        )
        return character_dict, scenario_dict

    async def get_session_info(self, session_id: str, token: str) -> VoiceSessionInfo:
        """Get information about a voice session."""
        user = await self._validate_jwt_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        # Get session from ADK
        adk_session_service = get_adk_session_service()
        adk_session = await adk_session_service.get_session(
            app_name="roleplay_chat", user_id=user.id, session_id=session_id
        )
        
        if not adk_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check if voice transcripts exist
        storage = get_storage_backend()
        voice_path = f"users/{user.id}/voice_sessions/{session_id}/"
        voice_files = await storage.list_keys(voice_path)
        
        return VoiceSessionInfo(
            session_id=session_id,
            user_id=user.id,
            character_id=adk_session.state.get("character_id"),
            scenario_id=adk_session.state.get("scenario_id"),
            language=adk_session.state.get("language", "en"),
            started_at=adk_session.state.get("session_creation_time_iso"),
            transcript_available=len(voice_files) > 0
        )

    