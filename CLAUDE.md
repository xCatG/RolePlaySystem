# CLAUDE.md

Guidance for Claude Code when working with this RolePlay System repository.

## Quick Start Commands

```bash
# Backend
python3 -m venv venv && source venv/bin/activate  # Setup
pip install -r src/python/requirements.txt
make dev-setup                                     # Set up dev environment & copy resources
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
**Resources**: `/data/resources/` containing versioned JSON files with metadata

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
- **Agent Configuration**: Centralized ADK agent creation via `get_production_agent()` in roleplay_agent module

### Frontend (Modular Monolith)
- **Structure**: Single module with domain boundaries (auth/, chat/, evaluation/)
- **Evolution**: Domain-based organization → mechanical module splitting when needed
- **Internationalization**: Vue i18n with English/Traditional Chinese support, language switcher with confirmation
- **Session Creation**: Dual-flow UI supporting both script-based and character-based (freeform) session creation

### Production Locking
- **Critical**: Lease duration (60-300s crash recovery) ≠ acquisition timeout (5-30s retry)
- **Features**: Async I/O, stale lock recovery, cross-backend consistency

### Testing
- **Structure**: `/test/python/` → unit/ | integration/ | e2e/ | fixtures/
- **Coverage**: >90% unit, critical integration, user journey e2e, language functionality
- **Stack**: pytest, httpx, pytest-asyncio, factory-boy
- **Language Tests**: ContentLoader language filtering, auth language preferences, model validation
- **Makefile Targets**: `make test`, `make test-chat`, `make test-unit`, `make test-integration`, `make test-coverage-html`

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

### Evaluation Module Enhancement (Completed)
- [x] **EvaluationHandler.evaluate_session() Cleanup**: Enhanced error handling, session validation, resource management
- [x] **Comprehensive Unit Tests**: 9 test cases covering success path, error conditions, cleanup scenarios (71% coverage)
- [x] **Code Organization**: Added region comments, improved exception handling, proper resource cleanup
- [x] **Testing Integration**: Added `/test/python/unit/evaluation/` structure following existing patterns

### Evaluation Report Storage (Completed)
- [x] **Backend Storage**: Reports stored at `users/{user_id}/eval_reports/{chat_session_id}/{timestamp}_{unique_id}` (timestamps use underscores instead of colons for filesystem compatibility)
- [x] **Smart Loading**: Frontend checks for existing reports before generating new ones
- [x] **Re-evaluation**: Users can trigger new evaluations via "Re-evaluate" button
- [x] **API Endpoints**:
  - `GET /api/eval/session/{session_id}/report` - Get latest report or 404
  - `POST /api/eval/session/{session_id}/evaluate` - Always create new evaluation
  - `GET /api/eval/session/{session_id}/all_reports` - List all reports for session
  - `GET /api/eval/reports/{report_id}` - Get specific report by ID
- [x] **Test Coverage**: 18 comprehensive unit tests for all evaluation functionality

### Resource Versioning & Validation (Completed)
- [x] **Resource File Organization**: Separated characters and scenarios into dedicated JSON files
- [x] **Version Metadata**: All resource files now include `resource_version`, `last_modified`, and `modified_by` fields
- [x] **ResourceLoader Enhancement**: Added version validation with SUPPORTED_VERSIONS = ["1.0"]
- [x] **Comprehensive Testing**: Added 20 new unit tests achieving 100% coverage for ResourceLoader
- [x] **Validation Script**: Created `validate_resources.py` for JSON syntax, metadata, and cross-reference checking
- [x] **Metadata Update Script**: Created `update_resource_metadata.py` for manual editors to update timestamps
- [x] **Makefile Targets**: 
  - `make dev-setup` - Set up dev environment by copying resources to configured storage path
  - `make validate-resources` - Validate all resource JSON files
  - `make update-resource-metadata` - Update timestamps after manual edits
  - `make upload-resources` - Upload resources to GCS bucket
  - `make download-resources` - Download resources from GCS bucket
  - `make deploy-with-resources` - Deploy app and upload resources together
- [x] **GCS Testing**: Successfully tested resource loading from beta GCS bucket (`rps-app-data-beta`)
- [x] **Dev Setup**: Created `make dev-setup` to handle storage path configuration (resolves ~/data/rps_dev vs ./data issue)
- [x] **Storage Monitoring Integration**: Integrated StorageMonitor into storage backends for I/O and lock operation metrics
- [x] **Script Refactoring**: Refactored validation and metadata scripts to be object-oriented with asyncio support
- [x] **Resource Loading Fix**: Fixed GCS path issue in Makefile, hardened path handling with forward slashes
- [x] **Integration Testing**: Replaced test script with proper pytest integration test for resource loading

### ADK Agent Refactoring (Completed)
- [x] **Centralized Agent Configuration**: Refactored `get_production_config()` to async `get_production_agent()` in roleplay_agent module
- [x] **Chat Handler Integration**: Updated chat handler to use centralized agent creation instead of duplicating prompt logic
- [x] **Language-Aware Agents**: Agent creation respects user's preferred language for system prompts
- [x] **Test Coverage**: All 20+ chat handler unit tests passing after refactoring
- [x] **Code Deduplication**: Eliminated duplicate agent configuration logic between modules

### Script-Based Session Creation (Completed)
- [x] **Frontend UI Enhancement**: Added dual-flow session creation supporting both script and character selection
- [x] **Radio Button Pattern**: Implemented mutually exclusive selection with proper accessibility (id/for attributes)
- [x] **Adaptive UI**: Script dropdown only shown when scripts are available for selected scenario
- [x] **TypeScript Integration**: Added ScriptInfo type and updated CreateSessionRequest to support script_id
- [x] **API Integration**: Added getScripts method to chatApi service for frontend script fetching
- [x] **Internationalization**: Full English/Traditional Chinese support for new UI elements
- [x] **CSS Improvements**: Fixed radio button alignment issues with proper flexbox layout

### Pending Development
- [ ] **Resource Architecture for Script Creator**:
  - [x] Design LayeredResourceLoader for base + user resources (see RESOURCE_ARCHITECTURE.md)
  - [ ] Implement user resource directories (`users/{user_id}/resources/`)
  - [ ] Update APIs to distinguish base vs user-created content
  - [ ] Design resource sharing and visibility controls
- [ ] **Backend API Implementation**: Create script content endpoints to support frontend script selection
- [ ] **Code Quality & Testing** (Post-refactoring improvements):
  - [ ] Implement API contract testing to prevent frontend/backend data structure mismatches
  - [ ] Add runtime API response validation in development mode to catch integration issues early
  - [ ] Add caching layer for API responses to reduce redundant calls
  - [ ] Extract common error handling decorator for backend methods
  - [ ] Create utility functions for date formatting across components
  - [ ] Add validation that session belongs to requesting user before creating evaluation reports
  - [ ] Add retry logic for transient storage failures in evaluation system
- [ ] WebSocket: `server/websocket.py` connection manager
- [ ] Auth Module: Complete OAuth implementation
- [ ] Scripter: Complete module implementation  
- [ ] Frontend: Modular monolith restructure, chat/eval interfaces
- [ ] Testing: integration/handlers/, e2e/api/
- [ ] Docs: README.md architecture, OAUTH_SETUP.md
- [ ] User Management: Complete module
- [ ] Database: Future schema design
- [ ] **Localization Completeness**: Complete ChatWindow.vue localization (message placeholders, session labels, timestamps still in English)
- [ ] Additional Languages: Japanese (ja) content and UI translations

### Read-Only Session History (Completed)
- [x] Backend: Add `GET /chat/session/{session_id}/status` endpoint to check if session is active or ended
- [x] Backend: Add `GET /chat/session/{session_id}/messages` endpoint to retrieve message history from JSONL
- [x] Backend: Add `DELETE /chat/session/{session_id}` endpoint to permanently delete sessions
- [x] Backend: Update `SessionInfo` model to include `is_active`, `ended_at`, `ended_reason` fields
- [x] Backend: Block message sending to ended sessions (403 Forbidden)
- [x] Backend: ChatLogger methods for session end info and message retrieval
- [x] Frontend: Update TypeScript types for session status tracking
- [x] Frontend: Add visual distinction for ended sessions in session list (gray out, badges)
- [x] Frontend: ChatWindow read-only mode (hide input, show banner for historical sessions)
- [x] Frontend: Load and display message history when viewing ended sessions
- [x] Frontend: Scrollable sessions list with max-height container
- [x] Frontend: Session management actions (end/delete) with confirmation dialogs
- [x] UI: Add "Send to Evaluation" button next to Export button (show "Coming Soon" dialog)
- [x] UI: Session management buttons in both session list and chat window
- [x] UI: Safe deletion workflow (hide delete during active chat, show after ending)
- [x] Internationalization: Full English/Chinese support for all new features

### Testing Infrastructure (Completed)
- [x] Comprehensive test targets in Makefile for development workflow
- [x] `make test` - Full test suite with coverage reporting and 25% minimum threshold
- [x] `make test-quiet` - Quiet mode execution for faster feedback
- [x] `make test-chat` - Chat module specific testing with dedicated coverage
- [x] `make test-unit` - Unit tests only for focused testing
- [x] `make test-integration` - Integration tests for service interactions
- [x] `make test-coverage-html` - HTML coverage reports for detailed analysis
- [x] `make test-no-coverage` - Fast test execution without coverage overhead
- [x] `make test-specific TEST_PATH=<path>` - Targeted test execution for debugging

### Code Simplification & Refactoring (Completed)
- [x] **Backend Phase 1**: Extract `_parse_jsonl_file()` utility from ChatLogger (~200 lines duplicate code eliminated)
- [x] **Backend Phase 1**: Extract `_validate_active_session()` helper from handler methods
- [x] **Backend Phase 2**: Break down complex `send_message()` method (80→30 lines) into focused helpers:
  - `_log_participant_message()` - Handle participant message logging
  - `_log_character_message()` - Handle character response logging  
  - `_load_session_content()` - Load and validate character/scenario content
  - `_generate_character_response()` - ADK Runner interaction and response generation
- [x] **Frontend Phase 2**: Create reusable composables for common patterns:
  - `useConfirmModal.ts` - Centralized modal management
  - `useAsyncOperation.ts` - Standardized loading/error handling
  - `useSessionActions.ts` - Session operation workflows
  - `useChatData.ts` - Consolidated data management
- [x] **Frontend Phase 2**: Consolidate data loading patterns (7 duplicate `loadInitialData()` calls → single `refreshData()`)
- [x] **Frontend Phase 3**: Integrate composables into Chat.vue:
  - Replaced manual state management with `useChatData` composable
  - Integrated `useConfirmModal` for consistent deletion workflows
  - Applied `useAsyncOperation` for unified loading/error states
  - Reduced component complexity from ~340 to ~280 lines
- [x] **Impact**: ~300 lines duplicate code eliminated, better maintainability, all 241 tests passing
- [x] **Critical Fix**: Resolved frontend data loading issues in Phase 3 refactoring (API response handling bugs)

### Voice Chat & Audio Debugging (Completed)
- [x] **WebSocket Voice Handler**: Real-time bidirectional audio streaming with ADK integration
- [x] **PCM Audio Logging**: Environment-based audio recording for debugging (dev/beta only)
- [x] **Binary Data Fix**: Corrected PCM audio storage from `write()` to `write_bytes()` for proper binary handling
- [x] **Audio Debug Utility**: `debug_audio.py` script for reassembling and analyzing recorded PCM chunks:
  - `info <session_dir>` - Show audio session statistics and timing
  - `reassemble <session_dir>` - Combine PCM chunks into playable WAV files
  - `play <session_dir>` - Playback reassembled audio for debugging
- [x] **Audio Format Support**: 16-bit PCM, 16kHz, mono format matching Gemini Live API requirements
- [x] **Testing Infrastructure**: Comprehensive voice backend testing suite with WebSocket simulation
- [x] **Documentation**: Complete README.md with usage examples and troubleshooting guides


## Implementation Phases
1. Core Infrastructure → 2. Authentication → 3. Handlers → 4. WebSocket/Audio → 5. Polish

## Key Implementation Status

### Completed Systems
- **Infrastructure**: Common modules, FileStorage, AuthManager, JWT, cloud storage with distributed locking
- **Server**: FastAPI with stateless handlers, JWT auth, CORS, environment configs
- **Auth**: RoleChecker pattern (replaced decorators), role hierarchy, proper HTTP codes, language preferences
- **Chat**: ADK integration, JSONL logging, singleton services, POC endpoints, language-aware content, refactored for maintainability, centralized agent configuration
- **Voice Chat**: WebSocket-based real-time audio streaming with Gemini Live API integration, PCM audio debugging utilities
- **Evaluation**: AI agent evaluation system with persistent storage, comprehensive error handling, session validation, and resource cleanup
- **Testing**: 260+ tests, language functionality coverage (ContentLoader, auth, models), evaluation module unit tests, ResourceLoader version validation tests, comprehensive Makefile targets
- **Frontend**: Vue.js auth UI, i18n with Traditional Chinese, language switcher, reusable composables, dual-flow session creation
- **Localization**: Complete Traditional Chinese support with content isolation
- **Code Quality**: Simplified architecture with extracted utilities, focused methods, reduced duplication

### Architecture Highlights
- **Storage**: Async distributed locking, lease (60-300s) vs timeout (5-30s) separation
- **Chat**: Separated ADK runtime from JSONL persistence, per-message Runner creation, utility methods for JSONL parsing, centralized agent configuration
- **Backend Structure**: Helper methods for session validation, message logging, content loading, response generation
- **Frontend Patterns**: Composable architecture for modal management, async operations, data loading, dual-flow session creation with script/character selection
- **Config**: YAML + env vars, dynamic handler loading, fail-fast validation
- **Cloud**: GCS (async atomic ops), S3/Redis (stubs), env restrictions
- **Language Architecture**: Per-language content files, fallback filtering, UI/backend sync, caching
- **Evaluation Storage**: Persistent JSON reports with timestamps, re-evaluation support, efficient retrieval
- **Resource Management**: Version-validated JSON resources, separated character/scenario files, metadata tracking, validation tooling

## i18n/l10n Design Notes & Principles

### Architecture Overview
- **Language Isolation**: Content created in single language, no active translation
- **IETF BCP 47 Format**: Consistent language codes (`en`, `zh-TW`, `ja`) throughout system
- **User-Driven**: User's `preferred_language` drives all content selection and UI
- **Modular Design**: Language support integrated into existing architecture without disruption

### Frontend Implementation
- **Vue i18n**: Centralized translation management with locale files
- **Custom Components**: `ConfirmModal.vue` replaces browser dialogs for consistency
- **Language Switcher**: Header component with confirmation flow
- **State Management**: localStorage + backend sync for preference persistence
- **Content Reload**: Efficient switching without full page reload

### Backend Implementation
- **Content Files**: Language-specific resources (`scenarios_zh-TW.json`)
- **API Design**: Language parameter on content endpoints (`?language=zh-TW`)
- **Fallback Strategy**: Falls back to filtering main content if language file missing
- **Caching**: Per-language content caching for performance
- **User Model**: `preferred_language` field with default `"en"`

### Key Principles
1. **Single Source of Truth**: User preference stored in backend, synced to frontend
2. **Graceful Degradation**: Missing translations fall back to English
3. **Performance First**: Language-specific caching, lazy loading
4. **Future-Ready**: Architecture supports script creator vision (single-language content creation)
5. **Security**: Server-side content filtering by language preference

### Content Organization
- **File Naming**: `{resource}_{language}.json` pattern (e.g., `scenarios_zh-TW.json`)
- **Content Structure**: Each item tagged with `"language"` field
- **Scenario Compatibility**: Characters properly linked to scenarios within same language
- **System Prompts**: Localized instructions for role-play agents

### Known Localization Gaps
- **ChatWindow.vue**: Message input placeholders, session timestamps, and some UI labels remain in English
- **Dynamic Content**: Session labels using participant names not fully localized
- **Future Work**: Complete ChatWindow localization for full Traditional Chinese support

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
- ResourceLoader validates versions and caches content
- ContentLoader filters by language, caches per-language
- Frontend Vue i18n syncs with backend user preferences
- Language-specific content files: `scenarios_zh-TW.json`, `characters_zh-TW.json` 
