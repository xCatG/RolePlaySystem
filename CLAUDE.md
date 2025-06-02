# CLAUDE.md

Guidance for Claude Code when working with this RolePlay System repository.

## Quick Start Commands

```bash
# Backend
python3 -m venv venv && source venv/bin/activate  # Setup
pip install -r src/python/requirements.txt
python src/python/run_server.py                    # Run server
pytest test/python/                                # Run tests

# Frontend
cd src/ts/role_play/ui && npm install && npm run dev
```

**Environment**: `ENV=dev|beta|prod`, configs in `config/{env}.yaml`
**Required**: `JWT_SECRET_KEY`, `STORAGE_PATH`
**Key Files**: `/API.md`, `/DEPLOYMENT.md`, `/ENVIRONMENTS.md`, `/data/scenarios.json`

## Architecture Summary

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

### Frontend (Modular Monolith)
- **Structure**: Single module with domain boundaries (auth/, chat/, evaluation/)
- **Evolution**: Domain-based organization → mechanical module splitting when needed

### Production Locking
- **Critical**: Lease duration (60-300s crash recovery) ≠ acquisition timeout (5-30s retry)
- **Features**: Async I/O, stale lock recovery, cross-backend consistency

### Testing
- **Structure**: `/test/python/` → unit/ | integration/ | e2e/ | fixtures/
- **Coverage**: >90% unit, critical integration, user journey e2e
- **Stack**: pytest, httpx, pytest-asyncio, factory-boy

## TODO List

### Pending
- [ ] WebSocket: `server/websocket.py` connection manager
- [ ] Auth Module: handler.py, models.py, oauth_client.py
- [ ] Scripter: Complete module implementation
- [ ] Frontend: Modular monolith restructure, chat/eval interfaces
- [ ] Testing: integration/handlers/, e2e/api/
- [ ] Cleanup: Remove deprecated auth_decorators.py and imports
- [ ] Docs: README.md architecture, OAUTH_SETUP.md
- [ ] User Management: Complete module
- [ ] Database: Future schema design

### Completed
- [x] Base Infrastructure: All common modules, cloud storage, distributed locking
- [x] Server Core: Base classes, dependencies, config, user accounts
- [x] Chat Module: ADK integration, JSONL logging, POC features
- [x] Evaluation: Simple export implementation
- [x] Config & Env: All YAML configs, env loading
- [x] Testing: Unit tests, storage integration, test infrastructure
- [x] Core Docs: API.md, DEPLOYMENT.md, ENVIRONMENTS.md

## Implementation Phases
1. Core Infrastructure → 2. Authentication → 3. Handlers → 4. WebSocket/Audio → 5. Polish

## Key Implementation Status

### Completed Systems
- **Infrastructure**: Common modules, FileStorage, AuthManager, JWT, cloud storage with distributed locking
- **Server**: FastAPI with stateless handlers, JWT auth, CORS, environment configs
- **Auth**: RoleChecker pattern (replaced decorators), role hierarchy, proper HTTP codes
- **Chat**: ADK integration, JSONL logging, singleton services, POC endpoints
- **Evaluation**: Simple text export from JSONL
- **Testing**: 150+ tests, 30% coverage (92% FileStorage, 0% cloud stubs)
- **Frontend**: Vue.js auth UI, basic chat structure

### Architecture Highlights
- **Storage**: Async distributed locking, lease (60-300s) vs timeout (5-30s) separation
- **Chat**: Separated ADK runtime from JSONL persistence, per-message Runner creation
- **Config**: YAML + env vars, dynamic handler loading, fail-fast validation
- **Cloud**: GCS (async atomic ops), S3/Redis (stubs), env restrictions

## Critical Guidelines

**General**:
- Do exactly what's asked - no more, no less
- Never create files unless necessary - edit existing
- No proactive documentation files (*.md)
- Clean up temp files
- Sync TypeScript types with Pydantic models

**Datetime (UTC Only)**:
- Use: `datetime.now(timezone.utc)`
- Persist: ISO 8601 UTC strings
- Exception: `datetime.utcnow().isoformat()` when immediately saving
- Client converts UTC → local for display only 
