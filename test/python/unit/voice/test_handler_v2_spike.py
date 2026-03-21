"""Tests for voice handler v2 spike — dataclasses and event classification."""
import asyncio
import base64
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from starlette.websockets import WebSocketDisconnect

from role_play.voice.handler_v2_spike import (
    VoiceSessionState,
    EventClassification,
)


class TestVoiceSessionState:
    def test_creation_with_required_fields(self):
        state = VoiceSessionState(
            session_id="sess-1",
            user_id="user-1",
            runner=MagicMock(),
            live_events=MagicMock(),
            live_request_queue=MagicMock(),
            adk_session=MagicMock(),
            stop_event=asyncio.Event(),
            termination_reason=None,
            started_at=datetime.now(timezone.utc),
            session_timeout=60,
            warning_seconds=10,
            chat_logger=MagicMock(),
            transcript_buffer=[],
            stats={"audio_chunks_sent": 0, "errors": 0},
        )
        assert state.session_id == "sess-1"
        assert state.termination_reason is None
        assert state.transcript_buffer == []
        assert not state.stop_event.is_set()

    def test_started_at_is_datetime(self):
        now = datetime.now(timezone.utc)
        state = VoiceSessionState(
            session_id="s", user_id="u", runner=MagicMock(),
            live_events=MagicMock(), live_request_queue=MagicMock(),
            adk_session=MagicMock(), stop_event=asyncio.Event(),
            termination_reason=None, started_at=now,
            session_timeout=60, warning_seconds=10,
            chat_logger=MagicMock(), transcript_buffer=[], stats={},
        )
        assert isinstance(state.started_at, datetime)
        assert state.started_at.tzinfo is not None

    def test_stop_event_can_be_set(self):
        event = asyncio.Event()
        state = VoiceSessionState(
            session_id="s", user_id="u", runner=MagicMock(),
            live_events=MagicMock(), live_request_queue=MagicMock(),
            adk_session=MagicMock(), stop_event=event,
            termination_reason=None, started_at=datetime.now(timezone.utc),
            session_timeout=60, warning_seconds=10,
            chat_logger=MagicMock(), transcript_buffer=[], stats={},
        )
        assert not state.stop_event.is_set()
        state.stop_event.set()
        assert state.stop_event.is_set()


class TestEventClassification:
    def test_audio_event(self):
        ec = EventClassification(kind="audio", data=b"\x01\x02")
        assert ec.kind == "audio"
        assert ec.role is None
        assert ec.is_terminal is False

    def test_transcript_partial(self):
        ec = EventClassification(
            kind="transcript", data="Hello", role="user", is_partial=True
        )
        assert ec.is_partial is True
        assert ec.role == "user"

    def test_terminal_event(self):
        ec = EventClassification(
            kind="transcript", data="Goodbye",
            role="assistant", is_terminal=True,
            terminal_reason="AI_CONCLUDED",
        )
        assert ec.is_terminal is True
        assert ec.terminal_reason == "AI_CONCLUDED"

    def test_unknown_event(self):
        ec = EventClassification(kind="unknown", data={"raw": "stuff"})
        assert ec.kind == "unknown"
