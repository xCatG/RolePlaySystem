# GEMINI.md

This document provides guidance for Gemini Code when working with this RolePlay System repository.

## Quick Start Commands

```bash
# Backend
python3 -m venv venv && source venv/bin/activate  # Setup
pip install -r src/python/requirements.txt
python src/python/run_server.py                    # Run server
make test                                          # Run tests with coverage

# Frontend
cd src/ts/role_play/ui && npm install && npm run dev

# Testing Options
make test-chat          # Chat module tests only
make test-coverage-html # Generate HTML coverage report
make test-specific TEST_PATH="test/python/unit/chat/test_chat_logger.py"
```

**Environment**: `ENV=dev|beta|prod`, configs in `config/{env}.yaml`
**Required**: `JWT_SECRET_KEY`, `STORAGE_PATH`
**Key Files**: `/API.md`, `/DEPLOYMENT.md`, `/ENVIRONMENTS.md`
**Resources**: `/src/python/role_play/resources/scenarios.json`, `/scenarios_zh-TW.json`

## Architecture Summary

### Storage Configuration (Dev Environment)
- **Flexible Storage**: Dev supports file (default), GCS, or S3 via `STORAGE_TYPE` env var
- **Quick Switch**: `STORAGE_TYPE=gcs GCS_BUCKET=my-bucket python run_server.py`
- **Lock Strategies**: file (local), object (cloud atomic), redis (distributed)
- **See**: `/STORAGE_CONFIG.md` for detailed setup instructions

### Core Design Principles
1. **Layered Architecture**: App layer (chat/evaluator/scripter) → Base layer (server/common), no circular dependencies
2. **Stateless Handlers**: New instance per request/connection for scaling
3. **Dependency Injection**: FastAPI `Depends()` with factory functions
4. **Config-Based Registration**: Dynamic handler loading from YAML
5. **JWT Auth**: Multi-provider (local/OAuth), role-based (Admin/User), WebSocket token in first message
6. **WebSocket**: Audio streaming via Gemini Live API proxy

### Storage & Locking
- **Abstraction**: `StorageBackend` ABC → FileStorage (dev) → GCS/S3 (prod)
- **Key Format**: `users/{user_id}/profile` (no .json), opaque strings
- **Distributed Locking**: 
  - Strategies: file (dev), object (GCS), redis (prod)
  - Lease duration (60-300s) vs timeout (5-30s)
  - Async I/O via `asyncio.to_thread()`

### Environment & Data Models
- **Multi-Env**: dev/beta/prod configs with feature flags
- **Data Models**: Keep in feature packages unless shared

### Chat System (ADK)
- **Separation**: ADK runtime state | ChatLogger JSONL persistence
- **Services**: Singleton ContentLoader/ChatLogger/InMemorySessionService
- **Storage**: `users/{user_id}/chat_logs/{session_id}` JSONL
- **Runners**: Created per-message, not persisted
- **Language Support**: User preferred language drives content selection and agent instructions

### Frontend (Modular Monolith)
- **Structure**: Single module with domain boundaries (auth/, chat/, evaluation/)
- **Evolution**: Domain-based organization → mechanical module splitting when needed
- **Internationalization**: Vue i18n with English/Traditional Chinese support, language switcher with confirmation

### Production Locking
- **Critical**: Lease duration (60-300s crash recovery) ≠ acquisition timeout (5-30s retry)
- **Features**: Async I/O, stale lock recovery, cross-backend consistency

### Testing
- **Structure**: `/test/python/` → unit/ | integration/ | e2e/ | fixtures/
- **Coverage**: >90% unit, critical integration, user journey e2e, language functionality
- **Stack**: pytest, httpx, pytest-asyncio, factory-boy
- **Language Tests**: ContentLoader language filtering, auth language preferences, model validation
- **Makefile Targets**: `make test`, `make test-chat`, `make test-unit`, `make test-integration`, `make test-coverage-html`

## Python Implementation Guidelines

### Handler Architecture

#### Stateless Design
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

### Dependency Injection

#### Singleton Services
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

#### Factory Functions
Pure functions that create new instances:

```python
def get_storage() -> StorageBackend:
    """Factory - creates new storage instance per request"""
    storage_path = os.environ.get("STORAGE_PATH", "./storage")
    config = StorageConfig(type="file", path=storage_path)
    return FileStorage(config)
```

### Async Operations

#### Use asyncio.to_thread for Blocking I/O
```python
async def read_file(self, path: str) -> str:
    """Wrap blocking I/O in asyncio.to_thread for FastAPI"""
    return await asyncio.to_thread(self._blocking_read, path)

def _blocking_read(self, path: str) -> str:
    """Actual blocking I/O operation"""
    with open(path, 'r') as f:
        return f.read()
```

### Storage Patterns

#### Key Conventions
- **No file extensions**: `users/123/profile` not `users/123.json`
- **User data prefix**: `users/{user_id}/...`
- **Opaque strings**: Keys work identically across FileStorage/GCS/S3

#### Distributed Locking
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

### Chat System Implementation

#### Session Lifecycle
1. **Create**: ChatLogger creates JSONL, ADK stores metadata with user's preferred language
2. **Message**: Log → Create Runner with language context → Process → Log response → Discard Runner
3. **End**: Log session_end, remove from ADK memory
4. **Export**: Read JSONL directly, format as text

#### File Locking for JSONL
```python
# ChatLogger uses FileLock for concurrent access
with FileLock(f"{log_path}.lock", timeout=5):
    with open(log_path, 'a') as f:
        f.write(json.dumps(event) + '\n')
```

#### ADK Integration
- **Per-message Runners**: Create new Runner for each message
- **No persistent state**: Runners immediately discarded after use
- **Separation of concerns**: ADK for runtime, ChatLogger for persistence
- **Language Context**: Agent system prompts include language instructions

### Authentication Patterns

#### RoleChecker Dependency (Preferred)
```python
# Modern pattern using Depends()
@router.get("/admin/users")
async def list_users(
    user: User = Depends(RoleChecker(min_role=UserRole.ADMIN))
):
    return {"users": []}
```

#### Role Hierarchy
```python
ADMIN > SCRIPTER > USER > GUEST
```

### Evaluation System Implementation

#### Report Storage Pattern
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

#### Evaluation Handler Patterns
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

#### API Design for Report Retrieval
- **GET /session/{id}/report**: Returns latest or 404 (check existing first)
- **POST /session/{id}/evaluate**: Always creates new (explicit re-evaluation)
- **GET /session/{id}/all_reports**: Historical reports list
- **GET /reports/{report_id}**: Specific report by ID

#### Evaluation Error Handling
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

#### Callback Implementation Patterns
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

### Common Pitfalls

1. **Global State**: Never use global variables, use dependency injection
2. **Blocking I/O**: Always wrap in `asyncio.to_thread()` for FastAPI
3. **File Extensions in Keys**: Storage keys should be extension-free
4. **Persistent Runners**: ADK Runners must be created per-message
5. **Handler State**: Handlers must remain stateless
6. **Report Storage**: Always include timestamps in report paths for uniqueness
7. **Session Validation**: Always validate session ownership before operations
8. **Storage Failures**: Handle transient storage errors with retry logic

### Performance Considerations

- **Singleton Services**: Use `@lru_cache` for expensive initializations
- **Concurrent JSONL**: Use FileLock with 5-second timeout
- **Lock Tuning**: Lease duration (60-300s) vs acquisition timeout (5-30s)
- **Async Everything**: All I/O operations should be async

### Language Support Implementation

#### ContentLoader Language Architecture
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

#### User Language Preferences
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

#### Chat Handler Language Context
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

#### Language Validation Patterns
```python
# ContentLoader language validation
def _validate_languages(self, data: Dict) -> None:
    for scenario in data.get("scenarios", []):
        scenario_lang = scenario.get("language", "en")
        if scenario_lang not in self.supported_languages:
            raise ValueError(f"Unsupported language '{scenario_lang}'")
```

## TypeScript/Frontend Implementation Guidelines

### Directory Rules
ONLY create TypeScript source code files under this directory.

### Architecture Overview

#### Current Structure
- **Domain-Based Organization**: Separated by feature (auth/, chat/, evaluation/)
- **Composable Patterns**: Reusable Vue composables for common workflows
- **Type Safety**: Full TypeScript with backend Pydantic model sync

#### Domain Organization
```
src/ts/role_play/
├── types/          # TypeScript interfaces
├── services/       # API clients
├── composables/    # Reusable Vue logic
├── components/     # UI components by domain
└── views/          # Page-level components
```

### Type Synchronization

#### Backend Pydantic → Frontend TypeScript
Always keep types in sync with Python models:

```python
# Python (Pydantic)
class User(BaseModel):
    id: str
    email: str
    role: UserRole
    preferred_language: str = "en"
    created_at: datetime
```

```typescript
// TypeScript
interface User {
  id: string;
  email: string;
  role: UserRole;
  preferred_language: string;
  createdAt: string;  // ISO 8601 UTC
}
```

#### API Response Types
```typescript
interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: number;
}
```

### Composable Patterns

#### Reusable Vue Composables
```typescript
// composables/useAsyncOperation.ts
export function useAsyncOperation<T>() {
  const loading = ref(false);
  const error = ref<string | null>(null);
  
  const execute = async (operation: () => Promise<T>): Promise<T | null> => {
    loading.value = true;
    error.value = null;
    try {
      return await operation();
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error';
      return null;
    } finally {
      loading.value = false;
    }
  };
  
  return { loading: readonly(loading), error: readonly(error), execute };
}

// composables/useConfirmModal.ts
export function useConfirmModal() {
  const showModal = ref(false);
  const modalConfig = ref<ConfirmModalConfig>({});
  
  const confirm = (config: ConfirmModalConfig): Promise<boolean> => {
    return new Promise((resolve) => {
      modalConfig.value = { ...config, onConfirm: () => resolve(true), onCancel: () => resolve(false) };
      showModal.value = true;
    });
  };
  
  return { showModal, modalConfig, confirm };
}
```

### State Management

#### Store Pattern
```typescript
// stores/auth.ts
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    token: null as string | null,
  }),
  
  actions: {
    async login(credentials: LoginRequest) {
      const response = await authApi.login(credentials);
      this.token = response.token;
      this.user = response.user;
    }
  }
});
```

### API Integration

#### Service Layer
```typescript
// services/auth-api.ts
class AuthApi {
  private baseUrl = '/api/auth';
  
  async login(data: LoginRequest): Promise<LoginResponse> {
    const response = await fetch(`${this.baseUrl}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
    
    return response.json();
  }
}

export const authApi = new AuthApi();
```

#### Token Management
```typescript
// Automatic token injection
fetch(url, {
  headers: {
    'Authorization': `Bearer ${authStore.token}`,
    'Content-Type': 'application/json'
  }
});
```

### Component Guidelines

#### Domain Components
```typescript
// components/chat/MessageList.vue
<template>
  <div class="message-list">
    <Message v-for="msg in messages" :key="msg.id" :message="msg" />
  </div>
</template>

<script setup lang="ts">
import { Message } from '../types/chat';
import Message from './Message.vue';

defineProps<{
  messages: Message[]
}>();
</script>
```

#### Cross-Domain Integration
```typescript
// When chat needs to show user info
import { useAuthStore } from '@/stores/auth';
import { useChatStore } from '@/stores/chat';

const authStore = useAuthStore();
const chatStore = useChatStore();

// Access current user from auth domain
const currentUser = computed(() => authStore.user);
```

### Development Patterns

#### Environment Variables
```typescript
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
```

#### Error Handling
```typescript
try {
  await chatApi.sendMessage(sessionId, message);
} catch (error) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      // Handle auth error
      await authStore.logout();
    }
  }
}
```

#### WebSocket Integration (Future)
```typescript
// services/chat-websocket.ts
class ChatWebSocket {
  private ws: WebSocket | null = null;
  
  connect(sessionId: string, token: string) {
    this.ws = new WebSocket(`ws://localhost:8000/ws/chat/${sessionId}`);
    
    // Send auth token as first message
    this.ws.onopen = () => {
      this.ws?.send(JSON.stringify({ type: 'auth', token }));
    };
  }
}
```

### Build & Development

#### Vite Configuration
```javascript
// vite.config.js
export default {
  server: {
    host: '0.0.0.0',  // For container support
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
}
```

#### Type Checking
```bash
npm run type-check  # Run TypeScript compiler without emit
```

### Internationalization (i18n)

#### Vue i18n Setup
```typescript
// main.ts
import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'

const i18n = createI18n({
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en, 'zh-TW': zhTW }
})
```

#### Language Management
```typescript
// Language preference sync with backend
async function updateLanguagePreference(language: string) {
  // Update Vue i18n locale
  i18n.global.locale.value = language
  
  // Persist to localStorage
  localStorage.setItem('language', language)
  
  // Sync with backend if authenticated
  if (authStore.token) {
    await authApi.updateLanguagePreference(authStore.token, { language })
    authStore.user.preferred_language = language
  }
}
```

#### Component Localization
```vue
<template>
  <div>
    <h1>{{ $t('nav.title') }}</h1>
    <p>{{ $t('chat.welcomeMessage') }}</p>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t, locale } = useI18n()
</script>
```

#### Language-Specific API Types
```typescript
// Language preference API types
interface UpdateLanguageRequest {
  language: string;  // IETF BCP 47 format: "en", "zh-TW"
}

interface UpdateLanguageResponse {
  success: boolean;
  language: string;
  message: string;
}

// Content API with language support
interface GetScenariosParams {
  language?: string;  // Filter scenarios by language
}
```

### Evaluation System Integration

#### Evaluation API Types
```typescript
// Core evaluation types
interface StoredEvaluationReport {
  success: boolean;
  report_id: string;
  chat_session_id: string;
  created_at: string;
  evaluation_type: string;
  report: FinalReviewReport;
}

interface EvaluationReportSummary {
  report_id: string;
  chat_session_id: string;
  created_at: string;
  evaluation_type: string;
}

interface EvaluationReportListResponse {
  success: boolean;
  reports: EvaluationReportSummary[];
}
```

#### Evaluation Service Implementation
```typescript
// services/evaluationApi.ts
export const evaluationApi = {
  // Check for existing report first
  async getLatestReport(sessionId: string): Promise<StoredEvaluationReport | null> {
    try {
      const response = await fetch(`/api/eval/session/${sessionId}/report`, {
        headers: { 'Authorization': `Bearer ${authStore.token}` }
      });
      if (response.status === 404) return null;
      if (!response.ok) throw new Error('Failed to fetch report');
      return await response.json();
    } catch (error) {
      throw error;
    }
  },

  // Always creates new evaluation
  async createNewEvaluation(sessionId: string, evaluationType = 'comprehensive'): Promise<EvaluationResponse> {
    const response = await fetch(`/api/eval/session/${sessionId}/evaluate?evaluation_type=${evaluationType}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authStore.token}` }
    });
    if (!response.ok) throw new Error('Failed to create evaluation');
    return await response.json();
  },

  // List all historical reports
  async listAllReports(sessionId: string): Promise<EvaluationReportListResponse> {
    const response = await fetch(`/api/eval/session/${sessionId}/all_reports`, {
      headers: { 'Authorization': `Bearer ${authStore.token}` }
    });
    if (!response.ok) throw new Error('Failed to list reports');
    return await response.json();
  }
};
```

#### Smart Report Loading Pattern
```typescript
// Using composables for evaluation workflow
const { loading: evaluationLoading, execute } = useAsyncOperation();
const { confirm } = useConfirmModal();

const sendToEvaluation = async () => {
  showEvaluationReport.value = true;
  
  const result = await execute(async () => {
    // First check for existing report
    const existingReport = await evaluationApi.getLatestReport(session.session_id);
    
    if (existingReport) {
      evaluationReport.value = existingReport.report;
      isExistingReport.value = true;
      return existingReport;
    } else {
      // Generate new report only if none exists
      const newReport = await evaluationApi.createNewEvaluation(session.session_id);
      evaluationReport.value = newReport.report;
      isExistingReport.value = false;
      return newReport;
    }
  });
  
  if (!result) {
    showEvaluationReport.value = false; // Hide on error
  }
};
```

#### Re-evaluation UI Pattern
```vue
<!-- EvaluationReport.vue -->
<template>
  <div class="evaluation-report">
    <div v-if="isExistingReport" class="report-actions">
      <button @click="handleReevaluate" 
              :disabled="loading" 
              class="primary-button">
        {{ $t('evaluation.reevaluate') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const { loading, execute } = useAsyncOperation();
const { confirm } = useConfirmModal();

const handleReevaluate = async () => {
  const confirmed = await confirm({
    title: t('evaluation.confirmReevaluate'),
    message: t('evaluation.reevaluateWarning')
  });
  
  if (confirmed) {
    await execute(() => evaluationApi.createNewEvaluation(sessionId));
  }
};
</script>
```

## Testing Guidelines

### Test Organization
```
test/
└── python/
    ├── unit/          # Fast isolated tests
    │   ├── common/    # Models, storage, auth
    │   ├── server/    # Base handlers, decorators
    │   ├── chat/      # Chat-specific logic
    │   ├── auth/      # Auth module
    │   ├── scripter/  # Scripter module
    │   └── evaluator/ # Evaluator module
    ├── integration/   # Module interactions
    │   ├── storage/   # Backend integration
    │   ├── auth/      # OAuth flows
    │   └── handlers/  # Registration & DI
    ├── e2e/          # Full API tests
    │   ├── api/      # HTTP workflows
    │   └── websocket/# WebSocket tests
    └── fixtures/     # Shared test data
```

### Naming Conventions
- Unit tests: `test_<module_name>.py`
- Integration/E2E: `test_<feature>_flow.py`
- Test functions: `test_<what>_<condition>_<expected_result>`

### Coverage Targets
- **Unit Tests**: >90% coverage for core modules
- **Integration**: Critical paths (auth flows, storage backends)
- **E2E**: User journeys (registration → login → chat → evaluation)

### Test Stack
- **pytest**: Test runner with async support
- **httpx**: Async HTTP client for API tests
- **pytest-asyncio**: Async test support
- **factory-boy**: Test data generation
- **pytest-mock**: Mocking framework

### Performance Testing
```python
@pytest.mark.slow
def test_large_dataset_handling():
    """Mark slow tests to skip during rapid development"""
    pass
```

### Storage Testing
When testing storage backends:
- Use temporary directories for FileStorage
- Mock cloud storage clients (GCS, S3)
- Test both success and failure paths
- Verify lock behavior with concurrent operations

### Fixtures Best Practices
```python
# conftest.py
@pytest.fixture
async def auth_manager(tmp_path):
    """Create isolated auth manager for each test"""
    storage = FileStorage(config)
    return AuthManager(storage)

# Use fixtures for common test data
@pytest.fixture
def valid_user_data():
    return {"email": "test@example.com", "password": "secure123"}
```

### Current Test Status
- **FileStorage**: 92% coverage (production ready)
- **Auth/Models**: 80%+ coverage
- **Cloud Storage**: 0% (stubs only, validated via integration tests)
- **Evaluation**: 73% coverage (18 comprehensive tests)
- **Total**: 260+ tests, 54% overall coverage

### Evaluation Testing Patterns

#### Mock Storage for Handler Tests
```python
@pytest.fixture
def mock_storage():
    """Create mock storage backend for evaluation tests."""
    storage = AsyncMock()
    storage.write = AsyncMock()
    storage.read = AsyncMock() 
    storage.list_keys = AsyncMock()
    return storage
```

#### UUID Mocking for Predictable Tests
```python
# Mock UUID generation for consistent test results
with patch('role_play.evaluation.handler.uuid.uuid4') as mock_uuid:
    mock_uuid.return_value = Mock(__str__=lambda self: "abcd1234")
```

#### Evaluation Test Coverage
- **Handler Tests**: Session evaluation flow, error handling, cleanup
- **Endpoint Tests**: Report retrieval, listing, creation
- **Storage Tests**: Report persistence, retrieval by ID
- **Error Scenarios**: Missing reports, storage failures, malformed data

### Running Tests
```bash
# All tests
pytest

# Run with make targets
make test                                 # Full suite with coverage
make test-no-coverage                     # Fast execution
make test-unit                            # Unit tests only
make test-evaluation                      # Evaluation module only

# Specific test execution
make test-specific TEST_PATH=test/python/unit/evaluation/

# Generate HTML coverage report
make test-coverage-html
```

### Language Support Testing

#### Test Coverage
- **ContentLoader**: Language filtering, fallback logic, caching
- **Auth**: Language preference API, user model updates
- **Models**: Validation of language codes (IETF BCP 47)
- **Chat Handler**: Language context in agent prompts
- **Frontend**: Language switcher, i18n message rendering

#### Test Patterns
```python
# Test language filtering in ContentLoader
def test_content_loader_language_filter():
    loader = ContentLoader(supported_languages=["en", "zh-TW"])
    scenarios = loader.get_scenarios("zh-TW")
    assert all(s.language == "zh-TW" for s in scenarios)

# Test language preference API
async def test_update_language_preference(client, authenticated_user):
    response = await client.patch(
        "/api/auth/language",
        json={"language": "zh-TW"},
        headers={"Authorization": f"Bearer {authenticated_user['token']}"}
    )
    assert response.status_code == 200
    assert response.json()["language"] == "zh-TW"
```

### Frontend Testing (Future)
- **Vitest**: Unit testing for components and composables
- **Cypress**: E2E testing for user flows
- **Storybook**: Component isolation and visual regression testing
