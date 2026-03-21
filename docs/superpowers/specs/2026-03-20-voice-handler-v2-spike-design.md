# Voice Handler V2 Spike — Design Spec

**Date:** 2026-03-20
**Status:** Approved
**Output file:** `src/python/role_play/voice/handler_v2_spike.py`

---

## 1. Purpose

Prototype a voice handler for 45-minute behavioral interviews that addresses all gaps identified in `docs/voice_handler_gap_report.md`. The spike validates feasibility of session resumption, wall clock enforcement, and Live API event handling before production investment.

## 2. Non-Negotiables

These constraints are fixed and not subject to design trade-offs:

- Use existing `StorageBackend` interface — no new abstract methods
- Use `google.genai` types (not `google.generativeai`)
- All new async methods must be `async def`
- Output goes to `handler_v2_spike.py` — do not modify existing files
- Inject `StorageBackend` at construction time, do not call `get_storage_backend()` in loops

### 2.1 Registration & Route Path

The spike is **not registered via the standard `server.register_handler()` path**. It lives in the same package as v1 but is imported and tested directly (unit tests, manual WebSocket testing). It uses the route prefix `/voice-v2` to avoid conflicts with v1's `/voice` prefix. Production integration into the handler registration system is post-spike work.

## 3. Architecture

### 3.1 Class Shape & Construction

`VoiceHandlerV2` extends `BaseHandler`. Storage is injected at construction, not fetched per-call.

```python
class VoiceHandlerV2(BaseHandler):
    def __init__(self, storage: StorageBackend):
        super().__init__()
        self._storage = storage
```

The v1 untyped `adk: Dict[str, Any]` is replaced by a dataclass:

```python
@dataclass
class VoiceSessionState:
    session_id: str
    user_id: str
    runner: Runner
    live_events: AsyncGenerator
    live_request_queue: LiveRequestQueue
    adk_session: Any
    stop_event: asyncio.Event          # replaces adk["active"] boolean
    termination_reason: Optional[str]  # set by _handle_termination
    started_at: datetime               # datetime object, not ISO string
    session_timeout: int               # per-session, from query param or default
    warning_seconds: int               # per-session, from query param or default
    chat_logger: ChatLogger             # injected alongside storage
    transcript_buffer: List[Dict]       # accumulated transcripts for evaluation
    stats: Dict[str, int]               # numeric counters only (audio_chunks_sent, etc.)
```

`chat_logger` is obtained once via `get_chat_logger(self._storage)` in `handle_voice_session` and passed into the state, not fetched per-call.

`transcript_buffer` accumulates all transcript entries (both partial and final, with role and timestamp) during the session. `_send_to_client` appends to it when routing transcript events. `_cleanup_session` can access it for evaluation data. Initialized as an empty list.

`stats` contains only numeric counters (`audio_chunks_sent`, `audio_chunks_received`, `text_chunks_sent`, `transcripts_processed`, `errors`). Non-numeric session data like `termination_reason` lives on dedicated `VoiceSessionState` fields.

Key changes from v1:
- `stop_event` (`asyncio.Event`) replaces the `active` boolean — any coroutine can set it, any coroutine can `await` it
- `started_at` is a `datetime` object for elapsed-time arithmetic
- `termination_reason` is captured before cleanup for the `session_ended` message
- `session_timeout` and `warning_seconds` are per-session configurable
- Storage lives on `self._storage`, not fetched per-call

### 3.2 Event Classification

v1's `_process_adk_event` (sync) did classification AND built frontend messages. v2 splits responsibilities:

- `_classify_adk_event(event) -> EventClassification` — sync, pure classification, no side effects
- `_send_to_client` — async, routes based on classification

```python
@dataclass
class EventClassification:
    kind: str                          # "audio", "transcript", "turn_status",
                                       # "session_resumption", "go_away", "unknown"
    data: Any                          # parsed payload
    role: Optional[str] = None         # "user" or "assistant" for transcripts
    is_partial: bool = False           # partial vs final transcript
    is_terminal: bool = False          # AI sentinel detected
    terminal_reason: Optional[str] = None  # AI_CONCLUDED or AI_EARLY_TERMINATION
```

### 3.3 ADK Event Detection Strategy

The ADK Live API event shape is not fully documented. Detection uses a **discovery-first approach**: log all event attributes for unrecognized events, and use best-effort attribute checks for known types.

**Detection heuristics for `_classify_adk_event`:**

| Kind | Detection logic |
|---|---|
| `audio` | `event.content.parts[*].inline_data` is not None (existing v1 logic) |
| `transcript` | `event.content.parts[*].text` is not None (existing v1 logic) |
| `turn_status` | `hasattr(event, "turn_complete")` or `hasattr(event, "interrupted")` (existing v1 logic) |
| `session_resumption` | Check `hasattr(event, "session_resumption_update")` or `type(event).__name__` contains `SessionResumption`. **If neither works, the spike logs the raw event and classifies as `unknown`.** |
| `go_away` | Check `hasattr(event, "go_away")` or `type(event).__name__` contains `GoAway`. **Same fallback to `unknown` with logging.** |
| `unknown` | Catch-all. Log `type(event).__name__` and all attributes at DEBUG level for discovery. |

**Important:** The `session_resumption` and `go_away` detection is explicitly best-effort. If the ADK sends these events in a shape we don't anticipate, they land in `unknown` with full attribute logging. The spike's purpose is to discover the actual event shapes. The routing table (Section 5) handles `unknown` safely (log only, no frontend delivery).

The resumption handle itself is expected to be a string token (based on ADK documentation references). If it turns out to be bytes or a complex object, serialize to JSON string via `json.dumps()` before `storage.write()`. Log the actual type on first encounter.

## 4. Coroutine Structure & Task Racing

`_handle_streaming` races four coroutines with a shared `asyncio.Event` (stop signal). The key improvement over v1: `asyncio.wait(FIRST_COMPLETED)` still drives the orchestrator, but individual coroutines use `stop_event` to coordinate graceful wind-down. In v1, the first task to complete caused immediate cancellation of its sibling — notably, `_receive_from_client` going quiet killed `_send_to_client`. In v2, only `_handle_termination` (or the orchestrator's fallback) sets the stop event, so silence on one side doesn't kill the other.

```
_handle_streaming (orchestrator)
  ├── _receive_from_client   — reads WebSocket input, forwards to ADK
  ├── _send_to_client        — reads ADK events, routes to frontend/storage/logs
  ├── _session_timer         — enforces wall clock, injects warning
  └── _heartbeat             — sends keepalive JSON every N seconds
```

**Lifecycle:**

1. Orchestrator creates all four tasks, then `asyncio.wait(FIRST_COMPLETED)`
2. When a task completes, orchestrator checks `stop_event`
3. If set: cancel remaining tasks, proceed to cleanup
4. If not set (unexpected early return): log warning, set `stop_event`, cancel remaining

**Each coroutine's exit behavior:**

| Coroutine | Normal exit trigger | Calls `_handle_termination`? |
|---|---|---|
| `_receive_from_client` | `end_session=True` or `WebSocketDisconnect` | Yes — `USER_ENDED` or `DISCONNECTED` |
| `_send_to_client` | Detects AI sentinel or `stop_event` | Yes — `AI_CONCLUDED` or `AI_EARLY_TERMINATION` |
| `_session_timer` | Clock hits T=0 | Yes — `TIME_LIMIT` |
| `_heartbeat` | `stop_event` is set | No — just exits |
| `_heartbeat` | `ConnectionError` on send | Yes — `DISCONNECTED` (before re-raising) |

**Heartbeat disconnection:** If `_heartbeat` catches a `ConnectionError` when sending, it calls `_handle_termination(state, "DISCONNECTED")` before re-raising the exception. This ensures `termination_reason` is set correctly rather than relying on the orchestrator's fallback path (which would set `stop_event` but not the reason).

**Key difference from v1:** `_receive_from_client` ending due to silence does NOT kill `_send_to_client`. The receive coroutine only terminates the session on explicit `end_session` or disconnect.

## 5. Event Routing

Routing table in `_send_to_client`, based on `EventClassification.kind`:

| `kind` | Sent to frontend? | Backend action |
|---|---|---|
| `audio` | Yes (base64 JSON) | Update stats |
| `transcript` | **No** (REQ-7) | Log to `chat_logger`, accumulate in buffer |
| `turn_status` | Yes | Update stats; log turn_complete correlation for AI termination analysis |
| `session_resumption` | No | `await self._storage.write(handle_key, handle)` |
| `go_away` | No (REQ-3) | Log at WARNING level |
| `unknown` | No | Log at DEBUG for spike discovery |

### 5.1 AI Termination Detection (Hybrid)

**Primary — sentinel text scanning:**
`_classify_adk_event` checks transcript text for `[RPS_SESSION_COMPLETE]` or `[RPS_END_EARLY:reason]`. If found:
- `is_terminal = True`
- `terminal_reason` = `AI_CONCLUDED` or `AI_EARLY_TERMINATION`
- Sentinel is stripped from `data` before storage

**Secondary — turn_complete correlation:**
When `turn_status` has `turn_complete=True`, log it with the last transcript buffer entry for post-hoc analysis. For the spike, only the sentinel triggers actual termination. Turn-complete correlation is logged for future heuristic development.

`AI_EARLY_TERMINATION` events log extra context (last N transcript lines, agent state) to support future human review pipeline.

## 6. Session Timer & 5-Minute Warning

### 6.1 Timer Coroutine

Two phases: sleep until warning time, fire warning, sleep until termination.

```python
async def _session_timer(self, state: VoiceSessionState):
    elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
    warning_at = state.session_timeout - state.warning_seconds

    # Phase 1: wait until warning (interruptible via stop_event)
    try:
        await asyncio.wait_for(
            state.stop_event.wait(),
            timeout=max(0, warning_at - elapsed)
        )
        return  # stop_event was set, session ended before warning
    except asyncio.TimeoutError:
        pass  # timer reached warning point

    await self._inject_time_warning(state)

    # Phase 2: wait until termination (interruptible via stop_event)
    try:
        await asyncio.wait_for(
            state.stop_event.wait(),
            timeout=state.warning_seconds
        )
        return  # stop_event was set during warning period
    except asyncio.TimeoutError:
        pass  # timer reached termination point

    await self._handle_termination(state, "TIME_LIMIT")
```

This uses the same `wait_for(stop_event.wait(), timeout=...)` pattern as `_heartbeat` (Section 9), ensuring the timer responds immediately to session termination rather than sleeping through it. If the orchestrator cancels the task, `CancelledError` propagates naturally from `wait_for`.

### 6.2 Warning Injection (Dual Approach)

`_inject_time_warning` fires both approaches to test which the Live API responds to:

1. **State update (likely won't work, here for discovery):** `state.adk_session.state["time_warning"] = True` — ADK session state mutation via direct dict access may not propagate to the live agent mid-session. The runner likely only reads state at turn boundaries, not mid-stream. Included to confirm this hypothesis; content injection is the real approach.
2. **Content injection (primary):** `state.live_request_queue.send_content(Content(parts=[Part(text="[SYSTEM] 5 minutes remaining. Begin wrapping up the interview.")]))`

Both fire. Each is wrapped in try/except — failures are logged as valuable spike data, not propagated to the timer coroutine. Spike logging will reveal which (or both) triggers observable agent behavior.

### 6.3 Configuration

**VoiceConfig defaults:**

```python
DEFAULT_SESSION_TIMEOUT_SECONDS = 2700   # 45 min
DEFAULT_SESSION_WARNING_SECONDS = 300    # 5 min
MIN_SESSION_WARNING_SECONDS = 10         # floor
HEARTBEAT_INTERVAL_SECONDS = 30          # keepalive
```

**Per-session override via WebSocket query params** (for testing):

```
/voice-v2/ws/{session_id}?token=xxx&timeout=60&warning=10
```

Production will eventually pull values from session metadata or session-type config.

### 6.4 Reconnection Timer Continuity

On reconnect, `started_at` is read from persisted session metadata, not reset. The wall clock is absolute from original session start.

## 7. Termination & Cleanup

### 7.1 `_handle_termination(state, reason, detail=None)`

Single convergence point for all exit paths:

1. **Guard:** Check-and-set `stop_event` atomically (no `await` between check and set). Since all coroutines run on a single event loop, `if not stop_event.is_set(): stop_event.set()` is safe — there are no await points between the check and set to create a race. If `stop_event` is already set, return immediately.
2. Set `state.termination_reason = reason`
3. (stop_event already set in step 1)
4. Send frontend message, guarded by try/except `ConnectionError`/`WebSocketDisconnect` (for `DISCONNECTED` the socket is already dead, so the send silently fails): `{"type": "session_ended", "reason": reason, "detail": detail, "timestamp": "..."}`
5. Close `live_request_queue` — **unless** reason is `DISCONNECTED` (keep alive for resume)
6. Log termination with full context

### 7.2 Five Termination Reasons

| Reason | Close queue? | Resumable? | Notes |
|---|---|---|---|
| `USER_ENDED` | Yes | No | Client sent `end_session` |
| `TIME_LIMIT` | Yes | No | Wall clock expired |
| `AI_CONCLUDED` | Yes | No | Agent signaled interview complete |
| `AI_EARLY_TERMINATION` | Yes | No | Agent ended early; log extra context for future human review |
| `DISCONNECTED` | No | Yes | WebSocket died; resumption handle in storage |

### 7.3 Cleanup (`_cleanup_session`)

Called from `finally` block after `_handle_streaming` completes:

1. Cancel any remaining tasks
2. Compute final stats (duration, chunk counts, termination reason)
3. `await chat_logger.log_voice_session_end(user_id, session_id, voice_stats=stats)`
4. If `DISCONNECTED`: persist `started_at` alongside resumption handle for timer continuity

## 8. Session Resumption

### 8.1 Handle Storage (REQ-1, REQ-4)

Storage key: `users/{user_id}/voice_sessions/{session_id}/gemini_handle` (single overwrite for spike; production will version).

Session metadata key: `users/{user_id}/voice_sessions/{session_id}/session_meta` (JSON with `started_at`, `session_timeout`, `warning_seconds`).

Handle writes happen in `_send_to_client` when `EventClassification.kind == "session_resumption"`.

**Initial metadata write:** `session_meta` is written at the end of `_initialize_adk` (not only on `DISCONNECTED` cleanup) to ensure timer continuity from session start. This way, if a disconnect occurs before any `session_resumption` event arrives, the reconnection path still has a valid `started_at` and timeout config.

### 8.2 Reconnection Path in `_initialize_adk`

```python
handle_key = f"users/{user_id}/voice_sessions/{session_id}/gemini_handle"
meta_key = f"users/{user_id}/voice_sessions/{session_id}/session_meta"

existing_handle = None
if await self._storage.exists(handle_key):
    existing_handle = await self._storage.read(handle_key)

session_meta = None
if await self._storage.exists(meta_key):
    session_meta = json.loads(await self._storage.read(meta_key))
```

If Gemini rejects a stale handle, fall back to a fresh session and log the failure. `started_at` from `session_meta` is still used so the wall clock doesn't reset.

### 8.3 Context Window Compression (REQ-2)

Set unconditionally on every `RunConfig`, not just reconnections.

**Verify at implementation time:** The exact type name and `RunConfig` field for context window compression must be confirmed against the installed `google-adk` and `google-genai` package versions. The ADK documentation references `ContextWindowCompressionConfig` on `RunConfig`, but the actual import path and parameter names may differ. The implementer should:

1. Check `google.adk.agents.RunConfig` for a `context_window_compression` field
2. Check `google.genai.types` for a `ContextWindowCompressionConfig` class
3. If neither exists, check for `SlidingWindowConfig`, `ContextCompressionConfig`, or similar
4. If no compression config exists in the current SDK version, log a WARNING and skip — the spike should still run without it. A 45-minute session during testing won't hit the context limit, so the spike remains valid

**Expected usage (pending verification):**

```python
context_window_compression=ContextWindowCompressionConfig(
    trigger_tokens=CONTEXT_WINDOW_TRIGGER_TOKENS,  # 100_000
    strategy="sliding_window",
)
```

**VoiceConfig constants:**

```python
CONTEXT_WINDOW_TRIGGER_TOKENS = 100_000
CONTEXT_WINDOW_STRATEGY = "sliding_window"
```

## 9. Keepalive

A fourth coroutine sends application-level heartbeat JSON:

```python
async def _heartbeat(self, websocket, state):
    while not state.stop_event.is_set():
        try:
            await asyncio.wait_for(
                state.stop_event.wait(),
                timeout=HEARTBEAT_INTERVAL_SECONDS
            )
            break  # stop_event was set
        except asyncio.TimeoutError:
            pass  # interval elapsed, send heartbeat
        try:
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": utc_now_isoformat()
            })
        except (ConnectionError, WebSocketDisconnect):
            await self._handle_termination(state, "DISCONNECTED")
            raise
```

## 10. Method Inventory

All methods in `VoiceHandlerV2`, grouped by region:

### Session Lifecycle
| Method | Async? | Purpose |
|---|---|---|
| `handle_voice_session` | Yes | Entry point, auth, setup, finally cleanup |
| `_initialize_adk` | Yes | Create agent, runner, handle reconnection |
| `_cleanup_session` | Yes | Stats, logging, persisting disconnect state |

### Streaming
| Method | Async? | Purpose |
|---|---|---|
| `_handle_streaming` | Yes | Orchestrate four coroutines |
| `_receive_from_client` | Yes | WebSocket → ADK input |
| `_send_to_client` | Yes | ADK events → frontend/storage/logs |
| `_heartbeat` | Yes | Periodic keepalive |
| `_session_timer` | Yes | Wall clock enforcement |

### Event Processing
| Method | Async? | Purpose |
|---|---|---|
| `_classify_adk_event` | No | Pure event classification |
| `_inject_time_warning` | Yes | Dual warning approach |

### Termination
| Method | Async? | Purpose |
|---|---|---|
| `_handle_termination` | Yes | Single convergence point for all exits |

### Auth (unchanged from v1)
| Method | Async? | Purpose |
|---|---|---|
| `_validate_jwt_token` | Yes | JWT verification |
| `_check_session_limit` | No | Placeholder, returns True |

## 11. Gap Report Coverage

| Gap | Section | Resolution |
|---|---|---|
| REQ-1: Session resumption | 8.1, 8.2 | Handle persisted on every update, read on reconnect |
| REQ-2: Context compression | 8.3 | Always-on in RunConfig |
| REQ-3: GoAway handling | 5 | Classify → log at WARNING, suppress frontend |
| REQ-4: Handle persistence | 8.1 | Write in `_send_to_client` routing |
| REQ-5: Termination reasons | 7.1, 7.2 | Five reasons (expanded from gap report's four to add `DISCONNECTED`), single `_handle_termination()` |
| REQ-6: Wall clock timer | 6 | Per-session configurable, dual warning |
| REQ-7: Transcript suppression | 5 | Routing table skips frontend for transcripts |
| O-1: No reconnection | 8.2 | Resumption handle + session meta |
| O-2: FIRST_COMPLETED kills sibling | 4 | Four-task racing with stop_event |
| O-3: No keepalive | 9 | Heartbeat coroutine |
| O-4: Storage not threaded | 3.1 | `self._storage` injected at construction; streaming methods access it via `self._storage` |
| O-5: Sync process method | 3.2 | Split into sync classifier + async router |
| O-6: started_at is string | 3.1 | `datetime` object in `VoiceSessionState` |
| O-7: Timeout never enforced | 6.1 | Timer coroutine enforces it |

## 12. Out of Scope (Post-Spike)

- Human review pipeline for `AI_EARLY_TERMINATION` events
- Versioned handle storage (production upgrade from single-key)
- Protocol-level WebSocket ping/pong (server config)
- Per-session-type timeout configuration (session metadata)
- `_check_session_limit` real implementation
- Frontend changes (frontend only sees `session_ended` + `heartbeat` as new message types)
- Ticket-based auth replacing JWT in query params
