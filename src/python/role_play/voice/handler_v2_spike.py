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
