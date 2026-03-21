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
    classify_adk_event,
    VoiceHandlerV2,
)
from role_play.voice.voice_config_v2 import VoiceConfigV2


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


class TestClassifyAdkEvent:
    """Tests for the sync event classifier."""

    def _make_event(self, **kwargs):
        """Build a mock ADK event with specified attributes."""
        event = MagicMock()
        for attr in ["content", "turn_complete", "interrupted", "partial",
                      "session_resumption_update", "go_away"]:
            if attr not in kwargs:
                delattr(event, attr) if hasattr(event, attr) else None
        for k, v in kwargs.items():
            setattr(event, k, v)
        return event

    def test_transcript_final_from_model(self):
        part = MagicMock()
        part.text = "Hello there"
        part.inline_data = None
        content = MagicMock()
        content.parts = [part]
        content.role = "model"
        event = self._make_event(content=content, partial=False)

        result = classify_adk_event(event)
        assert result.kind == "transcript"
        assert result.data == "Hello there"
        assert result.role == "assistant"
        assert result.is_partial is False
        assert result.is_terminal is False

    def test_transcript_partial(self):
        part = MagicMock()
        part.text = "Hel"
        part.inline_data = None
        content = MagicMock()
        content.parts = [part]
        content.role = "model"
        event = self._make_event(content=content, partial=True)

        result = classify_adk_event(event)
        assert result.kind == "transcript"
        assert result.is_partial is True

    def test_transcript_from_user(self):
        part = MagicMock()
        part.text = "My answer"
        part.inline_data = None
        content = MagicMock()
        content.parts = [part]
        content.role = "user"
        event = self._make_event(content=content, partial=False)

        result = classify_adk_event(event)
        assert result.role == "user"

    def test_audio_event(self):
        part = MagicMock()
        del part.text  # no text attribute
        part.inline_data = MagicMock(data=b"\x01\x02", mime_type="audio/pcm")
        content = MagicMock()
        content.parts = [part]
        event = self._make_event(content=content)

        result = classify_adk_event(event)
        assert result.kind == "audio"
        assert result.data["audio_data"] == b"\x01\x02"
        assert result.data["mime_type"] == "audio/pcm"

    def test_sentinel_session_complete(self):
        part = MagicMock()
        part.text = "Thank you for your time. [RPS_SESSION_COMPLETE]"
        part.inline_data = None
        content = MagicMock()
        content.parts = [part]
        content.role = "model"
        event = self._make_event(content=content, partial=False)

        result = classify_adk_event(event)
        assert result.kind == "transcript"
        assert result.is_terminal is True
        assert result.terminal_reason == VoiceConfigV2.REASON_AI_CONCLUDED
        assert VoiceConfigV2.SENTINEL_SESSION_COMPLETE not in result.data

    def test_sentinel_end_early(self):
        part = MagicMock()
        part.text = "I need to stop. [RPS_END_EARLY:off_topic]"
        part.inline_data = None
        content = MagicMock()
        content.parts = [part]
        content.role = "model"
        event = self._make_event(content=content, partial=False)

        result = classify_adk_event(event)
        assert result.is_terminal is True
        assert result.terminal_reason == VoiceConfigV2.REASON_AI_EARLY_TERMINATION

    def test_turn_status_complete(self):
        event = self._make_event(turn_complete=True, interrupted=False)
        if hasattr(event, "content"):
            event.content = None

        result = classify_adk_event(event)
        assert result.kind == "turn_status"
        assert result.data["turn_complete"] is True

    def test_turn_status_interrupted(self):
        event = self._make_event(turn_complete=False, interrupted=True)
        if hasattr(event, "content"):
            event.content = None

        result = classify_adk_event(event)
        assert result.kind == "turn_status"
        assert result.data["interrupted"] is True

    def test_session_resumption_event(self):
        event = self._make_event(session_resumption_update="handle-abc-123")
        if hasattr(event, "content"):
            event.content = None

        result = classify_adk_event(event)
        assert result.kind == "session_resumption"
        assert result.data == "handle-abc-123"

    def test_go_away_event(self):
        event = self._make_event(go_away=MagicMock())
        if hasattr(event, "content"):
            event.content = None

        result = classify_adk_event(event)
        assert result.kind == "go_away"

    def test_unknown_event(self):
        """Event with no recognizable attributes -> unknown."""
        event = MagicMock(spec=[])  # empty spec = no attributes
        result = classify_adk_event(event)
        assert result.kind == "unknown"

    def test_empty_content_parts(self):
        content = MagicMock()
        content.parts = []
        event = self._make_event(content=content)

        result = classify_adk_event(event)
        assert result.kind in ("turn_status", "unknown")

    def test_none_content(self):
        event = self._make_event(content=None, turn_complete=True)
        result = classify_adk_event(event)
        assert result.kind == "turn_status"


def _make_state(**overrides) -> VoiceSessionState:
    """Factory for VoiceSessionState with sensible defaults."""
    defaults = dict(
        session_id="sess-1", user_id="user-1",
        runner=MagicMock(), live_events=MagicMock(),
        live_request_queue=MagicMock(), adk_session=MagicMock(),
        stop_event=asyncio.Event(), termination_reason=None,
        started_at=datetime.now(timezone.utc),
        session_timeout=60, warning_seconds=10,
        chat_logger=MagicMock(), transcript_buffer=[], stats={},
    )
    defaults.update(overrides)
    return VoiceSessionState(**defaults)


class TestHandleTermination:
    @pytest.fixture
    def handler(self):
        storage = AsyncMock()
        return VoiceHandlerV2(storage)

    @pytest.mark.asyncio
    async def test_sets_reason_and_stop_event(self, handler):
        ws = AsyncMock()
        state = _make_state()
        await handler._handle_termination(ws, state, "USER_ENDED")
        assert state.termination_reason == "USER_ENDED"
        assert state.stop_event.is_set()

    @pytest.mark.asyncio
    async def test_sends_session_ended_to_frontend(self, handler):
        ws = AsyncMock()
        state = _make_state()
        await handler._handle_termination(ws, state, "TIME_LIMIT")
        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "session_ended"
        assert msg["reason"] == "TIME_LIMIT"

    @pytest.mark.asyncio
    async def test_closes_queue_for_non_disconnect(self, handler):
        queue = MagicMock()
        state = _make_state(live_request_queue=queue)
        await handler._handle_termination(AsyncMock(), state, "USER_ENDED")
        queue.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_keeps_queue_open_for_disconnected(self, handler):
        queue = MagicMock()
        state = _make_state(live_request_queue=queue)
        await handler._handle_termination(AsyncMock(), state, "DISCONNECTED")
        queue.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_guard_prevents_double_fire(self, handler):
        ws = AsyncMock()
        state = _make_state()
        state.stop_event.set()  # already set
        state.termination_reason = "USER_ENDED"  # already has reason
        await handler._handle_termination(ws, state, "TIME_LIMIT")
        assert state.termination_reason == "USER_ENDED"
        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_websocket_send_failure(self, handler):
        ws = AsyncMock()
        ws.send_json.side_effect = ConnectionError("closed")
        state = _make_state()
        await handler._handle_termination(ws, state, "DISCONNECTED")
        assert state.termination_reason == "DISCONNECTED"
        assert state.stop_event.is_set()

    @pytest.mark.asyncio
    async def test_detail_included_in_message(self, handler):
        ws = AsyncMock()
        state = _make_state()
        await handler._handle_termination(ws, state, "AI_EARLY_TERMINATION", detail="off_topic")
        msg = ws.send_json.call_args[0][0]
        assert msg["detail"] == "off_topic"
