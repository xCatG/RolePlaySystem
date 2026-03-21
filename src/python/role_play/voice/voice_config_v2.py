"""V2 voice configuration constants.

Extends VoiceConfig with constants for the v2 spike handler:
session timer, heartbeat, sentinels, termination reasons.
Does not modify the original voice_config.py.
"""
from .voice_config import VoiceConfig


class VoiceConfigV2(VoiceConfig):
    """Constants for voice handler v2 spike."""

    # Session timer (per-session overridable via query params)
    DEFAULT_SESSION_TIMEOUT_SECONDS = 2700   # 45 min
    DEFAULT_SESSION_WARNING_SECONDS = 300    # 5 min
    MIN_SESSION_WARNING_SECONDS = 10         # floor for sanity

    # Keepalive
    HEARTBEAT_INTERVAL_SECONDS = 30

    # Context window compression
    CONTEXT_WINDOW_TRIGGER_TOKENS = 100_000
    CONTEXT_WINDOW_STRATEGY = "sliding_window"

    # AI termination sentinels (RPS_ prefix avoids false positives)
    SENTINEL_SESSION_COMPLETE = "[RPS_SESSION_COMPLETE]"
    SENTINEL_END_EARLY = "[RPS_END_EARLY:"  # followed by reason]

    # Termination reasons
    REASON_USER_ENDED = "USER_ENDED"
    REASON_TIME_LIMIT = "TIME_LIMIT"
    REASON_AI_CONCLUDED = "AI_CONCLUDED"
    REASON_AI_EARLY_TERMINATION = "AI_EARLY_TERMINATION"
    REASON_DISCONNECTED = "DISCONNECTED"

    # Storage key templates
    HANDLE_KEY_TEMPLATE = "users/{user_id}/voice_sessions/{session_id}/gemini_handle"
    META_KEY_TEMPLATE = "users/{user_id}/voice_sessions/{session_id}/session_meta"
