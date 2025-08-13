import asyncio
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from typing import Annotated, AsyncGenerator

from .adk_voice_service import ADKVoiceService
from google.adk.agents import LiveRequestQueue
from google.adk.sessions import InMemorySessionService, Session
from google.genai.types import Content, Part

from ..server.base_handler import BaseHandler
from ..common.models import User
from ..common.auth import AuthManager
from ..server.dependencies import get_adk_session_service, get_auth_manager
from ..common.exceptions import AuthenticationError, TokenExpiredError

import logging
logger = logging.getLogger(__name__)


class VoiceChatHandler(BaseHandler):
    """Handler for real-time voice chat sessions."""

    def __init__(self):
        super().__init__()
        self.voice_service = ADKVoiceService()

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()
            self._router.websocket("/ws/{session_id}")(self.handle_voice_session)
        return self._router

    @property
    def prefix(self) -> str:
        return "/voice"

    async def _validate_jwt_token(self, token: str, auth_manager: AuthManager) -> User:
        """Validates the JWT token and returns the user."""
        try:
            user = await auth_manager.get_user_by_token(token)
            return user
        except (AuthenticationError, TokenExpiredError) as e:
            # For WebSockets, we can't return a standard HTTP response,
            # so we'll raise an exception to be caught by the main handler.
            raise ConnectionAbortedError(f"Authentication failed: {e}")

    async def handle_voice_session(
        self,
        websocket: WebSocket,
        session_id: str,
        token: Annotated[str, Query()],
        auth_manager: Annotated[AuthManager, Depends(get_auth_manager)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)]
    ):
        """Main handler for the voice WebSocket connection."""
        user = None
        live_request_queue = None
        try:
            await websocket.accept()

            # 1. Authenticate user
            user = await self._validate_jwt_token(token, auth_manager)

            # 2. Get the initial chat session state
            chat_session = await adk_session_service.get_session(
                app_name="roleplay_chat", user_id=user.id, session_id=session_id
            )
            if not chat_session:
                raise ValueError("Chat session not found. A voice session must be started from an existing chat session.")

            # 3. Create the ADK live session for voice
            live_events, live_request_queue = await self.voice_service.create_voice_session(
                session_id=session_id,
                user_id=user.id,
                character_id=chat_session.state["character_id"],
                scenario_id=chat_session.state["scenario_id"],
                script_data=chat_session.state.get("script_data"),
                language=chat_session.state.get("language", "en")
            )

            # 4. Start concurrent tasks for bidirectional streaming
            client_to_agent_task = asyncio.create_task(
                self._handle_client_to_agent(websocket, live_request_queue)
            )
            agent_to_client_task = asyncio.create_task(
                self._handle_agent_to_client(websocket, live_events)
            )

            done, pending = await asyncio.wait(
                [client_to_agent_task, agent_to_client_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

        except (WebSocketDisconnect, ConnectionAbortedError, ValueError) as e:
            reason = str(e) if str(e) else "Client disconnected"
            logger.warning(f"Closing WebSocket for session {session_id}. Reason: {reason}")
            # The 'finally' block will handle cleanup. If websocket is already closed, this will do nothing.
            await websocket.close(code=4000, reason=reason)
        except Exception as e:
            logger.error(f"Unexpected error in voice session {session_id}: {e}", exc_info=True)
            await websocket.close(code=5000, reason="Internal server error")
        finally:
            if live_request_queue:
                live_request_queue.close()
            if user:
                # Clean up the dedicated voice session from the ADK service
                await adk_session_service.delete_session(
                    app_name="roleplay_voice", user_id=user.id, session_id=session_id
                )
            logger.info(f"Cleaned up voice session resources for: {session_id}")

    async def _handle_client_to_agent(self, websocket: WebSocket, queue: LiveRequestQueue):
        """Listens for messages from the client and forwards them to the agent."""
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "audio":
                    audio_bytes = base64.b64decode(data["data"])
                    await queue.send_realtime(audio_bytes)
                elif data.get("type") == "text":
                    await queue.send_content(Content(parts=[Part(text=data["text"])]))
        except WebSocketDisconnect:
            logger.info("Client disconnected from C2A task.")
            # Let the main handler manage cleanup by re-raising.
            raise
        except Exception as e:
            logger.error(f"Error in client-to-agent task: {e}", exc_info=True)
            # Propagate the error to the main handler
            raise ConnectionAbortedError(f"Client-side error: {e}")

    async def _handle_agent_to_client(self, websocket: WebSocket, events: AsyncGenerator):
        """Listens for events from the agent and forwards them to the client."""
        try:
            async for event in events:
                # Turn status
                if event.turn_complete or event.interrupted:
                    await websocket.send_json({
                        "type": "turn_status",
                        "turn_complete": event.turn_complete,
                        "interrupted": event.interrupted
                    })

                # Transcriptions
                if hasattr(event, 'input_transcription') and event.input_transcription:
                    await websocket.send_json({"type": "transcript", "role": "user", "text": event.input_transcription.text})
                if hasattr(event, 'output_transcription') and event.output_transcription:
                    await websocket.send_json({"type": "transcript", "role": "assistant", "text": event.output_transcription.text})

                # Audio/Text content
                if not event.content or not event.content.parts:
                    continue

                part = event.content.parts[0]

                if part.inline_data and part.inline_data.mime_type.startswith("audio"):
                    audio_data = base64.b64encode(part.inline_data.data).decode("utf-8")
                    await websocket.send_json({"type": "audio", "data": audio_data})
                elif part.text:
                    await websocket.send_json({"type": "text", "data": part.text, "partial": event.partial})
        except WebSocketDisconnect:
            logger.info("Client disconnected from A2C task.")
            # Let the main handler manage cleanup by re-raising.
            raise
        except Exception as e:
            logger.error(f"Error in agent-to-client task: {e}", exc_info=True)
            # Propagate the error to the main handler
            raise ConnectionAbortedError(f"Agent-side error: {e}")
