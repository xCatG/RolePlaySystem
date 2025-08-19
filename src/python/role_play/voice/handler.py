"""WebSocket handler for real-time voice conversations."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, AsyncGenerator, Dict

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from google.adk.agents import LiveRequestQueue
from google.genai.types import Blob, Content, Part

from .adk_voice_service import ADKVoiceService
from ..chat.chat_logger import ChatLogger
from ..server.dependencies import (
    get_adk_session_service,
    get_auth_manager,
    get_chat_logger,
    get_storage_backend,
)
from ..common.exceptions import AuthenticationError, TokenExpiredError

logger = logging.getLogger(__name__)


class VoiceChatHandler:
    """Handler managing a bidirectional voice chat session over WebSocket."""

    def __init__(self, chat_logger: ChatLogger | None = None) -> None:
        self.voice_service = ADKVoiceService()
        # Allow dependency injection for easier testing
        self.chat_logger = chat_logger or get_chat_logger(get_storage_backend())
        # Track message counts per session for logging
        self._message_counters: Dict[str, int] = {}

    async def handle_voice_session(
        self, websocket: WebSocket, session_id: str, token: str
    ) -> None:
        """Main entry point for handling a voice WebSocket session."""
        user = await self._validate_jwt_token(token)
        adk_session = await self._get_adk_session(session_id, user.id)

        live_events, live_request_queue = await self.voice_service.create_voice_session(
            session_id=session_id,
            user_id=user.id,
            character_id=adk_session.state["character_id"],
            scenario_id=adk_session.state["scenario_id"],
            script_data=adk_session.state.get("script_data"),
            language=adk_session.state.get("language", "en"),
        )

        # Initialize message counter for this session
        self._message_counters[session_id] = adk_session.state.get("message_count", 0)

        client_to_agent_task = asyncio.create_task(
            self._handle_client_to_agent(websocket, live_request_queue)
        )
        agent_to_client_task = asyncio.create_task(
            self._handle_agent_to_client(
                websocket, live_events, session_id, user.id
            )
        )

        try:
            done, pending = await asyncio.wait(
                [client_to_agent_task, agent_to_client_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
        finally:
            live_request_queue.close()
            self._message_counters.pop(session_id, None)

    async def _handle_client_to_agent(
        self, websocket: WebSocket, queue: LiveRequestQueue
    ) -> None:
        """Stream audio/text from the client to the agent."""
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "audio":
                    audio_bytes = base64.b64decode(data["data"])
                    await queue.send_realtime(Blob(mime_type="audio/pcm", data=audio_bytes))
                elif data.get("type") == "text":
                    await queue.send_content(Content(parts=[Part(text=data["text"])]))
        except WebSocketDisconnect:
            pass

    async def _handle_agent_to_client(
        self,
        websocket: WebSocket,
        live_events: AsyncGenerator,
        session_id: str,
        user_id: str,
    ) -> None:
        """
        Stream responses from the agent to the client while buffering transcript
        text for logging when a turn completes.
        """
        transcript_buffer: list[str] = []

        try:
            async for event in live_events:
                if getattr(event, "input_transcription", None):
                    await websocket.send_json(
                        {
                            "type": "transcript",
                            "role": "user",
                            "text": event.input_transcription.text,
                        }
                    )
                if getattr(event, "output_transcription", None):
                    await websocket.send_json(
                        {
                            "type": "transcript",
                            "role": "assistant",
                            "text": event.output_transcription.text,
                        }
                    )

                part = getattr(event, "content", None)
                part = part and part.parts and part.parts[0]

                if part:
                    if getattr(part, "inline_data", None) and part.inline_data.mime_type.startswith(
                        "audio"
                    ):
                        audio_data = base64.b64encode(part.inline_data.data).decode("utf-8")
                        await websocket.send_json({"type": "audio", "data": audio_data})
                    elif getattr(part, "text", None) and getattr(event, "partial", False):
                        transcript_buffer.append(part.text)
                        await websocket.send_json(
                            {"type": "text", "data": part.text, "partial": True}
                        )

                if getattr(event, "turn_complete", False) or getattr(
                    event, "interrupted", False
                ):
                    if transcript_buffer:
                        full_transcript = "".join(transcript_buffer)
                        message_num = self._message_counters.get(session_id, 0) + 1
                        self._message_counters[session_id] = message_num
                        try:
                            await self.chat_logger.log_message(
                                user_id=user_id,
                                session_id=session_id,
                                role="assistant",
                                content=full_transcript,
                                message_number=message_num,
                            )
                        except Exception as log_err:  # pragma: no cover - logging failure shouldn't crash session
                            logger.error(
                                "Failed to log transcript for session %s: %s",
                                session_id,
                                log_err,
                            )
                        transcript_buffer.clear()

                    await websocket.send_json(
                        {
                            "type": "turn_status",
                            "turn_complete": getattr(event, "turn_complete", False),
                            "interrupted": getattr(event, "interrupted", False),
                        }
                    )
        except Exception as e:  # pragma: no cover - best effort logging
            logger.error("Error in agent->client stream for session %s: %s", session_id, e)

    async def _validate_jwt_token(self, token: str) -> Any:
        """Validate JWT token and return the associated user."""
        auth_manager = get_auth_manager(get_storage_backend())
        try:
            token_data = auth_manager.verify_token(token)
            user = await auth_manager.storage.get_user(token_data.user_id)
            if user is None:
                raise HTTPException(status_code=401, detail="User not found")
            return user
        except TokenExpiredError as exc:
            raise HTTPException(status_code=401, detail="Token expired") from exc
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc

    async def _get_adk_session(self, session_id: str, user_id: str) -> Any:
        """Retrieve an existing ADK session for the user."""
        session_service = get_adk_session_service()
        session = await session_service.get_session(
            app_name="roleplay_voice", user_id=user_id, session_id=session_id
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
