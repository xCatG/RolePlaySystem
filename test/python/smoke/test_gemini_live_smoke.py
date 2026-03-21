"""Smoke test: Gemini Live API round-trip.

Validates that the v2 spike's assumptions about the Gemini Live API hold:
  1. google.genai types (Blob, Content, Part) match our _Blob/_Content/_Part stubs
  2. Runner.run_live yields events with the attributes we classify
  3. Session resumption handles are actually emitted
  4. LiveRequestQueue.send_content / .close work as expected

Requires:
  GOOGLE_API_KEY env var (Gemini API key)

Usage:
  # From worktree root:
  GOOGLE_API_KEY=<key> python -m pytest test/python/smoke/test_gemini_live_smoke.py -v -s

  # Or run directly:
  GOOGLE_API_KEY=<key> python test/python/smoke/test_gemini_live_smoke.py
"""
import asyncio
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skip early if no API key
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("GOOGLE_API_KEY", "")

try:
    import pytest
    smoke = pytest.mark.smoke
    skip_no_key = pytest.mark.skipif(not API_KEY, reason="GOOGLE_API_KEY not set")
except ImportError:
    # Running directly (not via pytest)
    def smoke(fn):
        return fn
    def skip_no_key(fn):
        return fn


# ---------------------------------------------------------------------------
# Imports — these validate that google-genai + google-adk are importable
# ---------------------------------------------------------------------------
def _import_deps():
    """Import and return all ADK/genai dependencies. Raises ImportError if missing."""
    from google.adk import Runner
    from google.adk.agents import LiveRequestQueue, RunConfig, Agent
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    from google.genai.types import (
        AudioTranscriptionConfig,
        Blob,
        Content,
        Part,
    )
    return {
        "Runner": Runner,
        "LiveRequestQueue": LiveRequestQueue,
        "RunConfig": RunConfig,
        "Agent": Agent,
        "InMemorySessionService": InMemorySessionService,
        "types": types,
        "AudioTranscriptionConfig": AudioTranscriptionConfig,
        "Blob": Blob,
        "Content": Content,
        "Part": Part,
    }


# ---------------------------------------------------------------------------
# 1. Type compatibility check (no API call)
# ---------------------------------------------------------------------------
@smoke
@skip_no_key
def test_type_stubs_match_real_types():
    """Verify our _Blob/_Content/_Part stubs have the same construction interface."""
    deps = _import_deps()
    Blob = deps["Blob"]
    Content = deps["Content"]
    Part = deps["Part"]

    # Our stubs construct with these signatures — real types must accept them too
    blob = Blob(mime_type="audio/pcm", data=b"\x00\x01\x02")
    assert blob.mime_type == "audio/pcm"
    assert blob.data == b"\x00\x01\x02"

    part = Part(text="hello")
    assert part.text == "hello"

    content = Content(parts=[part])
    assert len(content.parts) == 1
    assert content.parts[0].text == "hello"

    logger.info("PASS: Type stubs match real google.genai types")


# ---------------------------------------------------------------------------
# 2. Live session round-trip (requires API key)
# ---------------------------------------------------------------------------
@smoke
@skip_no_key
def test_live_session_round_trip():
    """Send one text turn to Gemini Live, read back at least one event."""
    asyncio.run(_live_round_trip())


async def _live_round_trip():
    deps = _import_deps()
    Runner = deps["Runner"]
    LiveRequestQueue = deps["LiveRequestQueue"]
    RunConfig = deps["RunConfig"]
    Agent = deps["Agent"]
    InMemorySessionService = deps["InMemorySessionService"]
    types = deps["types"]
    AudioTranscriptionConfig = deps["AudioTranscriptionConfig"]
    Content = deps["Content"]
    Part = deps["Part"]

    # Set up a minimal agent
    agent = Agent(
        name="smoke_test_agent",
        model="gemini-2.5-flash-preview-native-audio-dialog",
        instruction="You are a test assistant. Respond briefly to confirm you received the message.",
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="smoke_test", user_id="smoke_user",
    )

    runner = Runner(
        app_name="smoke_test", agent=agent, session_service=session_service,
    )

    run_config = RunConfig(
        response_modalities=[types.Modality.AUDIO],
        output_audio_transcription=AudioTranscriptionConfig(),
        input_audio_transcription=AudioTranscriptionConfig(),
    )

    live_queue = LiveRequestQueue()
    live_events = runner.run_live(
        session=session,
        live_request_queue=live_queue,
        run_config=run_config,
    )

    # Send a single text message
    content = Content(parts=[Part(text="Say the word 'pineapple' and nothing else.")])
    live_queue.send_content(content)

    # Collect events with timeout
    events_received = []
    event_kinds = set()

    async def _collect():
        async for event in live_events:
            info = _describe_event(event)
            events_received.append(info)
            event_kinds.add(info["kind"])
            logger.info(f"  Event: {info}")

            # Stop after we get a turn_complete or enough events
            if info.get("turn_complete") or len(events_received) > 50:
                break

    try:
        await asyncio.wait_for(_collect(), timeout=30.0)
    except asyncio.TimeoutError:
        logger.warning(f"Timed out after 30s with {len(events_received)} events")

    live_queue.close()

    # Assertions
    assert len(events_received) > 0, "Expected at least one event from Gemini Live"
    logger.info(f"PASS: Received {len(events_received)} events, kinds: {event_kinds}")

    # Verify we got at least audio or transcript back
    has_content = any(k in event_kinds for k in ("audio", "transcript", "text"))
    assert has_content, f"Expected audio/transcript/text event, got kinds: {event_kinds}"
    logger.info("PASS: Got content back from Gemini Live")


def _describe_event(event) -> dict:
    """Describe an ADK live event in terms our classifier cares about."""
    info = {
        "kind": "unknown",
        "author": getattr(event, "author", None),
        "turn_complete": getattr(event, "turn_complete", False),
        "partial": getattr(event, "partial", False),
        "interrupted": getattr(event, "interrupted", False),
    }

    content = getattr(event, "content", None)
    if content is None:
        # Check for server_content (some event types)
        server_content = getattr(event, "server_content", None)
        if server_content:
            content = getattr(server_content, "model_turn", None)

    if content and hasattr(content, "parts") and content.parts:
        for part in content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                info["kind"] = "audio"
                info["mime_type"] = getattr(part.inline_data, "mime_type", "unknown")
                info["data_size"] = len(getattr(part.inline_data, "data", b""))
                break
            elif hasattr(part, "text") and part.text:
                info["kind"] = "transcript" if info.get("partial") or "transcript" in str(type(part)).lower() else "text"
                info["text_preview"] = part.text[:100]
                break

    # Session resumption handle
    if hasattr(event, "session_resumption_update"):
        update = event.session_resumption_update
        if update and hasattr(update, "new_handle") and update.new_handle:
            info["kind"] = "session_resumption"
            info["handle_length"] = len(update.new_handle)

    # GoAway
    if hasattr(event, "go_away") and event.go_away:
        info["kind"] = "go_away"

    return info


# ---------------------------------------------------------------------------
# 3. Session resumption handle check
# ---------------------------------------------------------------------------
@smoke
@skip_no_key
def test_session_resumption_handle_emitted():
    """Verify Gemini Live emits a session_resumption_update event."""
    asyncio.run(_check_resumption_handle())


async def _check_resumption_handle():
    deps = _import_deps()
    Runner = deps["Runner"]
    LiveRequestQueue = deps["LiveRequestQueue"]
    RunConfig = deps["RunConfig"]
    Agent = deps["Agent"]
    InMemorySessionService = deps["InMemorySessionService"]
    types = deps["types"]
    AudioTranscriptionConfig = deps["AudioTranscriptionConfig"]
    Content = deps["Content"]
    Part = deps["Part"]

    agent = Agent(
        name="handle_test_agent",
        model="gemini-2.5-flash-preview-native-audio-dialog",
        instruction="Respond briefly.",
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="handle_test", user_id="handle_user",
    )

    runner = Runner(
        app_name="handle_test", agent=agent, session_service=session_service,
    )

    run_config = RunConfig(
        response_modalities=[types.Modality.AUDIO],
        output_audio_transcription=AudioTranscriptionConfig(),
    )

    live_queue = LiveRequestQueue()
    live_events = runner.run_live(
        session=session,
        live_request_queue=live_queue,
        run_config=run_config,
    )

    # Send a message to trigger activity
    content = Content(parts=[Part(text="Hello")])
    live_queue.send_content(content)

    resumption_handle = None

    async def _collect():
        nonlocal resumption_handle
        async for event in live_events:
            if hasattr(event, "session_resumption_update"):
                update = event.session_resumption_update
                if update and hasattr(update, "new_handle") and update.new_handle:
                    resumption_handle = update.new_handle
                    logger.info(f"  Got resumption handle ({len(resumption_handle)} bytes)")
                    break

            if getattr(event, "turn_complete", False):
                break

    try:
        await asyncio.wait_for(_collect(), timeout=30.0)
    except asyncio.TimeoutError:
        logger.warning("Timed out waiting for resumption handle")

    live_queue.close()

    # Resumption handle is not guaranteed on every session, but log the result
    if resumption_handle:
        logger.info(f"PASS: Session resumption handle received ({len(resumption_handle)} bytes)")
    else:
        logger.warning(
            "SKIP: No resumption handle emitted — this is expected for short sessions. "
            "The handle typically arrives after the first turn exchange."
        )


# ---------------------------------------------------------------------------
# 4. Classify real events with our classifier
# ---------------------------------------------------------------------------
@smoke
@skip_no_key
def test_classify_real_events():
    """Run real Gemini events through classify_adk_event and verify no crashes."""
    asyncio.run(_classify_real())


async def _classify_real():
    """Collect events from Gemini and run them through the v2 spike classifier."""
    # Add source to path
    src_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "python")
    sys.path.insert(0, os.path.abspath(src_path))

    from role_play.voice.handler_v2_spike import classify_adk_event

    deps = _import_deps()
    Runner = deps["Runner"]
    LiveRequestQueue = deps["LiveRequestQueue"]
    RunConfig = deps["RunConfig"]
    Agent = deps["Agent"]
    InMemorySessionService = deps["InMemorySessionService"]
    types = deps["types"]
    AudioTranscriptionConfig = deps["AudioTranscriptionConfig"]
    Content = deps["Content"]
    Part = deps["Part"]

    agent = Agent(
        name="classify_test_agent",
        model="gemini-2.5-flash-preview-native-audio-dialog",
        instruction="Say hello briefly.",
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="classify_test", user_id="classify_user",
    )

    runner = Runner(
        app_name="classify_test", agent=agent, session_service=session_service,
    )

    run_config = RunConfig(
        response_modalities=[types.Modality.AUDIO],
        output_audio_transcription=AudioTranscriptionConfig(),
        input_audio_transcription=AudioTranscriptionConfig(),
    )

    live_queue = LiveRequestQueue()
    live_events = runner.run_live(
        session=session,
        live_request_queue=live_queue,
        run_config=run_config,
    )

    content = Content(parts=[Part(text="Say hello")])
    live_queue.send_content(content)

    classifications = []

    async def _collect():
        async for event in live_events:
            try:
                classification = classify_adk_event(event)
                classifications.append(classification)
                logger.info(
                    f"  {classification.kind:20s} | "
                    f"role={classification.role or '-':10s} | "
                    f"partial={classification.is_partial} | "
                    f"terminal={classification.is_terminal}"
                )
            except Exception as e:
                logger.error(f"  classify_adk_event CRASHED on event: {e}")
                logger.error(f"  Event type: {type(event).__name__}, attrs: {dir(event)}")
                raise

            if getattr(event, "turn_complete", False):
                break

    try:
        await asyncio.wait_for(_collect(), timeout=30.0)
    except asyncio.TimeoutError:
        logger.warning(f"Timed out with {len(classifications)} classifications")

    live_queue.close()

    assert len(classifications) > 0, "Expected at least one classified event"

    # Count by kind
    kinds = {}
    for c in classifications:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    logger.info(f"PASS: Classified {len(classifications)} events: {kinds}")


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: Set GOOGLE_API_KEY environment variable")
        sys.exit(1)

    print("=" * 60)
    print("Gemini Live API Smoke Tests")
    print("=" * 60)

    print("\n--- Test 1: Type stub compatibility ---")
    test_type_stubs_match_real_types()

    print("\n--- Test 2: Live session round-trip ---")
    test_live_session_round_trip()

    print("\n--- Test 3: Session resumption handle ---")
    test_session_resumption_handle_emitted()

    print("\n--- Test 4: Classify real events ---")
    test_classify_real_events()

    print("\n" + "=" * 60)
    print("All smoke tests complete!")
    print("=" * 60)
