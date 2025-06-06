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

## TODO List

### Deployment Tasks (Beta Environment)
- [x] Update base_server.py to serve Vue.js frontend static files
- [x] Add health check endpoint (/health) to base_server.py
- [x] Create Dockerfile with multi-stage build (Vue.js + FastAPI)
- [x] Create/update Makefile with deployment targets
- [x] Add structured JSON logging for Cloud Logging
- [x] Create .env.mk template for GCP project IDs
- [x] Add run-local-docker target to Makefile
- [x] Update frontend to use /api prefix for all API calls
- [x] Set up GCP infrastructure for beta (buckets, service accounts, secrets)
- [x] Deploy to Cloud Run beta environment
- [x] Test beta deployment end-to-end

### Deployment & Configuration Improvements
- [ ] Fix GCS bucket naming inconsistency (DEPLOYMENT.md uses `rps-app-data-{env}` but configs use `roleplay-{env}-storage`)
- [ ] Update API version path - remove `/api/v1/*` reference or implement versioning consistently
- [ ] Create environment-specific service accounts (`sa-rps-beta`, `sa-rps-prod`) instead of generic `sa-rps`
- [ ] Reduce GCS permissions from `objectAdmin` to least privilege (`objectUser` or separate creator/viewer roles)
- [ ] Make GCP region configurable in Makefile (currently hardcoded to us-west1)
- [ ] Document git version tagging strategy in DEPLOYMENT.md
- [ ] Add `make list-config` output example to deployment docs
- [ ] Explicitly state JWT secret name (`rps-jwt-secret`) in manual deploy examples

### Custom Domain Setup (Completed for Beta)
- [x] Configure CNAME records in DNS provider (cPanel)
  - Beta: `beta.rps.cattail-sw.com` → `rps-api-beta-493431680508.us-west1.run.app`
  - Prod: `rps.cattail-sw.com` → `rps-api-prod-xxxxx.us-west1.run.app`
- [x] Configure Cloud Run domain mapping for SSL certificates
- [x] Update CORS settings in Makefile to use custom domains

### Future Deployment Tasks
- [ ] CI/CD: Cloud Build pipeline (main → beta, tags → prod)
- [ ] Database migrations: Alembic setup when adding database
- [ ] Monitoring: Cloud Monitoring dashboards and alerts
- [ ] Tracing: OpenTelemetry + Cloud Trace integration

### Language Support Features (Completed)
- [x] Traditional Chinese (zh-TW) full localization system
- [x] Vue i18n frontend integration with English/Chinese translations  
- [x] Custom ConfirmModal component for consistent UX
- [x] Language switcher with user preference persistence
- [x] Backend language preference API (`PATCH /auth/language`)
- [x] Language-aware content loading (scenarios_zh-TW.json)
- [x] ContentLoader language filtering and caching
- [x] User model enhanced with preferred_language field
- [x] Comprehensive test coverage for language functionality
- [x] Frontend-backend language preference sync

### Pending Development
- [ ] WebSocket: `server/websocket.py` connection manager
- [ ] Auth Module: Complete OAuth implementation
- [ ] Scripter: Complete module implementation  
- [ ] Frontend: Modular monolith restructure, chat/eval interfaces
- [ ] Testing: integration/handlers/, e2e/api/
- [ ] Cleanup: Remove deprecated auth_decorators.py and imports
- [ ] Docs: README.md architecture, OAUTH_SETUP.md
- [ ] User Management: Complete module
- [ ] Database: Future schema design
- [ ] Additional Languages: Japanese (ja) content and UI translations

### Completed
- [x] Base Infrastructure: All common modules, cloud storage, distributed locking
- [x] Server Core: Base classes, dependencies, config, user accounts
- [x] Chat Module: ADK integration, JSONL logging, POC features
- [x] Evaluation: Simple export implementation
- [x] Config & Env: All YAML configs, env loading
- [x] Testing: Unit tests, storage integration, test infrastructure
- [x] Core Docs: API.md, DEPLOYMENT.md, ENVIRONMENTS.md
- [x] Traditional Chinese Localization: Complete frontend/backend language support system

## Implementation Phases
1. Core Infrastructure → 2. Authentication → 3. Handlers → 4. WebSocket/Audio → 5. Polish

## Key Implementation Status

### Completed Systems
- **Infrastructure**: Common modules, FileStorage, AuthManager, JWT, cloud storage with distributed locking
- **Server**: FastAPI with stateless handlers, JWT auth, CORS, environment configs
- **Auth**: RoleChecker pattern (replaced decorators), role hierarchy, proper HTTP codes, language preferences
- **Chat**: ADK integration, JSONL logging, singleton services, POC endpoints, language-aware content
- **Evaluation**: Simple text export from JSONL
- **Testing**: 190+ tests, language functionality coverage (ContentLoader, auth, models)
- **Frontend**: Vue.js auth UI, i18n with Traditional Chinese, language switcher
- **Localization**: Complete Traditional Chinese support with content isolation

### Architecture Highlights
- **Storage**: Async distributed locking, lease (60-300s) vs timeout (5-30s) separation
- **Chat**: Separated ADK runtime from JSONL persistence, per-message Runner creation
- **Config**: YAML + env vars, dynamic handler loading, fail-fast validation
- **Cloud**: GCS (async atomic ops), S3/Redis (stubs), env restrictions
- **Language Architecture**: Per-language content files, fallback filtering, UI/backend sync, caching

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

**Language Support**:
- Use IETF BCP 47 format: `"en"`, `"zh-TW"`, `"ja"`
- User `preferred_language` drives content selection and agent instructions
- ContentLoader filters by language, caches per-language
- Frontend Vue i18n syncs with backend user preferences
- Language-specific content files: `scenarios_zh-TW.json` 
