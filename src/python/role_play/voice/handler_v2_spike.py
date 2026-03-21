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
        except (ConnectionError, Exception):
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
            # Create a simple content-like object for the warning
            class _Part:
                def __init__(self, text):
                    self.text = text
            class _Content:
                def __init__(self, parts):
                    self.parts = parts

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
            except (ConnectionError, Exception) as e:
                if isinstance(e, ConnectionError):
                    await self._handle_termination(
                        websocket, state, VoiceConfigV2.REASON_DISCONNECTED,
                    )
                    raise
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
                    state.stats["audio_chunks_received"] = state.stats.get("audio_chunks_received", 0) + 1
                    await websocket.send_json({
                        "type": "audio",
                        "data": base64.b64encode(audio_data).decode("utf-8"),
                        "mime_type": classification.data["mime_type"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif classification.kind == "transcript":
                    # REQ-7: log but do NOT send to frontend
                    state.stats["transcripts_processed"] = state.stats.get("transcripts_processed", 0) + 1
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
        except (ConnectionError, Exception) as e:
            if isinstance(e, ConnectionError):
                logger.error(f"Connection error in _send_to_client: {e}")
                await self._handle_termination(
                    websocket, state, VoiceConfigV2.REASON_DISCONNECTED,
                )
            else:
                logger.error(f"Unexpected error in _send_to_client: {e}", exc_info=True)
                state.stats["errors"] = state.stats.get("errors", 0) + 1

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
                    state.stats["errors"] = state.stats.get("errors", 0) + 1
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
                    state.stats["errors"] = state.stats.get("errors", 0) + 1
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

                        # Create blob-like object
                        class _Blob:
                            def __init__(self, mime_type, data):
                                self.mime_type = mime_type
                                self.data = data
                        blob = _Blob(mime_type=mime_type, data=decoded)
                        state.live_request_queue.send_realtime(blob)
                        state.stats["audio_chunks_sent"] = state.stats.get("audio_chunks_sent", 0) + 1

                    elif mime_type == "text/plain":
                        text_data = decoded.decode("utf-8")
                        await state.chat_logger.log_message(
                            user_id=state.user_id,
                            session_id=state.session_id,
                            role="user",
                            content=text_data,
                            message_number=-1,
                        )
                        class _Part:
                            def __init__(self, text):
                                self.text = text
                        class _Content:
                            def __init__(self, parts):
                                self.parts = parts
                        content = _Content(parts=[_Part(text=text_data)])
                        state.live_request_queue.send_content(content)
                        state.stats["text_chunks_sent"] = state.stats.get("text_chunks_sent", 0) + 1

                except Exception as e:
                    logger.error(f"Error processing client input: {e}")
                    state.stats["errors"] = state.stats.get("errors", 0) + 1

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

# endregion
