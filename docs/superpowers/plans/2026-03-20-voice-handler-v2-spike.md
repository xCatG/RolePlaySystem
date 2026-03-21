# Voice Handler V2 Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `handler_v2_spike.py` — a prototype voice handler for 45-minute behavioral interviews addressing all gaps from the voice handler gap report.

**Architecture:** Single file with dataclasses (`VoiceSessionState`, `EventClassification`) and one handler class (`VoiceHandlerV2`). Four concurrent coroutines (receive, send, timer, heartbeat) coordinated by a shared `asyncio.Event` stop signal. Storage injected at construction. Sync event classifier + async router split.

**Tech Stack:** Python 3.11+, FastAPI/Starlette WebSocket, google-adk (`Runner`, `LiveRequestQueue`, `RunConfig`), google-genai types, pytest/pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-20-voice-handler-v2-spike-design.md`

**Constraints:**
- Do NOT modify any existing files
- All output goes to new files only
- Use existing `StorageBackend` interface (no new abstract methods)
- Use `google.genai` types (not `google.generativeai`)
- All new async methods must be `async def`

---

## File Structure

| File | Purpose |
|---|---|
| **Create:** `src/python/role_play/voice/handler_v2_spike.py` | Main handler — dataclasses, `VoiceHandlerV2` class |
| **Create:** `src/python/role_play/voice/voice_config_v2.py` | V2-specific constants (extends VoiceConfig without modifying it) |
| **Create:** `test/python/unit/voice/test_handler_v2_spike.py` | Unit tests for all testable methods |
| **Read (reference only):** `src/python/role_play/voice/handler.py` | V1 handler — reference for auth methods, patterns |
| **Read (reference only):** `src/python/role_play/voice/voice_config.py` | V1 config — inheritable constants |
| **Read (reference only):** `src/python/role_play/voice/models.py` | `VoiceRequest` model — reused as-is |
| **Read (reference only):** `src/python/role_play/server/base_handler.py` | `BaseHandler` ABC — must implement `router`, `prefix` |
| **Read (reference only):** `src/python/role_play/common/storage.py` | `StorageBackend` interface — `read`, `write`, `exists`, `read_bytes`, `write_bytes` |

---

## Task 1: VoiceConfigV2 Constants

**Files:**
- Create: `src/python/role_play/voice/voice_config_v2.py`
- Create: `test/python/unit/voice/test_voice_config_v2.py`

- [ ] **Step 1: Write the test file**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_voice_config_v2.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'role_play.voice.voice_config_v2'`

- [ ] **Step 3: Write the implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_voice_config_v2.py`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/role_play/voice/voice_config_v2.py test/python/unit/voice/test_voice_config_v2.py
git commit -m "feat(voice): add VoiceConfigV2 constants for v2 spike"
```

---

## Task 2: Dataclasses — VoiceSessionState & EventClassification

**Files:**
- Create: `src/python/role_play/voice/handler_v2_spike.py` (initial scaffold — dataclasses + imports only)
- Create: `test/python/unit/voice/test_handler_v2_spike.py` (initial scaffold)

- [ ] **Step 1: Write the test file for dataclasses**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the initial handler file with dataclasses**

Create `src/python/role_play/voice/handler_v2_spike.py` with:

```python
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

from fastapi import WebSocket, HTTPException, APIRouter
from google.adk import Runner
from google.adk.agents import RunConfig, LiveRequestQueue
from google.adk.sessions import BaseSessionService
from google.genai.types import (
    AudioTranscriptionConfig, Blob, Part, Content, Modality,
)
from starlette.websockets import WebSocketDisconnect

from .models import VoiceRequest
from .voice_config_v2 import VoiceConfigV2
from ..chat.chat_logger import ChatLogger
from ..common.exceptions import TokenExpiredError, AuthenticationError
from ..common.models import User, EnvironmentInfo
from ..common.storage import StorageBackend
from ..common.time_utils import utc_now_isoformat
from ..dev_agents.roleplay_agent.agent import get_production_agent
from ..server.base_handler import BaseHandler
from ..server.dependencies import (
    get_chat_logger,
    get_adk_session_service,
    get_auth_manager,
    get_environment_info,
)

logger = logging.getLogger(__name__)


# region Dataclasses

@dataclass
class EventClassification:
    """Result of classifying an ADK live event.

    Pure data — no side effects. Built by _classify_adk_event (sync).
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
    runner: Runner
    live_events: AsyncGenerator
    live_request_queue: LiveRequestQueue
    adk_session: Any
    stop_event: asyncio.Event
    termination_reason: Optional[str]
    started_at: datetime
    session_timeout: int
    warning_seconds: int
    chat_logger: ChatLogger
    transcript_buffer: List[Dict] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=lambda: {
        "audio_chunks_sent": 0,
        "audio_chunks_received": 0,
        "text_chunks_sent": 0,
        "transcripts_processed": 0,
        "errors": 0,
    })

# endregion
```

- [ ] **Step 4: Run test to verify it passes**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): add v2 spike dataclasses — VoiceSessionState, EventClassification"
```

---

## Task 3: Event Classifier — `_classify_adk_event`

**Files:**
- Modify: `test/python/unit/voice/test_handler_v2_spike.py` (add classifier tests)
- Modify: `src/python/role_play/voice/handler_v2_spike.py` (add classifier as module-level function)

The classifier is a pure sync function — no class needed yet. It takes an event and returns an `EventClassification`. This makes it trivially testable.

**Spec deviation:** The spec's method inventory (Section 10) lists `_classify_adk_event` as a class method. We deliberately implement it as a module-level `classify_adk_event` (public, no `self`) because it's a pure function with no dependency on handler state. This improves testability — tests call it directly without instantiating the handler class.

- [ ] **Step 1: Write the tests**

Add to `test/python/unit/voice/test_handler_v2_spike.py`:

```python
from role_play.voice.handler_v2_spike import classify_adk_event
from role_play.voice.voice_config_v2 import VoiceConfigV2


class TestClassifyAdkEvent:
    """Tests for the sync event classifier."""

    def _make_event(self, **kwargs):
        """Build a mock ADK event with specified attributes."""
        event = MagicMock()
        # Remove all optional attributes by default
        for attr in ["content", "turn_complete", "interrupted", "partial",
                      "session_resumption_update", "go_away"]:
            if attr not in kwargs:
                # Use spec to control which attributes exist
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
        # Ensure no content
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
        """Event with no recognizable attributes → unknown."""
        event = MagicMock(spec=[])  # empty spec = no attributes
        result = classify_adk_event(event)
        assert result.kind == "unknown"

    def test_empty_content_parts(self):
        content = MagicMock()
        content.parts = []
        event = self._make_event(content=content)

        result = classify_adk_event(event)
        # Empty content falls through to turn_status or unknown
        assert result.kind in ("turn_status", "unknown")

    def test_none_content(self):
        event = self._make_event(content=None, turn_complete=True)
        result = classify_adk_event(event)
        assert result.kind == "turn_status"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestClassifyAdkEvent`
Expected: FAIL — `ImportError: cannot import name 'classify_adk_event'`

- [ ] **Step 3: Implement `classify_adk_event`**

Add to `handler_v2_spike.py` after the dataclass definitions:

```python
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
        # Handle could be string, bytes, or complex object
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
            # Text content → transcript
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
                    # Strip sentinel: [RPS_END_EARLY:reason]
                    idx = text.find(VoiceConfigV2.SENTINEL_END_EARLY)
                    end_idx = text.find("]", idx)
                    if end_idx != -1:
                        text = (text[:idx] + text[end_idx + 1:]).strip()

                return EventClassification(
                    kind="transcript", data=text, role=role,
                    is_partial=is_partial, is_terminal=is_terminal,
                    terminal_reason=terminal_reason,
                )

            # Audio content → audio
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestClassifyAdkEvent`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): add sync event classifier for v2 spike"
```

---

## Task 4: Termination Handler — `_handle_termination`

This is the single convergence point. Must be tested before the coroutines that call it.

**Files:**
- Modify: `test/python/unit/voice/test_handler_v2_spike.py` (add termination tests)
- Modify: `src/python/role_play/voice/handler_v2_spike.py` (add `VoiceHandlerV2` class with `_handle_termination`)

- [ ] **Step 1: Write the tests**

Add to `test/python/unit/voice/test_handler_v2_spike.py`:

```python
from role_play.voice.handler_v2_spike import VoiceHandlerV2


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
        # Should not overwrite reason or send another message
        assert state.termination_reason == "USER_ENDED"
        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_websocket_send_failure(self, handler):
        ws = AsyncMock()
        ws.send_json.side_effect = ConnectionError("closed")
        state = _make_state()
        # Should not raise — swallows the connection error
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestHandleTermination`
Expected: FAIL — `ImportError: cannot import name 'VoiceHandlerV2'`

- [ ] **Step 3: Implement `VoiceHandlerV2` with `_handle_termination`**

Add to `handler_v2_spike.py`:

```python
# region Handler

class VoiceHandlerV2(BaseHandler):
    """Voice handler v2 spike for 45-minute behavioral interviews.

    Not registered via standard handler registration.
    Uses /voice-v2 prefix to avoid conflicts with v1.
    Storage injected at construction.
    """

    def __init__(self, storage: StorageBackend):
        super().__init__()
        self._storage = storage

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()
            # WebSocket route defined here — tested manually, not via handler registration
        return self._router

    @property
    def prefix(self) -> str:
        return "/voice-v2"

    # region Termination

    async def _handle_termination(
        self,
        websocket: WebSocket,
        state: VoiceSessionState,
        reason: str,
        detail: Optional[str] = None,
    ) -> None:
        """Single convergence point for all session exit paths.

        Guard: check-and-set stop_event atomically (no await between
        check and set — safe in single-threaded event loop).
        """
        # Guard: prevent double-fire
        if state.stop_event.is_set():
            return
        state.stop_event.set()
        state.termination_reason = reason

        # Notify frontend (may fail for DISCONNECTED — that's fine)
        try:
            await websocket.send_json({
                "type": "session_ended",
                "reason": reason,
                "detail": detail,
                "timestamp": utc_now_isoformat(),
            })
        except (ConnectionError, WebSocketDisconnect, RuntimeError):
            pass  # Socket may already be closed

        # Close queue unless resumable
        if reason != VoiceConfigV2.REASON_DISCONNECTED:
            state.live_request_queue.close()

        logger.info(
            f"Session {state.session_id} terminated: reason={reason}, detail={detail}"
        )

    # endregion

# endregion
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestHandleTermination`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): add VoiceHandlerV2 class with _handle_termination"
```

---

## Task 5: Session Timer & Warning Injection

**Files:**
- Modify: `test/python/unit/voice/test_handler_v2_spike.py`
- Modify: `src/python/role_play/voice/handler_v2_spike.py`

- [ ] **Step 1: Write the tests**

Add to test file:

```python
class TestSessionTimer:
    @pytest.fixture
    def handler(self):
        return VoiceHandlerV2(AsyncMock())

    @pytest.mark.asyncio
    async def test_timer_fires_termination_after_timeout(self, handler):
        state = _make_state(session_timeout=1, warning_seconds=0)
        # Patch _inject_time_warning and _handle_termination
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

        # Set stop event after a very short delay
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestSessionTimer`
Expected: FAIL — `AttributeError: 'VoiceHandlerV2' object has no attribute '_session_timer'`

- [ ] **Step 3: Implement `_session_timer` and `_inject_time_warning`**

Add to `VoiceHandlerV2` class:

```python
    # region Timer

    async def _session_timer(
        self, websocket: WebSocket, state: VoiceSessionState,
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
        Failures are logged as spike discovery data, not propagated.
        """
        # Approach 1: State update (likely won't propagate mid-stream)
        try:
            state.adk_session.state["time_warning"] = True
            logger.info(f"Session {state.session_id}: set time_warning=True in session state")
        except Exception as e:
            logger.warning(f"Session {state.session_id}: state update failed: {e}")

        # Approach 2: Content injection (primary approach)
        try:
            warning_content = Content(
                parts=[Part(text="[SYSTEM] 5 minutes remaining. Begin wrapping up the interview.")]
            )
            state.live_request_queue.send_content(warning_content)
            logger.info(f"Session {state.session_id}: injected time warning content")
        except Exception as e:
            logger.warning(f"Session {state.session_id}: content injection failed: {e}")

    # endregion
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py -k "TestSessionTimer or TestInjectTimeWarning"`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): add session timer with dual warning injection"
```

---

## Task 6: Heartbeat Coroutine

**Files:**
- Modify: `test/python/unit/voice/test_handler_v2_spike.py`
- Modify: `src/python/role_play/voice/handler_v2_spike.py`

- [ ] **Step 1: Write the tests**

```python
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

        # Use very short interval for testing
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestHeartbeat`
Expected: FAIL

- [ ] **Step 3: Implement `_heartbeat`**

Add to `VoiceHandlerV2`:

```python
    # region Keepalive

    async def _heartbeat(self, websocket: WebSocket, state: VoiceSessionState) -> None:
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
                    "timestamp": utc_now_isoformat(),
                })
            except (ConnectionError, WebSocketDisconnect):
                await self._handle_termination(
                    websocket, state, VoiceConfigV2.REASON_DISCONNECTED,
                )
                raise

    # endregion
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestHeartbeat`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): add heartbeat coroutine with disconnect detection"
```

---

## Task 7: Event Router — `_send_to_client`

**Files:**
- Modify: `test/python/unit/voice/test_handler_v2_spike.py`
- Modify: `src/python/role_play/voice/handler_v2_spike.py`

- [ ] **Step 1: Write the tests**

```python
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
        event = MagicMock()
        event.content = MagicMock(parts=[part])
        for attr in ["turn_complete", "interrupted", "session_resumption_update", "go_away"]:
            if hasattr(event, attr):
                delattr(event, attr)

        state = _make_state(live_events=self._make_live_events([event]))
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        assert ws.send_json.call_count == 1
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "audio"

    @pytest.mark.asyncio
    async def test_transcript_not_sent_to_frontend(self, handler):
        ws = AsyncMock()
        part = MagicMock()
        part.text = "Hello"
        part.inline_data = None
        event = MagicMock()
        event.content = MagicMock(parts=[part], role="model")
        event.partial = False
        for attr in ["turn_complete", "interrupted", "session_resumption_update", "go_away"]:
            if hasattr(event, attr):
                delattr(event, attr)

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
        part = MagicMock()
        part.text = "Test transcript"
        part.inline_data = None
        event = MagicMock()
        event.content = MagicMock(parts=[part], role="model")
        event.partial = False
        for attr in ["turn_complete", "interrupted", "session_resumption_update", "go_away"]:
            if hasattr(event, attr):
                delattr(event, attr)

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
        part = MagicMock()
        part.text = "Goodbye [RPS_SESSION_COMPLETE]"
        part.inline_data = None
        event = MagicMock()
        event.content = MagicMock(parts=[part], role="model")
        event.partial = False
        for attr in ["turn_complete", "interrupted", "session_resumption_update", "go_away"]:
            if hasattr(event, attr):
                delattr(event, attr)

        state = _make_state(live_events=self._make_live_events([event]))
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        handler._handle_termination.assert_called_once()
        call_args = handler._handle_termination.call_args
        assert call_args[0][2] == VoiceConfigV2.REASON_AI_CONCLUDED

    @pytest.mark.asyncio
    async def test_turn_status_sent_to_frontend(self, handler):
        ws = AsyncMock()
        event = MagicMock()
        event.content = None
        event.turn_complete = True
        event.interrupted = False
        for attr in ["session_resumption_update", "go_away"]:
            if hasattr(event, attr):
                delattr(event, attr)

        state = _make_state(live_events=self._make_live_events([event]))
        handler._handle_termination = AsyncMock()

        await handler._send_to_client(ws, state)
        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "turn_status"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestSendToClient`
Expected: FAIL

- [ ] **Step 3: Implement `_send_to_client`**

Add to `VoiceHandlerV2`:

```python
    # region Event Routing

    async def _send_to_client(
        self, websocket: WebSocket, state: VoiceSessionState,
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
                    state.stats["audio_chunks_received"] += 1
                    await websocket.send_json({
                        "type": "audio",
                        "data": base64.b64encode(audio_data).decode("utf-8"),
                        "mime_type": classification.data["mime_type"],
                        "timestamp": utc_now_isoformat(),
                    })

                elif classification.kind == "transcript":
                    # REQ-7: log but do NOT send to frontend
                    state.stats["transcripts_processed"] += 1
                    entry = {
                        "text": classification.data,
                        "role": classification.role,
                        "is_partial": classification.is_partial,
                        "timestamp": utc_now_isoformat(),
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
                        if classification.terminal_reason == VoiceConfigV2.REASON_AI_EARLY_TERMINATION:
                            # Log extra context for future human review
                            recent = state.transcript_buffer[-5:]
                            logger.warning(
                                f"Session {state.session_id}: AI_EARLY_TERMINATION, "
                                f"recent transcripts: {recent}"
                            )
                        await self._handle_termination(
                            websocket, state, classification.terminal_reason,
                        )
                        return

                elif classification.kind == "turn_status":
                    # Log turn_complete correlation for analysis
                    if classification.data.get("turn_complete") and state.transcript_buffer:
                        logger.debug(
                            f"Session {state.session_id}: turn_complete after "
                            f"'{state.transcript_buffer[-1].get('text', '')[:50]}'"
                        )
                    await websocket.send_json({
                        "type": "turn_status",
                        **classification.data,
                        "timestamp": utc_now_isoformat(),
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
        except (ConnectionError, WebSocketDisconnect) as e:
            logger.error(f"Connection error in _send_to_client: {e}")
            await self._handle_termination(
                websocket, state, VoiceConfigV2.REASON_DISCONNECTED,
            )
        except Exception as e:
            logger.error(f"Unexpected error in _send_to_client: {e}", exc_info=True)
            state.stats["errors"] += 1

    # endregion
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestSendToClient`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): add event router with transcript suppression and handle persistence"
```

---

## Task 8: Receive From Client — `_receive_from_client`

**Files:**
- Modify: `test/python/unit/voice/test_handler_v2_spike.py`
- Modify: `src/python/role_play/voice/handler_v2_spike.py`

- [ ] **Step 1: Write the tests**

```python
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
        assert state.stats["audio_chunks_sent"] == 1

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
        assert state.stats["errors"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestReceiveFromClient`
Expected: FAIL

- [ ] **Step 3: Implement `_receive_from_client`**

Add to `VoiceHandlerV2`:

```python
    # region Client Input

    async def _receive_from_client(
        self,
        websocket: WebSocket,
        state: VoiceSessionState,
        env_info: EnvironmentInfo,
    ) -> None:
        """Receive from client and forward to ADK.

        Handles audio/pcm and text/plain. end_session triggers USER_ENDED.
        WebSocketDisconnect triggers DISCONNECTED.
        """
        try:
            while not state.stop_event.is_set():
                data = await websocket.receive_text()

                try:
                    request = VoiceRequest.model_validate_json(data)
                except ValueError as e:
                    logger.warning(f"Invalid JSON from client: {e}")
                    state.stats["errors"] += 1
                    continue

                if request.end_session:
                    await self._handle_termination(
                        websocket, state, VoiceConfigV2.REASON_USER_ENDED,
                    )
                    return

                try:
                    if request.mime_type == "audio/pcm":
                        audio_data = request.decode_data()
                        if audio_data is None:
                            state.stats["errors"] += 1
                            continue

                        # PCM logging in non-production (same as v1)
                        if not env_info.is_production:
                            try:
                                await state.chat_logger.log_pcm_audio(
                                    user_id=state.user_id,
                                    session_id=state.session_id,
                                    audio_data=audio_data,
                                )
                            except (AttributeError, Exception) as e:
                                logger.debug(f"PCM logging skipped: {e}")

                        blob = Blob(mime_type=request.mime_type, data=audio_data)
                        state.live_request_queue.send_realtime(blob)
                        state.stats["audio_chunks_sent"] += 1

                    elif request.mime_type == "text/plain":
                        text_data = request.decode_data()
                        if text_data is None:
                            state.stats["errors"] += 1
                            continue

                        await state.chat_logger.log_message(
                            user_id=state.user_id,
                            session_id=state.session_id,
                            role="user",
                            content=text_data,
                            message_number=-1,
                        )
                        content = Content(parts=[Part(text=text_data)])
                        state.live_request_queue.send_content(content)
                        state.stats["text_chunks_sent"] += 1

                except Exception as e:
                    logger.error(f"Error processing client input: {e}")
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestReceiveFromClient`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): add client input receiver with termination routing"
```

---

## Task 9: Streaming Orchestrator & Session Lifecycle

**Files:**
- Modify: `test/python/unit/voice/test_handler_v2_spike.py`
- Modify: `src/python/role_play/voice/handler_v2_spike.py`

This is the final assembly — `_handle_streaming`, `_initialize_adk`, `_cleanup_session`, `handle_voice_session`, and the WebSocket route.

- [ ] **Step 1: Write the tests for `_handle_streaming`**

```python
class TestHandleStreaming:
    @pytest.fixture
    def handler(self):
        return VoiceHandlerV2(AsyncMock())

    @pytest.mark.asyncio
    async def test_orchestrator_cancels_remaining_on_stop(self, handler):
        ws = AsyncMock()
        state = _make_state()
        env_info = MagicMock(is_production=True)

        # Mock all four coroutines
        async def fast_receive(*a, **kw):
            await self_handler._handle_termination(ws, state, "USER_ENDED")
        self_handler = handler

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py -k "TestHandleStreaming or TestCleanupSession"`
Expected: FAIL

- [ ] **Step 3: Implement orchestrator, cleanup, and initialize_adk**

Add to `VoiceHandlerV2`:

```python
    # region Streaming Orchestrator

    async def _handle_streaming(
        self,
        websocket: WebSocket,
        state: VoiceSessionState,
        env_info: EnvironmentInfo,
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

    # region Session Lifecycle

    async def _initialize_adk(
        self,
        session_id: str,
        user: User,
        adk_session: Any,
        adk_session_service: BaseSessionService,
        session_timeout: int,
        warning_seconds: int,
    ) -> VoiceSessionState:
        """Initialize ADK components and build VoiceSessionState.

        Checks for existing resumption handle and session metadata.
        Writes initial session_meta for timer continuity.
        """
        # Check for resumption handle
        handle_key = VoiceConfigV2.HANDLE_KEY_TEMPLATE.format(
            user_id=user.id, session_id=session_id,
        )
        meta_key = VoiceConfigV2.META_KEY_TEMPLATE.format(
            user_id=user.id, session_id=session_id,
        )

        existing_handle = None
        if await self._storage.exists(handle_key):
            existing_handle = await self._storage.read(handle_key)
            logger.info(f"Session {session_id}: found resumption handle")

        # Read session meta for timer continuity
        started_at = datetime.now(timezone.utc)
        if await self._storage.exists(meta_key):
            try:
                meta = json.loads(await self._storage.read(meta_key))
                started_at = datetime.fromisoformat(meta["started_at"])
                session_timeout = meta.get("session_timeout", session_timeout)
                warning_seconds = meta.get("warning_seconds", warning_seconds)
                logger.info(f"Session {session_id}: resumed with original started_at")
            except Exception as e:
                logger.warning(f"Session {session_id}: failed to read meta: {e}")

        # Create agent
        agent = await get_production_agent(
            character_id=adk_session.state.get("character_id"),
            scenario_id=adk_session.state.get("scenario_id"),
            language=getattr(user, "preferred_language", "en"),
            scripted=bool(adk_session.state.get("script_data")),
            agent_model="gemini-2.5-flash-live-preview",
        )
        if not agent:
            raise ValueError("Failed to create roleplay agent")

        # Build RunConfig
        run_config_kwargs = dict(
            response_modalities=[Modality.AUDIO],
            output_audio_transcription=AudioTranscriptionConfig(),
            input_audio_transcription=AudioTranscriptionConfig(),
        )

        # Context window compression (verify SDK support at runtime)
        try:
            from google.genai.types import ContextWindowCompressionConfig
            run_config_kwargs["context_window_compression"] = ContextWindowCompressionConfig(
                trigger_tokens=VoiceConfigV2.CONTEXT_WINDOW_TRIGGER_TOKENS,
                sliding_window=True,
            )
            logger.info("Context window compression enabled")
        except (ImportError, AttributeError, TypeError) as e:
            logger.warning(f"Context window compression not available: {e}")

        # Session resumption config (verify SDK support at runtime)
        if existing_handle:
            try:
                from google.genai.types import SessionResumptionConfig
                run_config_kwargs["session_resumption_config"] = SessionResumptionConfig(
                    handle=existing_handle,
                )
                logger.info("Session resumption handle applied")
            except (ImportError, AttributeError, TypeError) as e:
                logger.warning(f"Session resumption not available in SDK: {e}")

        run_config = RunConfig(**run_config_kwargs)

        # Create runner and start live streaming
        runner = Runner(
            app_name="roleplay_chat", agent=agent,
            session_service=adk_session_service,
        )
        live_request_queue = LiveRequestQueue()
        live_events = runner.run_live(
            session=adk_session,
            live_request_queue=live_request_queue,
            run_config=run_config,
        )

        chat_logger = get_chat_logger(self._storage)

        state = VoiceSessionState(
            session_id=session_id,
            user_id=user.id,
            runner=runner,
            live_events=live_events,
            live_request_queue=live_request_queue,
            adk_session=adk_session,
            stop_event=asyncio.Event(),
            termination_reason=None,
            started_at=started_at,
            session_timeout=session_timeout,
            warning_seconds=warning_seconds,
            chat_logger=chat_logger,
        )

        # Write initial session_meta for timer continuity on reconnect
        meta_data = json.dumps({
            "started_at": started_at.isoformat(),
            "session_timeout": session_timeout,
            "warning_seconds": warning_seconds,
        })
        await self._storage.write(meta_key, meta_data)

        return state

    async def _cleanup_session(self, state: VoiceSessionState) -> None:
        """Clean up session resources and log final stats."""
        duration = (datetime.now(timezone.utc) - state.started_at).total_seconds()
        stats = {
            **state.stats,
            "duration_seconds": duration,
            "termination_reason": state.termination_reason,
            "ended_at": utc_now_isoformat(),
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

    # region Auth (unchanged from v1)

    @staticmethod
    async def _validate_jwt_token(token: str, storage: StorageBackend) -> Optional[User]:
        """Validate JWT token and return user."""
        try:
            auth_manager = get_auth_manager(storage)
            token_data = auth_manager.verify_token(token)
            user = await storage.get_user(token_data.user_id)
            if user is None:
                raise HTTPException(status_code=401, detail="User not found")
            return user
        except TokenExpiredError as exc:
            raise HTTPException(status_code=401, detail="Token expired") from exc
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            raise HTTPException(status_code=401, detail="Unknown error during validation") from e

    def _check_session_limit(self, user_id: str) -> bool:
        """Placeholder — always returns True. See VoiceConfig docstring."""
        return True

    # endregion
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py -k "TestHandleStreaming or TestCleanupSession"`
Expected: All 3 tests PASS

- [ ] **Step 5: Run the full test suite**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py -v`
Expected: All tests PASS (dataclasses + classifier + termination + timer + heartbeat + router + orchestrator + cleanup)

- [ ] **Step 6: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): add streaming orchestrator, session lifecycle, and cleanup"
```

---

## Task 10: WebSocket Route & Entry Point

**Files:**
- Modify: `src/python/role_play/voice/handler_v2_spike.py` (flesh out `router` property and `handle_voice_session`)

- [ ] **Step 1: Write test for `handle_voice_session` auth flow**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestHandleVoiceSession`
Expected: FAIL

- [ ] **Step 3: Implement `handle_voice_session` and `router`**

Update the `router` property and add `handle_voice_session`:

```python
    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

            @self._router.websocket("/ws/{session_id}")
            async def voice_v2_websocket(
                websocket: WebSocket,
                session_id: str,
                environment_info: Annotated[EnvironmentInfo, Depends(get_environment_info)],
            ):
                await websocket.accept()
                await self.handle_voice_session(websocket, session_id, environment_info)

        return self._router

    async def handle_voice_session(
        self,
        websocket: WebSocket,
        session_id: str,
        env_info: EnvironmentInfo,
    ) -> None:
        """Entry point for a voice WebSocket connection.

        Auth → session lookup → ADK init → streaming → cleanup.
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

            if not self._check_session_limit(user.id):
                await websocket.close(
                    code=VoiceConfigV2.WS_INVALID_TOKEN, reason="Session limit exceeded",
                )
                return

            # Session lookup
            adk_session_service = get_adk_session_service()
            adk_session = await adk_session_service.get_session(
                app_name="roleplay_chat", user_id=user.id, session_id=session_id,
            )
            if not adk_session:
                await websocket.close(
                    code=VoiceConfigV2.WS_SESSION_NOT_FOUND, reason="Session not found",
                )
                return

            logger.info(f"Voice v2 session {session_id} starting for user {user.id}")

            # Send initial status
            user_lang = getattr(user, "preferred_language", "en")
            await websocket.send_json({
                "type": "status", "status": "connecting",
                "message": "Initializing voice session",
            })

            # Initialize ADK
            state = await self._initialize_adk(
                session_id=session_id, user=user,
                adk_session=adk_session,
                adk_session_service=adk_session_service,
                session_timeout=timeout, warning_seconds=warning,
            )

            # Send config
            await websocket.send_json({
                "type": "config",
                "audio_format": VoiceConfigV2.AUDIO_FORMAT,
                "sample_rate": VoiceConfigV2.AUDIO_SAMPLE_RATE,
                "channels": VoiceConfigV2.AUDIO_CHANNELS,
                "bit_depth": VoiceConfigV2.AUDIO_BIT_DEPTH,
                "language": user_lang,
                "session_timeout": timeout,
                "warning_seconds": warning,
            })

            await state.chat_logger.log_voice_session_start(
                user.id, session_id,
                voice_config={"language": user_lang, "timeout": timeout},
            )

            await websocket.send_json({
                "type": "status", "status": "ready",
                "message": "Voice session ready",
            })

            # Run streaming
            await self._handle_streaming(websocket, state, env_info)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"Unexpected error for session {session_id}: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error", "error": str(e),
                    "timestamp": utc_now_isoformat(),
                })
            except Exception:
                pass
        finally:
            if state is not None:
                await self._cleanup_session(state)
                logger.info(f"Voice v2 session {session_id} cleanup completed")
```

Add the missing import at the top of the file:

```python
from typing import Optional, Dict, Any, AsyncGenerator, List, Annotated
from fastapi import WebSocket, HTTPException, APIRouter, Depends
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py::TestHandleVoiceSession`
Expected: All 2 tests PASS

- [ ] **Step 5: Run the full v2 test suite**

Run: `make test-specific TEST_PATH=test/python/unit/voice/test_handler_v2_spike.py -v`
Expected: ALL tests PASS

- [ ] **Step 6: Run existing v1 tests to confirm no breakage**

Run: `make test-voice`
Expected: All existing voice tests still PASS

- [ ] **Step 7: Commit**

```bash
git add src/python/role_play/voice/handler_v2_spike.py test/python/unit/voice/test_handler_v2_spike.py
git commit -m "feat(voice): complete v2 spike — WebSocket route, session lifecycle, full test suite"
```

---

## Task 11: Final Verification & Smoke Test

- [ ] **Step 1: Run full project test suite**

Run: `make test`
Expected: All 260+ tests PASS, no regressions from v2 spike files

- [ ] **Step 2: Verify no existing files were modified**

Run: `git diff --name-only HEAD~10 -- src/python/role_play/`
Expected: Only new files appear:
- `src/python/role_play/voice/handler_v2_spike.py`
- `src/python/role_play/voice/voice_config_v2.py`

- [ ] **Step 3: Check import health**

Run: `python -c "from role_play.voice.handler_v2_spike import VoiceHandlerV2, classify_adk_event, VoiceSessionState, EventClassification; print('imports OK')"`
Expected: `imports OK`

- [ ] **Step 4: Final commit (if any fixups needed)**

```bash
git add src/python/role_play/voice/handler_v2_spike.py src/python/role_play/voice/voice_config_v2.py test/python/unit/voice/test_handler_v2_spike.py test/python/unit/voice/test_voice_config_v2.py
git commit -m "chore(voice): final v2 spike verification pass"
```
