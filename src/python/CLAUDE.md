# Python Implementation Guidelines

## Handler Architecture

### Stateless Design
- **New instance per request**: Handlers instantiated via dependency injection
- **No instance variables**: Never store state in handler attributes
- **Request lifecycle**: HTTP handler lives for one request, WebSocket for connection duration

```python
# GOOD - Stateless handler
class ChatHandler(BaseHandler):
    def __init__(self, auth_manager: AuthManager, chat_logger: ChatLogger):
        self.auth_manager = auth_manager  # Injected dependencies only
        self.chat_logger = chat_logger

# BAD - Stateful handler
class ChatHandler(BaseHandler):
    def __init__(self):
        self.sessions = {}  # NEVER do this!
```

## Dependency Injection

### Singleton Services
Use `@lru_cache` for services that should be shared across requests:

```python
# dependencies.py
from functools import lru_cache

@lru_cache
def get_content_loader() -> ContentLoader:
    """Singleton content loader - loads once, reused across requests"""
    return ContentLoader()

@lru_cache
def get_chat_logger(storage: StorageBackend = Depends(get_storage)) -> ChatLogger:
    """Singleton chat logger with injected storage"""
    return ChatLogger(storage)
```

### Factory Functions
Pure functions that create new instances:

```python
def get_storage() -> StorageBackend:
    """Factory - creates new storage instance per request"""
    storage_path = os.environ.get("STORAGE_PATH", "./storage")
    config = StorageConfig(type="file", path=storage_path)
    return FileStorage(config)
```

## Async Operations

### Use asyncio.to_thread for Blocking I/O
```python
async def read_file(self, path: str) -> str:
    """Wrap blocking I/O in asyncio.to_thread for FastAPI"""
    return await asyncio.to_thread(self._blocking_read, path)

def _blocking_read(self, path: str) -> str:
    """Actual blocking I/O operation"""
    with open(path, 'r') as f:
        return f.read()
```

## Storage Patterns

### Key Conventions
- **No file extensions**: `users/123/profile` not `users/123.json`
- **User data prefix**: `users/{user_id}/...`
- **Opaque strings**: Keys work identically across FileStorage/GCS/S3

### Distributed Locking
```python
# Separate lease duration from acquisition timeout
lock_config = LockConfig(
    strategy="file",
    lease_duration_seconds=300,  # Lock valid for 5 min if holder crashes
    timeout=30                   # Try acquiring for 30 seconds
)

async with storage.lock("resource", timeout=30):
    # Critical section
    pass
```

## Chat System Implementation

### Session Lifecycle
1. **Create**: ChatLogger creates JSONL, ADK stores metadata with user's preferred language
2. **Message**: Log → Create Runner with language context → Process → Log response → Discard Runner
3. **End**: Log session_end, remove from ADK memory
4. **Export**: Read JSONL directly, format as text

### File Locking for JSONL
```python
# ChatLogger uses FileLock for concurrent access
with FileLock(f"{log_path}.lock", timeout=5):
    with open(log_path, 'a') as f:
        f.write(json.dumps(event) + '\n')
```

### ADK Integration
- **Per-message Runners**: Create new Runner for each message
- **No persistent state**: Runners immediately discarded after use
- **Separation of concerns**: ADK for runtime, ChatLogger for persistence
- **Language Context**: Agent system prompts include language instructions

## Authentication Patterns

### RoleChecker Dependency (Preferred)
```python
# Modern pattern using Depends()
@router.get("/admin/users")
async def list_users(
    user: User = Depends(RoleChecker(min_role=UserRole.ADMIN))
):
    return {"users": []}
```

### Role Hierarchy
```python
ADMIN > SCRIPTER > USER > GUEST
```

## Evaluation System Implementation

### Report Storage Pattern
```python
# Store evaluation reports with timestamp-based unique IDs
timestamp = utc_now_isoformat()
# Replace colons with underscores for filesystem compatibility
safe_timestamp = timestamp.replace(':', '_')
unique_id = str(uuid.uuid4())[:8]
storage_id = f"{safe_timestamp}_{unique_id}"
report_path = f"users/{user_id}/eval_reports/{session_id}/{storage_id}"

# Report includes metadata and full evaluation
report_data = {
    "eval_session_id": eval_session_id,
    "chat_session_id": session_id,
    "user_id": user_id,
    "created_at": timestamp,
    "evaluation_type": "comprehensive",
    "report": final_review_report.model_dump()
}
```

### Evaluation Handler Patterns
```python
# Helper methods for report management
async def _get_latest_report(user_id, session_id, storage):
    """Get most recent report by sorting keys"""
    prefix = f"users/{user_id}/eval_reports/{session_id}/"
    keys = await storage.list_keys(prefix)
    if not keys:
        return None
    latest_key = sorted(keys, reverse=True)[0]
    return json.loads(await storage.read(latest_key))

# Storage injection in handler methods
async def evaluate_session(
    self,
    request: EvaluationRequest,
    current_user: User = Depends(require_user_or_higher),
    storage: StorageBackend = Depends(get_storage_backend)
):
    # Store report after generation
    await storage.write(report_path, json.dumps(report_data))
```

### API Design for Report Retrieval
- **GET /session/{id}/report**: Returns latest or 404 (check existing first)
- **POST /session/{id}/evaluate**: Always creates new (explicit re-evaluation)
- **GET /session/{id}/all_reports**: Historical reports list
- **GET /reports/{report_id}**: Specific report by ID

### Evaluation Error Handling
```python
# Session ownership validation
async def _validate_session_ownership(user_id: str, session_id: str, chat_logger: ChatLogger):
    """Validate that session belongs to user before evaluation."""
    sessions = await chat_logger.list_user_sessions(user_id)
    session_ids = {s["session_id"] for s in sessions}
    if session_id not in session_ids:
        raise HTTPException(status_code=403, detail="Session access denied")

# Storage error handling with retry
async def _store_report_with_retry(storage: StorageBackend, path: str, data: str, max_retries: int = 3):
    """Store evaluation report with retry logic for transient failures."""
    for attempt in range(max_retries):
        try:
            await storage.write(path, data)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise HTTPException(status_code=500, detail="Failed to store evaluation report")
            logger.warning(f"Storage attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

### Callback Implementation Patterns
```python
# TODO completion pattern for agents
def agent_callback(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
    """Post-process agent responses to complete TODOs and aggregate data."""
    if not llm_response.content or not llm_response.content.parts:
        return None
    
    try:
        # Parse structured output
        response_data = json.loads(llm_response.content.parts[0].text)
        
        # Complete missing fields from callback state
        if "area_assessments" not in response_data or not response_data["area_assessments"]:
            response_data["area_assessments"] = _extract_assessments_from_state(callback_context.state)
        
        # Calculate derived fields (e.g., overall_score)
        response_data["overall_score"] = _calculate_overall_score(response_data["area_assessments"])
        
        # Return modified response
        modified_parts = [copy.deepcopy(part) for part in llm_response.content.parts]
        modified_parts[0].text = json.dumps(response_data)
        return LlmResponse(content=types.Content(role="model", parts=modified_parts))
        
    except Exception as e:
        logger.error(f"Callback processing failed: {e}")
        return None  # Return original response on error
```

## Common Pitfalls

1. **Global State**: Never use global variables, use dependency injection
2. **Blocking I/O**: Always wrap in `asyncio.to_thread()` for FastAPI
3. **File Extensions in Keys**: Storage keys should be extension-free
4. **Persistent Runners**: ADK Runners must be created per-message
5. **Handler State**: Handlers must remain stateless
6. **Report Storage**: Always include timestamps in report paths for uniqueness
7. **Session Validation**: Always validate session ownership before operations
8. **Storage Failures**: Handle transient storage errors with retry logic

## Performance Considerations

- **Singleton Services**: Use `@lru_cache` for expensive initializations
- **Concurrent JSONL**: Use FileLock with 5-second timeout
- **Lock Tuning**: Lease duration (60-300s) vs acquisition timeout (5-30s)
- **Async Everything**: All I/O operations should be async

## Storage Monitoring

### StorageMonitor Integration
```python
# Storage backends automatically use global StorageMonitor
from role_play.common.storage_monitoring import get_storage_monitor

# Monitor tracks operations automatically
async with storage.read("key") as data:
    # Read operation is monitored
    pass

async with storage.lock("resource") as lock:
    # Lock acquisition/hold times tracked
    pass
```

### Monitoring Metrics
- **Lock Metrics**: Acquisition attempts, successes, failures, timing
- **Storage Metrics**: Read/write/delete operations, error rates, latencies
- **Decision Support**: Automatic recommendations for lock strategy upgrades

### Usage in Scripts
```python
# Validation and metadata scripts use asyncio patterns
class ResourceValidator:
    def __init__(self, resource_dir: Path, storage_monitor: Optional[StorageMonitor] = None):
        self.monitor = storage_monitor or get_storage_monitor()
    
    async def validate_all(self):
        # Async validation with monitoring
        async with self.monitor.monitor_storage_operation("read"):
            data = await self._load_resource(path)
```

## Language Support Implementation

### ContentLoader Language Architecture
```python
# Language-aware content loading
loader = ContentLoader(supported_languages=["en", "zh-TW", "ja"])

# Per-language caching
en_scenarios = loader.get_scenarios("en")
zh_scenarios = loader.get_scenarios("zh-TW")

# Language-specific resource files
# scenarios.json (English default)
# scenarios_zh-TW.json (Traditional Chinese)
```

### User Language Preferences
```python
# User model with language preference
class User(BaseModel):
    preferred_language: str = "en"  # IETF BCP 47 format
    
# Language preference API
@router.patch("/auth/language")
async def update_language_preference(
    request: UpdateLanguageRequest,
    current_user: User = Depends(get_current_user)
):
    # Update user language preference
    pass
```

### Chat Handler Language Context
```python
# Session creation with user language
async def create_session(request: CreateSessionRequest, current_user: User):
    user_language = current_user.preferred_language
    
    # Load content in user's language
    scenario = content_loader.get_scenario_by_id(request.scenario_id, user_language)
    character = content_loader.get_character_by_id(request.character_id, user_language)
    
    # Agent with language-specific instructions
    system_prompt = f"""
    **IMPORTANT: Respond in {language_name} language as specified.**
    {character.system_prompt}
    """
```

### Language Validation Patterns
```python
# ContentLoader language validation
def _validate_languages(self, data: Dict) -> None:
    for scenario in data.get("scenarios", []):
        scenario_lang = scenario.get("language", "en")
        if scenario_lang not in self.supported_languages:
            raise ValueError(f"Unsupported language '{scenario_lang}'")
```

## Testing Patterns

### Mock Storage for Evaluation Tests
```python
@pytest.fixture
def mock_storage():
    """Create mock storage backend for evaluation tests."""
    storage = AsyncMock()
    storage.write = AsyncMock()
    storage.read = AsyncMock()
    storage.list_keys = AsyncMock()
    return storage

# Inject into test methods
async def test_evaluate_session(mock_storage):
    response = await handler.evaluate_session(
        request=request,
        current_user=user,
        storage=mock_storage
    )
```