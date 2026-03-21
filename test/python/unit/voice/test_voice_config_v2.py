"""Tests for VoiceConfigV2 constants."""
import pytest
from role_play.voice.voice_config_v2 import VoiceConfigV2


def test_session_timeout_default():
    assert VoiceConfigV2.DEFAULT_SESSION_TIMEOUT_SECONDS == 2700


def test_session_warning_default():
    assert VoiceConfigV2.DEFAULT_SESSION_WARNING_SECONDS == 300


def test_warning_floor():
    assert VoiceConfigV2.MIN_SESSION_WARNING_SECONDS == 10


def test_heartbeat_interval():
    assert VoiceConfigV2.HEARTBEAT_INTERVAL_SECONDS == 30


def test_context_window_trigger_tokens():
    assert VoiceConfigV2.CONTEXT_WINDOW_TRIGGER_TOKENS == 100_000


def test_sentinel_patterns():
    assert "RPS_SESSION_COMPLETE" in VoiceConfigV2.SENTINEL_SESSION_COMPLETE
    assert "RPS_END_EARLY" in VoiceConfigV2.SENTINEL_END_EARLY


def test_termination_reasons_are_strings():
    reasons = [
        VoiceConfigV2.REASON_USER_ENDED,
        VoiceConfigV2.REASON_TIME_LIMIT,
        VoiceConfigV2.REASON_AI_CONCLUDED,
        VoiceConfigV2.REASON_AI_EARLY_TERMINATION,
        VoiceConfigV2.REASON_DISCONNECTED,
    ]
    assert all(isinstance(r, str) for r in reasons)


def test_inherits_v1_audio_constants():
    """V2 re-exports V1 audio constants for compatibility."""
    assert VoiceConfigV2.AUDIO_SAMPLE_RATE == 16000
    assert VoiceConfigV2.AUDIO_CHANNELS == 1
    assert VoiceConfigV2.AUDIO_BIT_DEPTH == 16
    assert VoiceConfigV2.AUDIO_FORMAT == "pcm"
