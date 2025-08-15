from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import base64
import pytest
from fastapi import WebSocketDisconnect

from role_play.voice.handler import VoiceChatHandler


@pytest.mark.asyncio
async def test_handle_client_to_agent_audio_and_text(monkeypatch):
    handler = VoiceChatHandler(chat_logger=AsyncMock())

    # Patch Blob, Content, Part to simple test classes
    class DummyBlob:
        def __init__(self, mime_type, data):
            self.mime_type = mime_type
            self.data = data

    class DummyPart:
        def __init__(self, text=None):
            self.text = text

    class DummyContent:
        def __init__(self, parts):
            self.parts = parts

    monkeypatch.setattr("role_play.voice.handler.Blob", DummyBlob)
    monkeypatch.setattr("role_play.voice.handler.Content", DummyContent)
    monkeypatch.setattr("role_play.voice.handler.Part", DummyPart)

    audio_bytes = b"abc"
    ws = AsyncMock()
    ws.receive_json.side_effect = [
        {"type": "audio", "data": base64.b64encode(audio_bytes).decode()},
        {"type": "text", "text": "hi"},
        WebSocketDisconnect(),
    ]

    queue = AsyncMock()
    await handler._handle_client_to_agent(ws, queue)

    queue.send_realtime.assert_awaited()
    blob_arg = queue.send_realtime.await_args.args[0]
    assert isinstance(blob_arg, DummyBlob)
    assert blob_arg.data == audio_bytes

    queue.send_content.assert_awaited()
    content_arg = queue.send_content.await_args.args[0]
    assert isinstance(content_arg, DummyContent)
    assert content_arg.parts[0].text == "hi"


@pytest.mark.asyncio
async def test_handle_agent_to_client_sends_messages(monkeypatch):
    handler = VoiceChatHandler(chat_logger=AsyncMock())
    ws = AsyncMock()

    class DummyInline:
        def __init__(self, data):
            self.data = data
            self.mime_type = "audio/pcm"

    audio_event = SimpleNamespace(
        turn_complete=True,
        interrupted=False,
        input_transcription=SimpleNamespace(text="user words"),
        output_transcription=SimpleNamespace(text="assistant words"),
        content=SimpleNamespace(parts=[SimpleNamespace(inline_data=DummyInline(b"data"), text=None)]),
        partial=False,
    )

    text_event = SimpleNamespace(
        turn_complete=False,
        interrupted=False,
        input_transcription=None,
        output_transcription=None,
        content=SimpleNamespace(parts=[SimpleNamespace(inline_data=None, text="partial")]),
        partial=True,
    )

    async def event_gen():
        yield audio_event
        yield text_event

    await handler._handle_agent_to_client(ws, event_gen(), "sess", "user")

    calls = [call.args[0] for call in ws.send_json.call_args_list]
    assert {"type": "turn_status", "turn_complete": True, "interrupted": False} in calls
    assert {"type": "transcript", "role": "user", "text": "user words"} in calls
    assert {"type": "transcript", "role": "assistant", "text": "assistant words"} in calls
    audio_base64 = base64.b64encode(b"data").decode("utf-8")
    assert {"type": "audio", "data": audio_base64} in calls
    assert {"type": "text", "data": "partial", "partial": True} in calls


@pytest.mark.asyncio
async def test_handle_voice_session_runs_and_cleans(monkeypatch):
    handler = VoiceChatHandler(chat_logger=AsyncMock())
    ws = AsyncMock()
    queue = Mock()

    async def dummy_events():
        if False:
            yield None

    monkeypatch.setattr(handler, "_validate_jwt_token", AsyncMock(return_value=SimpleNamespace(id="u")))
    monkeypatch.setattr(
        handler,
        "_get_adk_session",
        AsyncMock(return_value=SimpleNamespace(state={"character_id": "c", "scenario_id": "s"})),
    )
    handler.voice_service.create_voice_session = AsyncMock(return_value=(dummy_events(), queue))
    monkeypatch.setattr(handler, "_handle_client_to_agent", AsyncMock())
    monkeypatch.setattr(handler, "_handle_agent_to_client", AsyncMock())

    await handler.handle_voice_session(ws, "sess", "token")

    handler._handle_client_to_agent.assert_awaited()
    handler._handle_agent_to_client.assert_awaited()
    assert queue.close.called


@pytest.mark.asyncio
async def test_transcript_buffer_logged(monkeypatch):
    chat_logger = AsyncMock()
    handler = VoiceChatHandler(chat_logger=chat_logger)
    ws = AsyncMock()

    # Two partial text events followed by turn completion
    part_event1 = SimpleNamespace(
        turn_complete=False,
        interrupted=False,
        input_transcription=None,
        output_transcription=None,
        content=SimpleNamespace(parts=[SimpleNamespace(inline_data=None, text="Hello ")]),
        partial=True,
    )
    part_event2 = SimpleNamespace(
        turn_complete=False,
        interrupted=False,
        input_transcription=None,
        output_transcription=None,
        content=SimpleNamespace(parts=[SimpleNamespace(inline_data=None, text="world")]),
        partial=True,
    )
    turn_event = SimpleNamespace(
        turn_complete=True,
        interrupted=False,
        input_transcription=None,
        output_transcription=None,
        content=None,
        partial=False,
    )

    async def events():
        yield part_event1
        yield part_event2
        yield turn_event

    await handler._handle_agent_to_client(ws, events(), "sess", "user")

    # Ensure full transcript logged once
    chat_logger.log_message.assert_awaited_once_with(
        user_id="user",
        session_id="sess",
        role="assistant",
        content="Hello world",
        message_number=1,
    )

    # Partial text chunks forwarded to client
    sends = [c.args[0] for c in ws.send_json.call_args_list]
    assert {"type": "text", "data": "Hello ", "partial": True} in sends
    assert {"type": "text", "data": "world", "partial": True} in sends
    assert {"type": "turn_status", "turn_complete": True, "interrupted": False} in sends
