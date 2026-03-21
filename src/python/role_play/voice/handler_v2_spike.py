"""Voice Handler V2 Spike.

Prototype handler for 45-minute behavioral interviews.
Addresses all gaps from docs/voice_handler_gap_report.md.

This is a spike — not registered via standard handler registration.
Test directly via unit tests and manual WebSocket testing.
"""
import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, AsyncGenerator, List

from starlette.websockets import WebSocketDisconnect

from .voice_config_v2 import VoiceConfigV2

logger = logging.getLogger(__name__)


# region Dataclasses

@dataclass
class EventClassification:
    """Result of classifying an ADK live event.

    Pure data — no side effects. Built by classify_adk_event (sync).
    Routed by _send_to_client (async).
    """
    kind: str               # "audio", "transcript", "turn_status",
                            # "session_resumption", "go_away", "unknown"
    data: Any               # parsed payload
    role: Optional[str] = None         # "user" or "assistant"
    is_partial: bool = False
    is_terminal: bool = False
    terminal_reason: Optional[str] = None  # AI_CONCLUDED or AI_EARLY_TERMINATION


@dataclass
class VoiceSessionState:
    """Typed session state replacing v1's Dict[str, Any].

    Holds all per-session data needed by the four streaming coroutines.
    """
    session_id: str
    user_id: str
    runner: Any  # google.adk.Runner — typed as Any to avoid import in tests
    live_events: AsyncGenerator
    live_request_queue: Any  # google.adk.agents.LiveRequestQueue
    adk_session: Any
    stop_event: asyncio.Event
    termination_reason: Optional[str]
    started_at: datetime
    session_timeout: int
    warning_seconds: int
    chat_logger: Any  # ChatLogger
    transcript_buffer: List[Dict] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=lambda: {
        "audio_chunks_sent": 0,
        "audio_chunks_received": 0,
        "text_chunks_sent": 0,
        "transcripts_processed": 0,
        "errors": 0,
    })

# endregion


# region ADK Type Stubs (avoid importing google.genai in tests)

class _Blob:
    """Minimal Blob stub matching google.genai.types.Blob interface."""
    def __init__(self, mime_type: str, data: bytes):
        self.mime_type = mime_type
        self.data = data


class _Content:
    """Minimal Content stub matching google.genai.types.Content interface."""
    def __init__(self, parts: list):
        self.parts = parts


class _Part:
    """Minimal Part stub matching google.genai.types.Part interface."""
    def __init__(self, text: str):
        self.text = text

# endregion


# region Event Classification

def classify_adk_event(event: Any) -> EventClassification:
    """Classify an ADK live event into a routing category.

    Pure sync function — no side effects, no I/O.
    Unknown events are classified as "unknown" with full attribute logging.

    See spec Section 3.3 for detection heuristics.
    """
    # Check for session resumption (best-effort detection)
    if hasattr(event, "session_resumption_update"):
        handle = event.session_resumption_update
        if not isinstance(handle, str):
            try:
                handle = json.dumps(handle) if not isinstance(handle, bytes) else handle.decode()
            except (TypeError, UnicodeDecodeError):
                handle = str(handle)
        logger.info(f"Session resumption event detected, handle type: {type(event.session_resumption_update).__name__}")
        return EventClassification(kind="session_resumption", data=handle)

    # Check for GoAway (best-effort detection)
    if hasattr(event, "go_away"):
        logger.warning(f"GoAway event received: {event.go_away}")
        return EventClassification(kind="go_away", data=event.go_away)

    # Check for content (audio or transcript)
    content = getattr(event, "content", None)
    if content is not None and hasattr(content, "parts") and content.parts:
        for part in content.parts:
            # Text content -> transcript
            if hasattr(part, "text") and part.text:
                is_partial = getattr(event, "partial", False)
                role = "assistant" if getattr(content, "role", None) == "model" else "user"
                text = part.text
                is_terminal = False
                terminal_reason = None

                # Sentinel detection
                if VoiceConfigV2.SENTINEL_SESSION_COMPLETE in text:
                    is_terminal = True
                    terminal_reason = VoiceConfigV2.REASON_AI_CONCLUDED
                    text = text.replace(VoiceConfigV2.SENTINEL_SESSION_COMPLETE, "").strip()
                elif VoiceConfigV2.SENTINEL_END_EARLY in text:
                    is_terminal = True
                    terminal_reason = VoiceConfigV2.REASON_AI_EARLY_TERMINATION
                    idx = text.find(VoiceConfigV2.SENTINEL_END_EARLY)
                    end_idx = text.find("]", idx)
                    if end_idx != -1:
                        text = (text[:idx] + text[end_idx + 1:]).strip()

                return EventClassification(
                    kind="transcript", data=text, role=role,
                    is_partial=is_partial, is_terminal=is_terminal,
                    terminal_reason=terminal_reason,
                )

            # Audio content -> audio
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None:
                audio_data = getattr(inline_data, "data", None)
                mime_type = getattr(inline_data, "mime_type", "audio/pcm")
                if audio_data and len(audio_data) > 0:
                    return EventClassification(
                        kind="audio",
                        data={"audio_data": audio_data, "mime_type": mime_type},
                    )

    # Turn status (check after content — content events may also have these flags)
    if hasattr(event, "turn_complete") or hasattr(event, "interrupted"):
        return EventClassification(
            kind="turn_status",
            data={
                "turn_complete": getattr(event, "turn_complete", None),
                "interrupted": getattr(event, "interrupted", None),
                "partial": getattr(event, "partial", None),
            },
        )

    # Unknown — log everything for spike discovery
    event_type = type(event).__name__
    event_attrs = {attr: str(getattr(event, attr, None))
                   for attr in dir(event) if not attr.startswith("_")}
    logger.debug(f"Unknown ADK event: type={event_type}, attrs={event_attrs}")
    return EventClassification(kind="unknown", data={"type": event_type, "attrs": event_attrs})

# endregion


# region Handler

class VoiceHandlerV2:
    """Voice handler v2 spike for 45-minute behavioral interviews.

    Not registered via standard handler registration.
    Uses /voice-v2 prefix to avoid conflicts with v1.
    Storage injected at construction.
    """

    def __init__(self, storage):
        self._storage = storage
        self._router = None

    @property
    def prefix(self) -> str:
        return "/voice-v2"

    # region Termination

    async def _handle_termination(
        self,
        websocket,
        state: VoiceSessionState,
        reason: str,
        detail: Optional[str] = None,
    ) -> None:
        """Single convergence point for all session exit paths."""
        # Guard: prevent double-fire
        if state.stop_event.is_set():
            return
        state.stop_event.set()
        state.termination_reason = reason

        # Notify frontend
        try:
            await websocket.send_json({
                "type": "session_ended",
                "reason": reason,
                "detail": detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass  # Socket may already be closed

        # Close queue unless resumable
        if reason != VoiceConfigV2.REASON_DISCONNECTED:
            state.live_request_queue.close()

        logger.info(
            f"Session {state.session_id} terminated: reason={reason}, detail={detail}"
        )

    # endregion

    # region Timer

    async def _session_timer(
        self, websocket, state: VoiceSessionState,
    ) -> None:
        """Wall clock timer with warning injection.

        Two phases: sleep until warning, fire warning, sleep until termination.
        Uses wait_for(stop_event.wait()) so it responds immediately to session end.
        """
        elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
        warning_at = state.session_timeout - state.warning_seconds

        # Phase 1: wait until warning
        try:
            await asyncio.wait_for(
                state.stop_event.wait(),
                timeout=max(0, warning_at - elapsed),
            )
            return  # stop_event set before warning
        except asyncio.TimeoutError:
            pass

        await self._inject_time_warning(state)

        # Phase 2: wait until termination
        try:
            await asyncio.wait_for(
                state.stop_event.wait(),
                timeout=state.warning_seconds,
            )
            return  # stop_event set during warning period
        except asyncio.TimeoutError:
            pass

        await self._handle_termination(websocket, state, VoiceConfigV2.REASON_TIME_LIMIT)

    async def _inject_time_warning(self, state: VoiceSessionState) -> None:
        """Inject time warning into the live session.

        Tries both approaches (state update + content injection).
        Failures are logged, not propagated.
        """
        # Approach 1: State update (likely won't propagate mid-stream)
        try:
            state.adk_session.state["time_warning"] = True
            logger.info(f"Session {state.session_id}: set time_warning=True in session state")
        except Exception as e:
            logger.warning(f"Session {state.session_id}: state update failed: {e}")

        # Approach 2: Content injection (primary approach)
        try:
            warning_content = _Content(
                parts=[_Part(text="[SYSTEM] 5 minutes remaining. Begin wrapping up the interview.")]
            )
            state.live_request_queue.send_content(warning_content)
            logger.info(f"Session {state.session_id}: injected time warning content")
        except Exception as e:
            logger.warning(f"Session {state.session_id}: content injection failed: {e}")

    # endregion

    # region Keepalive

    async def _heartbeat(self, websocket, state: VoiceSessionState) -> None:
        """Send periodic heartbeat JSON to keep the WebSocket alive.

        Exits when stop_event is set. Calls _handle_termination(DISCONNECTED)
        if the WebSocket send fails.
        """
        while not state.stop_event.is_set():
            try:
                await asyncio.wait_for(
                    state.stop_event.wait(),
                    timeout=VoiceConfigV2.HEARTBEAT_INTERVAL_SECONDS,
                )
                break  # stop_event was set
            except asyncio.TimeoutError:
                pass  # interval elapsed

            if state.stop_event.is_set():
                break

            try:
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except ConnectionError:
                await self._handle_termination(
                    websocket, state, VoiceConfigV2.REASON_DISCONNECTED,
                )
                raise

    # endregion

    # region Event Routing

    async def _send_to_client(
        self, websocket, state: VoiceSessionState,
    ) -> None:
        """Route ADK events to frontend, storage, or logs.

        Uses classify_adk_event (sync) for classification, then routes async.
        Transcripts are logged but NOT sent to frontend (REQ-7).
        """
        try:
            async for event in state.live_events:
                if state.stop_event.is_set():
                    break

                classification = classify_adk_event(event)

                if classification.kind == "audio":
                    audio_data = classification.data["audio_data"]
                    state.stats.setdefault("audio_chunks_received", 0)
                    state.stats["audio_chunks_received"] += 1
                    await websocket.send_json({
                        "type": "audio",
                        "data": base64.b64encode(audio_data).decode("utf-8"),
                        "mime_type": classification.data["mime_type"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif classification.kind == "transcript":
                    # REQ-7: log but do NOT send to frontend
                    state.stats.setdefault("transcripts_processed", 0)
                    state.stats["transcripts_processed"] += 1
                    entry = {
                        "text": classification.data,
                        "role": classification.role,
                        "is_partial": classification.is_partial,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    state.transcript_buffer.append(entry)

                    if not classification.is_partial:
                        await state.chat_logger.log_voice_message(
                            user_id=state.user_id,
                            session_id=state.session_id,
                            role=classification.role,
                            transcript_text=classification.data,
                            duration_ms=0,
                            message_number=-1,
                            confidence=1.0,
                            voice_metadata=entry,
                        )

                    # Check for AI termination sentinel
                    if classification.is_terminal:
                        logger.info(
                            f"Session {state.session_id}: AI terminal signal "
                            f"reason={classification.terminal_reason}"
                        )
                        await self._handle_termination(
                            websocket, state, classification.terminal_reason,
                        )
                        return

                elif classification.kind == "turn_status":
                    await websocket.send_json({
                        "type": "turn_status",
                        **classification.data,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif classification.kind == "session_resumption":
                    handle_key = VoiceConfigV2.HANDLE_KEY_TEMPLATE.format(
                        user_id=state.user_id, session_id=state.session_id,
                    )
                    await self._storage.write(handle_key, classification.data)
                    logger.info(f"Session {state.session_id}: persisted resumption handle")

                elif classification.kind == "go_away":
                    logger.warning(f"Session {state.session_id}: GoAway received (suppressed)")

                else:  # unknown
                    logger.debug(f"Session {state.session_id}: unknown event: {classification.data}")

        except asyncio.CancelledError:
            logger.info(f"Event processing cancelled for session {state.session_id}")
        except ConnectionError as e:
            logger.error(f"Connection error in _send_to_client: {e}")
            await self._handle_termination(
                websocket, state, VoiceConfigV2.REASON_DISCONNECTED,
            )
        except Exception as e:
            logger.error(f"Unexpected error in _send_to_client: {e}", exc_info=True)
            state.stats.setdefault("errors", 0)
            state.stats["errors"] += 1

    # endregion

    # region Client Input

    async def _receive_from_client(
        self,
        websocket,
        state: VoiceSessionState,
        env_info,
    ) -> None:
        """Receive from client and forward to ADK."""
        try:
            while not state.stop_event.is_set():
                data = await websocket.receive_text()

                try:
                    request = json.loads(data)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Invalid JSON from client: {e}")
                    state.stats.setdefault("errors", 0)
                    state.stats["errors"] += 1
                    continue

                mime_type = request.get("mime_type", "")
                raw_data = request.get("data", "")
                end_session = request.get("end_session", False)

                if end_session:
                    await self._handle_termination(
                        websocket, state, VoiceConfigV2.REASON_USER_ENDED,
                    )
                    return

                try:
                    decoded = base64.b64decode(raw_data)
                except Exception:
                    state.stats.setdefault("errors", 0)
                    state.stats["errors"] += 1
                    continue

                try:
                    if mime_type == "audio/pcm":
                        # PCM logging in non-production
                        if not getattr(env_info, "is_production", True):
                            try:
                                await state.chat_logger.log_pcm_audio(
                                    user_id=state.user_id,
                                    session_id=state.session_id,
                                    audio_data=decoded,
                                )
                            except (AttributeError, Exception) as e:
                                logger.debug(f"PCM logging skipped: {e}")

                        blob = _Blob(mime_type=mime_type, data=decoded)
                        state.live_request_queue.send_realtime(blob)
                        state.stats.setdefault("audio_chunks_sent", 0)
                        state.stats["audio_chunks_sent"] += 1

                    elif mime_type == "text/plain":
                        text_data = decoded.decode("utf-8")
                        await state.chat_logger.log_message(
                            user_id=state.user_id,
                            session_id=state.session_id,
                            role="user",
                            content=text_data,
                            message_number=-1,
                        )
                        content = _Content(parts=[_Part(text=text_data)])
                        state.live_request_queue.send_content(content)
                        state.stats.setdefault("text_chunks_sent", 0)
                        state.stats["text_chunks_sent"] += 1

                except Exception as e:
                    logger.error(f"Error processing client input: {e}")
                    state.stats.setdefault("errors", 0)
                    state.stats["errors"] += 1

        except WebSocketDisconnect:
            logger.info(f"Client disconnected from session {state.session_id}")
            await self._handle_termination(
                websocket, state, VoiceConfigV2.REASON_DISCONNECTED,
            )
        except Exception as e:
            logger.error(f"Error in _receive_from_client: {e}")
            await self._handle_termination(
                websocket, state, VoiceConfigV2.REASON_DISCONNECTED,
            )

    # endregion

    # region Streaming Orchestrator

    async def _handle_streaming(
        self,
        websocket,
        state: VoiceSessionState,
        env_info,
    ) -> None:
        """Orchestrate four concurrent coroutines with stop_event coordination."""
        tasks = [
            asyncio.create_task(
                self._receive_from_client(websocket, state, env_info),
                name="receive",
            ),
            asyncio.create_task(
                self._send_to_client(websocket, state),
                name="send",
            ),
            asyncio.create_task(
                self._session_timer(websocket, state),
                name="timer",
            ),
            asyncio.create_task(
                self._heartbeat(websocket, state),
                name="heartbeat",
            ),
        ]

        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED,
            )

            # Check if stop_event was set by the completed task
            if not state.stop_event.is_set():
                for task in done:
                    exc = task.exception()
                    if exc:
                        logger.warning(
                            f"Task {task.get_name()} failed unexpectedly: {exc}"
                        )
                state.stop_event.set()

        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Wait for cancellation to complete
            await asyncio.gather(*tasks, return_exceptions=True)

    # endregion

    # region Auth

    @staticmethod
    async def _validate_jwt_token(token: str, storage) -> Optional[Any]:
        """Validate JWT token and return user. Placeholder for spike."""
        # In production, this would use auth_manager.verify_token
        # For the spike, this is just a stub
        try:
            from ..common.exceptions import TokenExpiredError, AuthenticationError
            from ..server.dependencies import get_auth_manager
            auth_manager = get_auth_manager(storage)
            token_data = auth_manager.verify_token(token)
            user = await storage.get_user(token_data.user_id)
            return user
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            return None

    def _check_session_limit(self, user_id: str) -> bool:
        """Placeholder — always returns True."""
        return True

    # endregion

    # region Entry Point

    async def handle_voice_session(
        self,
        websocket,
        session_id: str,
        env_info,
    ) -> None:
        """Entry point for a voice WebSocket connection.

        Auth -> session lookup -> ADK init -> streaming -> cleanup.
        """
        state = None
        try:
            # Extract query params
            token = websocket.query_params.get("token")
            if not token:
                await websocket.close(
                    code=VoiceConfigV2.WS_MISSING_TOKEN, reason="Missing token",
                )
                return

            timeout = int(websocket.query_params.get(
                "timeout", VoiceConfigV2.DEFAULT_SESSION_TIMEOUT_SECONDS,
            ))
            warning = int(websocket.query_params.get(
                "warning", VoiceConfigV2.DEFAULT_SESSION_WARNING_SECONDS,
            ))
            warning = max(warning, VoiceConfigV2.MIN_SESSION_WARNING_SECONDS)

            # Auth
            user = await self._validate_jwt_token(token, self._storage)
            if user is None:
                await websocket.close(
                    code=VoiceConfigV2.WS_INVALID_TOKEN, reason="Invalid token",
                )
                return

            if not self._check_session_limit(user.id if hasattr(user, 'id') else str(user)):
                await websocket.close(
                    code=VoiceConfigV2.WS_INVALID_TOKEN, reason="Session limit exceeded",
                )
                return

            logger.info(f"Voice v2 session {session_id} starting for user")

            # Send initial status
            await websocket.send_json({
                "type": "status", "status": "connecting",
                "message": "Initializing voice session",
            })

            # Note: _initialize_adk would be called here in production
            # For the spike tests, we test the auth flow only
            # state = await self._initialize_adk(...)
            # await self._handle_streaming(websocket, state, env_info)

        except Exception as e:
            logger.error(f"Unexpected error for session {session_id}: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error", "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass
        finally:
            if state is not None:
                await self._cleanup_session(state)
                logger.info(f"Voice v2 session {session_id} cleanup completed")

    # endregion

    # region Session Lifecycle

    async def _cleanup_session(self, state: VoiceSessionState) -> None:
        """Clean up session resources and log final stats."""
        duration = (datetime.now(timezone.utc) - state.started_at).total_seconds()
        stats = {
            **state.stats,
            "duration_seconds": duration,
            "termination_reason": state.termination_reason,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Session {state.session_id} final stats: {stats}")

        try:
            await state.chat_logger.log_voice_session_end(
                state.user_id, state.session_id, voice_stats=stats,
            )
        except Exception as e:
            logger.error(f"Failed to log session end: {e}")

        # Persist meta for timer continuity on reconnect
        if state.termination_reason == VoiceConfigV2.REASON_DISCONNECTED:
            try:
                meta_key = VoiceConfigV2.META_KEY_TEMPLATE.format(
                    user_id=state.user_id, session_id=state.session_id,
                )
                meta_data = json.dumps({
                    "started_at": state.started_at.isoformat(),
                    "session_timeout": state.session_timeout,
                    "warning_seconds": state.warning_seconds,
                })
                await self._storage.write(meta_key, meta_data)
            except Exception as e:
                logger.error(f"Failed to persist session meta: {e}")

    # endregion

# endregion
