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


def _make_event(**kwargs):
    """Build a mock ADK event with specified attributes."""
    event = MagicMock()
    for attr in ["content", "turn_complete", "interrupted", "partial",
                  "session_resumption_update", "go_away"]:
        if attr not in kwargs:
            delattr(event, attr) if hasattr(event, attr) else None
    for k, v in kwargs.items():
        setattr(event, k, v)
    return event


class TestClassifyAdkEvent:
    """Tests for the sync event classifier."""

    def test_transcript_final_from_model(self):
        part = MagicMock()
        part.text = "Hello there"
        part.inline_data = None
        content = MagicMock()
        content.parts = [part]
        content.role = "model"
        event = _make_event(content=content, partial=False)

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
        event = _make_event(content=content, partial=True)

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
        event = _make_event(content=content, partial=False)

        result = classify_adk_event(event)
        assert result.role == "user"

    def test_audio_event(self):
        part = MagicMock()
        del part.text  # no text attribute
        part.inline_data = MagicMock(data=b"\x01\x02", mime_type="audio/pcm")
        content = MagicMock()
        content.parts = [part]
        event = _make_event(content=content)

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
        event = _make_event(content=content, partial=False)

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
        event = _make_event(content=content, partial=False)

        result = classify_adk_event(event)
        assert result.is_terminal is True
        assert result.terminal_reason == VoiceConfigV2.REASON_AI_EARLY_TERMINATION

    def test_turn_status_complete(self):
        event = _make_event(turn_complete=True, interrupted=False)
        if hasattr(event, "content"):
            event.content = None

        result = classify_adk_event(event)
        assert result.kind == "turn_status"
        assert result.data["turn_complete"] is True

    def test_turn_status_interrupted(self):
        event = _make_event(turn_complete=False, interrupted=True)
        if hasattr(event, "content"):
            event.content = None

        result = classify_adk_event(event)
        assert result.kind == "turn_status"
        assert result.data["interrupted"] is True

    def test_session_resumption_event(self):
        event = _make_event(session_resumption_update="handle-abc-123")
        if hasattr(event, "content"):
            event.content = None

        result = classify_adk_event(event)
        assert result.kind == "session_resumption"
        assert result.data == "handle-abc-123"

    def test_go_away_event(self):
        event = _make_event(go_away=MagicMock())
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
        event = _make_event(content=content)

        result = classify_adk_event(event)
        assert result.kind in ("turn_status", "unknown")

    def test_none_content(self):
        event = _make_event(content=None, turn_complete=True)
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
        chat_logger=AsyncMock(), transcript_buffer=[], stats={},
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


class TestSessionTimer:
    @pytest.fixture
    def handler(self):
        return VoiceHandlerV2(AsyncMock())

    @pytest.mark.asyncio
    async def test_timer_fires_termination_after_timeout(self, handler):
        state = _make_state(session_timeout=1, warning_seconds=0)
        handler._inject_time_warning = AsyncMock()
        handler._handle_termination = AsyncMock()
        ws = AsyncMock()

        await handler._session_timer(ws, state)
        handler._handle_termination.assert_called_once_with(
            ws, state, VoiceConfigV2.REASON_TIME_LIMIT
        )

    @pytest.mark.asyncio
    async def test_timer_exits_early_when_stop_event_set(self, handler):
        state = _make_state(session_timeout=10, warning_seconds=2)
        handler._inject_time_warning = AsyncMock()
        handler._handle_termination = AsyncMock()
        ws = AsyncMock()

        async def set_stop():
            await asyncio.sleep(0.05)
            state.stop_event.set()
        asyncio.create_task(set_stop())

        await handler._session_timer(ws, state)
        handler._handle_termination.assert_not_called()

    @pytest.mark.asyncio
    async def test_timer_calls_inject_warning(self, handler):
        state = _make_state(session_timeout=1, warning_seconds=0)
        handler._inject_time_warning = AsyncMock()
        handler._handle_termination = AsyncMock()
        ws = AsyncMock()

        await handler._session_timer(ws, state)
        handler._inject_time_warning.assert_called_once_with(state)


class TestInjectTimeWarning:
    @pytest.fixture
    def handler(self):
        return VoiceHandlerV2(AsyncMock())

    @pytest.mark.asyncio
    async def test_injects_content_into_queue(self, handler):
        queue = MagicMock()
        session = MagicMock()
        session.state = {}
        state = _make_state(live_request_queue=queue, adk_session=session)

        await handler._inject_time_warning(state)
        queue.send_content.assert_called_once()
        content_arg = queue.send_content.call_args[0][0]
        assert "5 minutes remaining" in content_arg.parts[0].text

    @pytest.mark.asyncio
    async def test_sets_session_state_time_warning(self, handler):
        queue = MagicMock()
        session = MagicMock()
        session.state = {}
        state = _make_state(live_request_queue=queue, adk_session=session)

        await handler._inject_time_warning(state)
        assert session.state.get("time_warning") is True

    @pytest.mark.asyncio
    async def test_survives_queue_failure(self, handler):
        queue = MagicMock()
        queue.send_content.side_effect = RuntimeError("queue closed")
        session = MagicMock()
        session.state = {}
        state = _make_state(live_request_queue=queue, adk_session=session)

        # Should not raise
        await handler._inject_time_warning(state)


class TestHeartbeat:
    @pytest.fixture
    def handler(self):
        return VoiceHandlerV2(AsyncMock())

    @pytest.mark.asyncio
    async def test_heartbeat_exits_when_stop_event_set(self, handler):
        ws = AsyncMock()
        state = _make_state()
        state.stop_event.set()

        await handler._heartbeat(ws, state)
        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_sends_json(self, handler):
        ws = AsyncMock()
        state = _make_state()

        async def stop_after_one():
            await asyncio.sleep(0.05)
            state.stop_event.set()

        with patch.object(VoiceConfigV2, "HEARTBEAT_INTERVAL_SECONDS", 0.01):
            asyncio.create_task(stop_after_one())
            await handler._heartbeat(ws, state)

        assert ws.send_json.call_count >= 1
        msg = ws.send_json.call_args_list[0][0][0]
        assert msg["type"] == "heartbeat"
        assert "timestamp" in msg

    @pytest.mark.asyncio
    async def test_heartbeat_calls_termination_on_connection_error(self, handler):
        ws = AsyncMock()
        ws.send_json.side_effect = ConnectionError("closed")
        state = _make_state()
        handler._handle_termination = AsyncMock()

        with patch.object(VoiceConfigV2, "HEARTBEAT_INTERVAL_SECONDS", 0.01):
            with pytest.raises(ConnectionError):
                await handler._heartbeat(ws, state)

        handler._handle_termination.assert_called_once_with(
            ws, state, VoiceConfigV2.REASON_DISCONNECTED
        )


class TestSendToClient:
    @pytest.fixture
    def handler(self):
        storage = AsyncMock()
        storage.write = AsyncMock()
        return VoiceHandlerV2(storage)

    def _make_live_events(self, events):
        """Create an async generator from a list of events."""
        async def gen():
            for e in events:
                yield e
        return gen()

    @pytest.mark.asyncio
    async def test_audio_sent_to_frontend(self, handler):
        ws = AsyncMock()
        part = MagicMock()
        del part.text
        part.inline_data = MagicMock(data=b"\x01\x02", mime_type="audio/pcm")
        event = _make_event(content=MagicMock(parts=[part]))

        state = _make_state(live_events=self._make_live_events([event]))
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        assert ws.send_json.call_count == 1
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "audio"

    @pytest.mark.asyncio
    async def test_transcript_not_sent_to_frontend(self, handler):
        ws = AsyncMock()
        part = MagicMock(text="Hello", inline_data=None)
        event = _make_event(content=MagicMock(parts=[part], role="model"), partial=False)

        chat_logger = AsyncMock()
        state = _make_state(
            live_events=self._make_live_events([event]),
            chat_logger=chat_logger,
        )
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        # Transcript must NOT be sent to frontend
        ws.send_json.assert_not_called()
        # But must be logged
        chat_logger.log_voice_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcript_appended_to_buffer(self, handler):
        ws = AsyncMock()
        part = MagicMock(text="Test transcript", inline_data=None)
        event = _make_event(content=MagicMock(parts=[part], role="model"), partial=False)

        state = _make_state(live_events=self._make_live_events([event]))
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        assert len(state.transcript_buffer) == 1
        assert state.transcript_buffer[0]["text"] == "Test transcript"

    @pytest.mark.asyncio
    async def test_session_resumption_writes_to_storage(self, handler):
        ws = AsyncMock()
        event = MagicMock(spec=[])
        event.session_resumption_update = "handle-xyz"
        event.content = None

        state = _make_state(live_events=self._make_live_events([event]))
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        handler._storage.write.assert_called_once()
        key = handler._storage.write.call_args[0][0]
        assert "gemini_handle" in key

    @pytest.mark.asyncio
    async def test_terminal_event_triggers_termination(self, handler):
        ws = AsyncMock()
        part = MagicMock(text="Goodbye [RPS_SESSION_COMPLETE]", inline_data=None)
        event = _make_event(content=MagicMock(parts=[part], role="model"), partial=False)

        state = _make_state(live_events=self._make_live_events([event]))
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        handler._handle_termination.assert_called_once()
        call_args = handler._handle_termination.call_args
        assert call_args[0][2] == VoiceConfigV2.REASON_AI_CONCLUDED

    @pytest.mark.asyncio
    async def test_turn_status_sent_to_frontend(self, handler):
        ws = AsyncMock()
        event = _make_event(content=None, turn_complete=True, interrupted=False)

        state = _make_state(live_events=self._make_live_events([event]))
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "turn_status"


class TestReceiveFromClient:
    @pytest.fixture
    def handler(self):
        return VoiceHandlerV2(AsyncMock())

    @pytest.mark.asyncio
    async def test_end_session_triggers_user_ended(self, handler):
        ws = AsyncMock()
        request_json = '{"mime_type": "text/plain", "data": "dGVzdA==", "end_session": true}'
        ws.receive_text = AsyncMock(return_value=request_json)
        state = _make_state()
        handler._handle_termination = AsyncMock()
        env_info = MagicMock(is_production=True)

        await handler._receive_from_client(ws, state, env_info)
        handler._handle_termination.assert_called_once_with(
            ws, state, VoiceConfigV2.REASON_USER_ENDED,
        )

    @pytest.mark.asyncio
    async def test_audio_forwarded_to_adk(self, handler):
        ws = AsyncMock()
        audio_b64 = base64.b64encode(b"\x01\x02").decode()
        request_json = f'{{"mime_type": "audio/pcm", "data": "{audio_b64}", "end_session": false}}'

        call_count = 0
        async def receive_then_stop(self_=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return request_json
            raise WebSocketDisconnect(code=1000)

        ws.receive_text = AsyncMock(side_effect=receive_then_stop)
        queue = MagicMock()
        state = _make_state(live_request_queue=queue)
        handler._handle_termination = AsyncMock()
        env_info = MagicMock(is_production=True)

        await handler._receive_from_client(ws, state, env_info)
        queue.send_realtime.assert_called_once()
        assert state.stats.get("audio_chunks_sent", 0) == 1

    @pytest.mark.asyncio
    async def test_text_forwarded_to_adk(self, handler):
        ws = AsyncMock()
        text_b64 = base64.b64encode(b"Hello").decode()
        request_json = f'{{"mime_type": "text/plain", "data": "{text_b64}", "end_session": false}}'

        call_count = 0
        async def receive_then_stop():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return request_json
            raise WebSocketDisconnect(code=1000)

        ws.receive_text = AsyncMock(side_effect=receive_then_stop)
        queue = MagicMock()
        chat_logger = AsyncMock()
        state = _make_state(live_request_queue=queue, chat_logger=chat_logger)
        handler._handle_termination = AsyncMock()
        env_info = MagicMock(is_production=True)

        await handler._receive_from_client(ws, state, env_info)
        queue.send_content.assert_called_once()
        chat_logger.log_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_triggers_disconnected(self, handler):
        ws = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect(code=1000))
        state = _make_state()
        handler._handle_termination = AsyncMock()
        env_info = MagicMock(is_production=True)

        await handler._receive_from_client(ws, state, env_info)
        handler._handle_termination.assert_called_once_with(
            ws, state, VoiceConfigV2.REASON_DISCONNECTED,
        )

    @pytest.mark.asyncio
    async def test_invalid_json_increments_errors(self, handler):
        ws = AsyncMock()
        call_count = 0
        async def bad_then_disconnect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "not valid json"
            raise WebSocketDisconnect(code=1000)

        ws.receive_text = AsyncMock(side_effect=bad_then_disconnect)
        state = _make_state()
        handler._handle_termination = AsyncMock()
        env_info = MagicMock(is_production=True)

        await handler._receive_from_client(ws, state, env_info)
        assert state.stats.get("errors", 0) >= 1


class TestHandleStreaming:
    @pytest.fixture
    def handler(self):
        return VoiceHandlerV2(AsyncMock())

    @pytest.mark.asyncio
    async def test_orchestrator_cancels_remaining_on_stop(self, handler):
        ws = AsyncMock()
        state = _make_state()
        env_info = MagicMock(is_production=True)

        # Mock all four coroutines — receive terminates immediately
        async def fast_receive(*a, **kw):
            state.stop_event.set()
            state.termination_reason = "USER_ENDED"

        handler._receive_from_client = AsyncMock(side_effect=fast_receive)
        handler._send_to_client = AsyncMock(side_effect=lambda *a, **kw: asyncio.sleep(10))
        handler._session_timer = AsyncMock(side_effect=lambda *a, **kw: asyncio.sleep(10))
        handler._heartbeat = AsyncMock(side_effect=lambda *a, **kw: asyncio.sleep(10))

        await handler._handle_streaming(ws, state, env_info)
        assert state.stop_event.is_set()


class TestCleanupSession:
    @pytest.fixture
    def handler(self):
        storage = AsyncMock()
        storage.write = AsyncMock()
        return VoiceHandlerV2(storage)

    @pytest.mark.asyncio
    async def test_logs_voice_session_end(self, handler):
        chat_logger = AsyncMock()
        state = _make_state(chat_logger=chat_logger, termination_reason="USER_ENDED")

        await handler._cleanup_session(state)
        chat_logger.log_voice_session_end.assert_called_once()

    @pytest.mark.asyncio
    async def test_persists_meta_on_disconnect(self, handler):
        state = _make_state(termination_reason="DISCONNECTED")

        await handler._cleanup_session(state)
        # Should write session_meta for timer continuity
        handler._storage.write.assert_called()
        key = handler._storage.write.call_args[0][0]
        assert "session_meta" in key


class TestHandleVoiceSession:
    @pytest.fixture
    def handler(self):
        storage = AsyncMock()
        storage.exists = AsyncMock(return_value=False)
        return VoiceHandlerV2(storage)

    @pytest.mark.asyncio
    async def test_missing_token_closes_websocket(self, handler):
        ws = AsyncMock()
        ws.query_params = {}
        env_info = MagicMock()

        await handler.handle_voice_session(ws, "sess-1", env_info)
        ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_token_closes_websocket(self, handler):
        ws = AsyncMock()
        ws.query_params = {"token": "bad", "timeout": "60", "warning": "10"}

        with patch.object(
            VoiceHandlerV2, "_validate_jwt_token",
            new_callable=AsyncMock, return_value=None,
        ):
            env_info = MagicMock()
            await handler.handle_voice_session(ws, "sess-1", env_info)
            ws.close.assert_called_once()
