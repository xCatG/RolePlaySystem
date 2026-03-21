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
