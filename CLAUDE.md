# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# RolePlay System - Architecture Design Summary

## Design Decisions

### 1. **Dependency Architecture**
- **Layered Architecture**: Application layer (chat/evaluator/scripter) depends on Base layer (server/common)
- **No Circular Dependencies**: Server package never imports from application packages
- **Clean Separation**: Business logic in handlers, infrastructure in server/common

### 2. **Handler Pattern**
- **Stateless Handlers**: New handler instance per HTTP request or WebSocket connection
- **Benefits**: Prevents shared state bugs, enables horizontal scaling, simplifies testing
- **Lifecycle**: 
  - HTTP: Handler instantiated per request
  - WebSocket: Handler lives for connection duration

### 3. **Dependency Injection**
- **Choice**: FastAPI's built-in `Depends()` system
- **Rationale**: Zero setup complexity, type safety, automatic documentation
- **Pattern**: Dependencies injected via factory functions

### 4. **Configuration System**
- **Configuration-Based Handler Registration**: Handlers defined in config, dynamically loaded
- **Structure**: `ServerConfig` → `HandlerConfig` list → Dynamic import and registration
- **Benefits**: Enable/disable handlers without code changes, configurable route prefixes

### 5. **Authentication**
- **JWT-Based Sessions**: Stateless authentication using signed tokens
- **Multi-Provider Support**: Local (username/password) and OAuth (Google, extensible)
- **Role-Based Access**: Admin and User roles
- **Decorator Pattern**: `@auth_required` and `@admin_only` decorators
- **WebSocket Auth**: First message must contain auth token
- **User Management**: User profiles with multiple auth methods support

### 6. **WebSocket Support**
- **Voice Interaction**: WebSocket for real-time audio streaming
- **Gemini Live API Integration**: Proxy pattern for audio processing
- **Text + Audio**: HTTP for text messages, WebSocket for audio streams

### 7. **Storage Abstraction**
- **Interface Pattern**: `StorageBackend` ABC with implementations
- **Evolution Path**: FileStorage (POC) → GCSStorage/S3Storage (Production)
- **User Storage**: Support for user profiles, auth methods, and sessions
- **Location**: `role_play/common/storage.py`
- **Per-User Data Segmentation**: All user-specific data organized under user ID prefix
  - Pattern: `users/{user_id}/profile`, `users/{user_id}/chat_logs/{session_id}`, etc.
  - Benefits: Easier per-user operations, better access control, cleaner organization
  - Migration path: FileStorage uses actual directories, cloud storage uses key prefixes
- **Key/Path Conventions**: 
  - No file extensions in storage keys (no .json suffix)
  - Storage implementations handle serialization internally
  - Keys are opaque strings that work identically across FileStorage/GCS/S3
  - Example: `users/123/profile` not `users/123.json`
- **Distributed Locking Architecture**:
  - **Lock Lease Duration**: Separate from acquisition timeout for robust crash recovery
  - **Configurable Strategies**: File locking (dev), Object locking (GCS), Redis (high-performance)
  - **Lease vs Timeout**: `lease_duration_seconds` (60-300s) for crash recovery, `timeout` (5-30s) for retry logic
  - **Async Operations**: All blocking I/O operations use `asyncio.to_thread()` for non-blocking execution
  - **Stale Lock Recovery**: Automatic cleanup of expired locks with comprehensive logging

### 8. **Multi-Environment Support**
- **Environment Configs**: Separate configs for dev/beta/prod
- **OAuth Flexibility**: Localhost support for dev, HTTPS for production
- **Feature Flags**: Environment-based feature enablement
- **Config Loading**: Template substitution for environment variables

### 9. **Data Model Location**
- **Data Class Placement**: Data class for each functionality should stay in each feature package, don't add to common unless actually shared among all classes or multiple classes/features

### 10. **Chat System ADK Integration - Separated Concerns Architecture**
- **Clear Separation**: ADK's InMemorySessionService for runtime state, ChatLogger for persistent JSONL logs
- **Stateless Handlers**: ChatHandler created per-request via FastAPI dependency injection
- **Singleton Services**: ContentLoader, ChatLogger, and InMemorySessionService shared across requests
- **File Locking**: ChatLogger implements FileLock for safe concurrent JSONL writes
- **Storage Format**: `users/{user_id}/chat_logs/{session_id}` with structured JSONL events (session_start, message, session_end)
- **Session State**: ADK session stores metadata (character_id, scenario_id, message_count) + reference to JSONL file
- **On-Demand Runners**: ADK Agent and Runner created per message, not stored between requests
- **Export Ready**: ChatLogger provides text export and session listing without touching ADK state

### 11. **Frontend Architecture - Modular Monolith**
- **Start Simple Philosophy**: Begin with single module to minimize learning curve and development complexity
- **Built-in Seams**: Structure code with domain boundaries (auth/, chat/, evaluation/) from day one
- **Clear Evolution Path**: Each domain organized as future module with index.ts exports for clean APIs
- **Domain-Based Organization**: Components, stores, services, views grouped by domain within single module
- **Mechanical Migration**: When splitting needed, move files maintaining exact structure with only import path changes
- **Future-Proof Boundaries**: Service layer contracts, store interfaces, and component exports designed for modularity
- **Progressive Complexity**: Split modules only when file count, team conflicts, or build time demands it

### 12. **Distributed Locking Architecture - Production Ready**
- **Lease Duration vs Acquisition Timeout Separation**: Critical architectural principle for robust distributed systems
  - **Lock Lease Duration** (`lease_duration_seconds`): How long a lock remains valid if the holder crashes (60-300 seconds)
  - **Acquisition Timeout** (`timeout`): How long to retry acquiring a contested lock (5-30 seconds)
  - **Independent Configuration**: These serve different purposes and must be tuned separately
- **Async-First Design**: All blocking I/O operations use `asyncio.to_thread()` for FastAPI compatibility
- **Stale Lock Recovery**: Automatic detection and cleanup of expired locks with race condition handling
- **Comprehensive Logging**: Debug/info/warning levels for operational visibility and troubleshooting
- **Cross-Backend Consistency**: Same locking semantics across FileStorage (dev) and GCS (production)
- **Production Deployment Ready**: Tested with concurrent operations and proper error handling

### 13. **Testing Strategy**
- **Multi-Language Structure**: Tests organized by language to support future TypeScript web frontend, Android client, etc.
- **Test Location**: `/test/python/` for Python backend tests (separate from source code)
- **Test Types & Organization**:
  - `test/python/unit/` - Fast isolated unit tests for individual components
    - `test/python/unit/common/` - Tests for shared models, storage, auth
    - `test/python/unit/server/` - Tests for base handlers, decorators, dependencies  
    - `test/python/unit/chat/` - Tests for chat-specific logic
    - `test/python/unit/auth/` - Tests for auth module
    - `test/python/unit/scripter/` - Tests for scripter module
    - `test/python/unit/evaluator/` - Tests for evaluator module
  - `test/python/integration/` - Tests for module interactions and external dependencies
    - `test/python/integration/storage/` - FileStorage vs database backend tests
    - `test/python/integration/auth/` - OAuth flow integration tests
    - `test/python/integration/handlers/` - Handler registration and dependency injection
  - `test/python/e2e/` - End-to-end API tests with real HTTP requests
    - `test/python/e2e/api/` - Full API workflow tests
    - `test/python/e2e/websocket/` - WebSocket connection and audio streaming tests
  - `test/python/fixtures/` - Shared test data, factories, and helper functions
- **Test Naming**: `test_<module_name>.py` for unit tests, `test_<feature>_flow.py` for integration/e2e
- **Coverage Strategy**: >90% unit test coverage, integration tests for critical paths, e2e for user journeys
- **Test Dependencies**: pytest, httpx (async HTTP), pytest-asyncio, factory-boy (test data), temporary directories for storage

## Implementation TODO List

### Base Infrastructure
- [x] Create `role_play/common/__init__.py`
- [x] Create `role_play/common/models.py` - Shared data models
- [x] Create `role_play/common/exceptions.py` - Custom exceptions
- [x] Create `role_play/common/storage.py` - Storage abstraction with configurable locking strategies
- [x] Create `role_play/common/auth.py` - AuthManager, TokenData, UserRole, AuthProvider, User model
- [x] **Cloud Storage Implementation** - Complete extensible cloud storage system
  - [x] Add lock configuration models (LockConfig, StorageConfig classes)
  - [x] Create `role_play/common/GCSBackend.py` - Google Cloud Storage with object-based locking
  - [x] Create `role_play/common/S3Backend.py` - AWS S3 Storage backend (stub implementation)
  - [x] Create `role_play/common/redis_locking.py` - Redis-based locking strategy (stub with documentation)
  - [x] Create `role_play/common/storage_factory.py` - Configuration-based backend selection
  - [x] Create `role_play/common/storage_monitoring.py` - Lock performance monitoring and decision criteria
  - [x] Add environment restrictions (dev: all storage types, beta/prod: cloud only)
  - [x] Update requirements.txt with cloud storage dependencies
  - [x] Create comprehensive configuration examples in `config/storage-examples.yaml`
  - [x] Update `config/dev.yaml` with new storage configuration format
- [x] **Distributed Locking Improvements** - Production-ready async locking system
  - [x] Separate lock lease duration from acquisition timeout across all backends
  - [x] All GCS operations made fully async with `asyncio.to_thread()`
  - [x] Enhanced stale lock detection and recovery with comprehensive logging
  - [x] FileStorage constructor updated to use config objects for proper lock configuration
  - [x] Fixed all test files (47+ files) to use new config-based FileStorage constructor
  - [x] Production-ready timeout and retry logic with race condition handling

### Server Core
- [x] Create `role_play/server/base_handler.py` - BaseHandler abstract class
- [x] Create `role_play/server/base_server.py` - BaseServer with auto-registration
- [x] Create `role_play/server/auth_decorators.py` - @auth_required, @admin_only, role hierarchy support
- [x] Create `role_play/server/dependencies.py` - Dependency injection factories
- [ ] Create `role_play/server/websocket.py` - WebSocket connection manager
- [x] Refactor `role_play/server/config.py` - Add HandlerConfig, AuthConfig, OAuthConfig
- [x] Create `role_play/server/user_account_handler.py` - User registration/login endpoints
- [x] Update `run_server.py` - Main server entry point using BaseServer

### Authentication Module
- [ ] Create `role_play/auth/__init__.py`
- [ ] Create `role_play/auth/handler.py` - AuthHandler with login/register/OAuth endpoints
- [ ] Create `role_play/auth/models.py` - LoginRequest, RegisterRequest, OAuth response models
- [ ] Create `role_play/auth/oauth_client.py` - OAuth client wrapper for multiple providers
- [x] ~~Revisit role auth decorator compatibility with FastAPI~~ - **COMPLETED**: Replaced with RoleChecker dependency pattern
- [x] ~~Figure out how to use FastAPI `Depends()` correctly~~ - **COMPLETED**: Implemented RoleChecker with proper Depends() usage
- [x] ~~Sync data types between backend and frontend~~ - **COMPLETED**: TypeScript types now exactly match Python Pydantic models

### Chat Module (ADK Integration) - Separated Concerns Architecture
- [x] Create `role_play/dev_agents/roleplay_agent/` - Development agent for `adk web` testing
  - [x] `role_play/dev_agents/roleplay_agent/__init__.py` - Package initialization
  - [x] `role_play/dev_agents/roleplay_agent/agent.py` - Simple `root_agent` for ADK web UI
  - [x] `role_play/dev_agents/roleplay_agent/.env` - Development environment config
- [x] ~~Create `role_play/chat/session_service.py`~~ - **REMOVED**: Replaced with separated ChatLogger + InMemorySessionService
- [x] Create `role_play/chat/chat_logger.py` - Handles all JSONL file operations with file locking
- [x] Create `role_play/chat/handler.py` - Stateless ChatHandler with dependency injection
- [x] Create `role_play/chat/models.py` - Chat request/response models with session metadata
- [x] Add ADK dependencies to requirements: `pip install google-adk`
- [x] Add filelock to requirements: `pip install filelock>=3.13.0`
- [x] **Architecture Improvements**:
  - [x] Singleton services via `@lru_cache` in dependencies.py
  - [x] Stateless handlers - no instance variables storing state
  - [x] On-demand ADK Runner creation per message
  - [x] File locking for concurrent JSONL access
  - [x] Clear separation between runtime state (ADK) and persistence (ChatLogger)
- [x] **POC Features**:
  - [x] Create `role_play/chat/content_loader.py` - Load scenarios/characters from static JSON file
  - [x] Create `data/scenarios.json` - Fixed scenario and character definitions
  - [x] Implement HTTP-based chat (no WebSocket needed for POC)
  - [x] Create simple text export endpoint: GET /chat/session/{id}/export-text
  - [x] Basic session listing: GET /chat/sessions (no complex filtering)
  - [x] Session end endpoint: POST /chat/session/{id}/end
- [x] Create operator session creation workflow: POST /chat/session with scenario + character + participant
- [x] Implement real-time JSONL logging for evaluation (append on each message exchange)

### Scripter Module
- [ ] Create `role_play/scripter/__init__.py`
- [ ] Create `role_play/scripter/handler.py` - ScripterHandler (admin only)
- [ ] Create `role_play/scripter/models.py` - Script models
- [ ] Create `role_play/scripter/storage.py` - Script persistence

### Evaluation Module (POC - Simple Export)
- [x] Create `role_play/evaluation/__init__.py`
- [x] Create `role_play/evaluation/handler.py` - Simple evaluation handler with text export
- [x] Create `role_play/evaluation/export.py` - Text export utilities
- [x] **POC Simplifications**:
  - [x] Simple text export: Convert JSONL to readable conversation format
  - [x] Basic session import from chat: Copy session IDs to evaluation queue
  - [x] Download endpoint: GET /evaluation/session/{id}/download - Returns text file
  - [x] Session list: GET /evaluation/sessions - Simple list for selection
  - [x] No complex analytics, scoring, or batch operations for POC

### Frontend (TypeScript/Vue.js) - Modular Monolith
- [x] Create `src/ts/role_play/ui/` - Vue.js authentication interface with login/register
- [x] Create `src/ts/role_play/chat/` - Directory structure for future chat UI components
- [ ] Restructure as modular monolith with domain-based organization:
  - [ ] `src/ts/role_play/types/` - Domain-separated types (auth.ts, chat.ts, evaluation.ts, shared.ts)
  - [ ] `src/ts/role_play/services/` - API clients by domain (auth-api.ts, chat-api.ts, evaluation-api.ts)
  - [ ] `src/ts/role_play/stores/` - Domain-specific stores (auth.ts, chat.ts, evaluation.ts)
  - [ ] `src/ts/role_play/components/` - Components grouped by domain (shared/, auth/, chat/, evaluation/)
  - [ ] `src/ts/role_play/views/` - Views organized by domain (auth/, chat/, evaluation/)
- [ ] Implement domain boundaries with clean index.ts exports for future modularity
- [ ] Create chat interface with WebSocket support and session management
- [ ] Implement evaluation interface with session import from chat
- [ ] Add domain-based routing with clear module boundaries
- [ ] Create cross-domain integration patterns (chat sessions → evaluation queue)
- [ ] Document migration strategy for future module splitting

### Configuration & Environment
- [x] Create `role_play/server/config_loader.py` - Environment-aware config loading with template substitution
- [x] Create `config/dev.yaml` - Development configuration (updated with chat/evaluation handlers)
- [x] Create `config/beta.yaml` - Beta/staging configuration
- [x] Create `config/prod.yaml` - Production configuration
- [x] Update `.env.example` with required variables (JWT_SECRET_KEY, GOOGLE_CLIENT_ID, ADK variables, etc.)

### Testing Infrastructure
- [x] Create `test/python/` directory structure (unit/integration/e2e/fixtures)
- [x] Create `test/python/conftest.py` - Pytest configuration and shared fixtures
- [x] Create `test/python/fixtures/` - Test data factories and helper functions
- [x] Create `test/python/unit/common/` - Unit tests for models, storage, auth, exceptions
- [x] Create `test/python/unit/server/` - Unit tests for base handlers, decorators, dependencies
- [x] Create `test/python/integration/storage/` - Storage backend integration tests
  - [x] Create `test_working_storage_integration.py` - Working integration tests for cloud storage system
  - [x] Test storage factory with environment restrictions (dev/beta/prod)
  - [x] Test GCS backend creation and method validation with mocking
  - [x] Test storage monitoring classes existence and basic functionality
  - [x] Test configuration validation for different storage types
- [x] Create `test/python/integration/auth/` - OAuth flow and auth integration tests
- [ ] Create `test/python/integration/handlers/` - Handler registration and dependency injection tests
- [ ] Create `test/python/e2e/api/` - End-to-end API workflow tests
- [x] Set up pytest configuration with coverage reporting and async support
- [x] Create `test/README.md` - Comprehensive testing guide and documentation

### Code Cleanup (Technical Debt)
- [ ] **Remove deprecated auth_decorators.py** - Now deprecated in favor of RoleChecker dependency pattern
  - [ ] Remove `role_play/server/auth_decorators.py` file
  - [ ] Remove `test/python/unit/server/test_auth_decorators.py` tests
  - [ ] Update remaining imports in:
    - [ ] `role_play/server/user_account_handler.py` - Remove unused import
    - [ ] `role_play/evaluation/handler.py` - Replace with RoleChecker dependencies
    - [ ] `role_play/server/example_role_usage.py` - Update examples to use new pattern
- [ ] **Validate no usage of deprecated decorators** - Ensure no @auth_required, @admin_only, @scripter_only remain in codebase

### Documentation
- [ ] Update README.md with architecture overview
- [x] Create API.md with endpoint documentation
- [x] Create DEPLOYMENT.md with deployment instructions for Google Cloud
- [ ] Create OAUTH_SETUP.md with Google OAuth setup guide
- [x] Create ENVIRONMENTS.md with multi-environment setup
- [x] Create .dockerignore for container builds

### User Management
- [ ] Create `role_play/users/__init__.py`
- [ ] Create `role_play/users/models.py` - User profile models
- [ ] Create `role_play/users/service.py` - User management service
- [ ] Implement user profile endpoints (GET/UPDATE /users/me)
- [ ] Implement admin user management endpoints

### Database (Future)
- [ ] Design user account schema with OAuth support
- [ ] Design user_auth_methods table for multiple auth providers
- [ ] Design script storage schema
- [ ] Design evaluation results schema
- [ ] Create migration scripts

## Implementation Order

1. **Phase 1 - Core Infrastructure** (Do First)
   - Common models and exceptions
   - Storage abstraction with user support
   - Base handler and server classes
   - Multi-environment configuration system

2. **Phase 2 - Authentication** (Do Second)
   - Auth manager and decorators
   - Local auth (username/password)
   - OAuth integration (Google)
   - User profile management
   - JWT token management

3. **Phase 3 - Handlers** (Do Third)
   - Chat handler with text support
   - Scripter handler (admin only)
   - Evaluator handler
   - User management endpoints

4. **Phase 4 - WebSocket & Audio** (Do Fourth)
   - WebSocket manager
   - Audio processor
   - Gemini Live API integration

5. **Phase 5 - Polish** (Do Last)
   - Comprehensive testing
   - Documentation
   - Error handling improvements
   - Production deployment setup

## Implementation Notes

### Base Infrastructure (COMPLETED)
- Created common module with all shared components
- FileStorage implementation ready for development/testing
- AuthManager supports both local (username/password) and OAuth authentication
- JWT token management with configurable expiration
- User models support multiple authentication methods per user
- Storage abstraction allows easy migration to database backends later
- **Cleanup**: Removed legacy server files (role_play_server.py, config.py, models.py) to prepare for clean BaseServer implementation

### Testing Infrastructure (UPDATED - 2025-05-30)
- **Comprehensive Test Suite**: 150+ tests with 30% code coverage (relaxed for cloud storage stubs)
- **Multi-Language Structure**: `/test/python/` ready for future `/test/ts/`, `/test/android/`
- **Test Categories**: Unit tests (100+), Integration tests (30+) with proper separation
- **Coverage Breakdown**: 
  - Core FileStorage: 92% (production ready)
  - Auth/Models: 80%+ (well tested)
  - Cloud Storage: 0% (stubs and minimal integration tests)
  - Storage Factory: 0% (basic integration tests only)
- **Real Validation**: All core functionality tested, cloud storage validated via integration tests
- **Performance Tests**: Including large dataset scenarios marked with `@pytest.mark.slow`
- **Test Documentation**: Complete testing guide in `/test/README.md`
- **Pytest Configuration**: Async support, 25% coverage threshold, cloud storage markers

### Barebone Server Implementation (COMPLETED)
- **FastAPI Server**: Fully functional with JWT authentication
- **User Account Handler**: Stateless handler with POST /auth/register, POST /auth/login, GET /auth/me
- **Email-based Authentication**: Users register and login with email+password (not username)
- **JWT Token Management**: Configurable expiration, proper token verification
- **CORS Support**: Enabled for frontend development
- **Error Handling**: Proper HTTP status codes and error messages
- **Production Ready**: Configurable via environment variables
- **Storage Configuration**: Environment variable support (STORAGE_PATH) with fail-fast validation
- **Deployment-Friendly**: Requires pre-existing storage directories, no silent directory creation

### Authentication System (COMPLETED)
- **Role-Based Authorization**: Complete decorator system with @auth_required, @admin_only, @scripter_only, @public
- **Role Hierarchy**: ADMIN > SCRIPTER > USER > GUEST with proper permission inheritance
- **Decorator Features**: Flexible role requirements (single role, multiple roles, any authenticated user)
- **HTTP Status Codes**: Proper 401 (Unauthorized) and 403 (Forbidden) responses
- **Example Usage**: Complete documentation in `role_play/server/example_role_usage.py`
- **Full Test Coverage**: 100% test coverage for all auth decorator functionality

### Frontend Architecture (PARTIAL)
- **Multi-Language Structure**: `/src/ts/role_play/` for TypeScript frontend components
- **UI Module**: Vue.js 3 authentication interface at `/src/ts/role_play/ui/`
- **Chat Module Structure**: Basic directory structure at `/src/ts/role_play/chat/`
- **Responsive Design**: Clean, modern styling with form validation
- **API Integration**: Full integration with Python backend auth endpoints
- **Token Management**: Automatic JWT storage and validation
- **Development Ready**: Vite build system, hot reload, CORS configured
- **Container Support**: Automatic host binding (0.0.0.0) for devcontainer compatibility

### Frontend Modular Monolith Architecture (PLANNED)
- **Single Module Start**: All frontend code in one module with domain-based organization
- **Built-in Seams**: Components, stores, services, and views organized by domain (auth/, chat/, evaluation/)
- **Clear APIs**: Each domain exports through index.ts files for clean interfaces
- **Evolution Ready**: Structure allows mechanical migration to separate modules when needed
- **Domain Boundaries**: Cross-domain communication through well-defined store interfaces
- **Progressive Splitting**: Start monolithic, split modules only when complexity demands it

### POC Implementation (COMPLETED - 2024-05-24)
- **Chat Module**: Full implementation with ADK integration placeholder
  - Static content loading from `data/scenarios.json`
  - Session management with JSONL logging for evaluation
  - HTTP-based chat endpoints (no WebSocket for POC)
  - Text export functionality for sessions
  - ADK client with placeholder responses (ready for real ADK integration)
- **Evaluation Module**: Simple text export implementation
  - Session listing from JSONL files
  - Text transcript download functionality
  - Direct integration with chat module's JSONL format
- **API Endpoints Created**:
  - `GET /chat/content/scenarios` - List available scenarios
  - `GET /chat/content/scenarios/{id}/characters` - Get compatible characters
  - `POST /chat/session` - Create new roleplay session
  - `GET /chat/sessions` - List user's sessions
  - `POST /chat/session/{id}/message` - Send message in session
  - `GET /chat/session/{id}/export-text` - Export session as text
  - `GET /evaluation/sessions` - List sessions for evaluation
  - `GET /evaluation/session/{id}/download` - Download session transcript
- **Data Configuration** (Updated 2025-05-28):
  - Created `data/scenarios.json` with 2 scenarios and 4 characters
  - ContentLoader successfully loads static content from project root
  - Note: In production, this would be environment-specific data in a database
- **Testing** (Updated 2025-05-28):
  - Added comprehensive unit tests for ContentLoader (16 test cases, 100% coverage)
  - Tests use mocking to avoid file system dependencies
  - Test location: `test/python/unit/chat/test_content_loader.py`
- **Next Steps**:
  - Replace ADK placeholder with actual Google ADK integration
  - Add WebSocket support for real-time chat (Phase 4)
  - Implement frontend chat interface
  - Add more sophisticated evaluation features

### Configuration System (COMPLETED)
- **Unified Config Loader**: Environment-aware YAML + .env loading with template substitution
- **Environment Validation**: Enum-based environment support (DEV/BETA/PROD) with fail-fast validation
- **Dynamic Handler Registration**: Importlib-based handler loading from configuration
- **Fallback Warnings**: Clear feedback when YAML configs are missing or using defaults
- **Fail-Fast Validation**: Storage path and configuration validation at server startup
- **No Global State**: Eliminated global variables in dependencies, pure factory functions
- **Production Ready**: JWT secret validation, proper error handling, concurrency warnings

### Chat System Architecture (COMPLETED - Separated Concerns)
- **Clean Architecture**: Separated ADK runtime state from JSONL persistence layer
- **Stateless Handlers**: ChatHandler instances created per-request, no stored state
- **Singleton Services**:
  - `ContentLoader`: Loads static scenarios/characters from JSON
  - `ChatLogger`: Manages all JSONL file operations with file locking
  - `InMemorySessionService`: ADK's built-in service for runtime session state
- **Dependency Injection**: All services injected via FastAPI's `Depends()` pattern
- **File Locking**: Concurrent JSONL writes protected by FileLock (5-second timeout)
- **Session Lifecycle**:
  1. Create session: ChatLogger creates JSONL file, ADK stores metadata in memory
  2. Send message: Log to JSONL, create Runner on-demand, process with ADK, log response
  3. End session: Log session_end event, remove from ADK memory
  4. Export: ChatLogger reads JSONL directly, formats as human-readable text
- **Storage Format**: Clean JSONL with typed events (session_start, message, session_end)
- **No Persistent Runners**: ADK Runners created per-message and immediately discarded
- **POC Features**: Static content, HTTP-only chat, text export for evaluation

### Cloud Storage System (COMPLETED - 2025-05-31)
- **Extensible Architecture**: Strategy pattern for locking with pluggable storage backends
- **Multiple Backend Support**: FileStorage (dev), GCSStorage (production), S3Storage (stub)
- **Configurable Locking Strategies**:
  - `file`: OS-level file locking for single-server deployments
  - `object`: Cloud storage object-based locking (GCS atomic operations, S3 best-effort)
  - `redis`: High-performance Redis-based distributed locking (stub with documentation)
- **Environment Restrictions**: Dev allows all storage types, Beta/Prod enforce cloud-only storage
- **YAML Configuration**: Complete examples and environment variable support
- **Factory Pattern**: `storage_factory.py` with validation and environment-aware backend selection
- **Monitoring System**: Built-in performance metrics and decision criteria for strategy upgrades
- **Production Guidance**: Clear documentation on when to use each locking strategy
- **Dependencies**: Added google-cloud-storage, boto3, redis to requirements.txt
- **Production-Ready Locking**: Fully async distributed locking with proper lease duration separation
- **Implementation Details**:
  - GCS Backend: Full async implementation with atomic object operations using `if_generation_match=0`
  - S3 Backend: Stub with best-effort locking documented for production Redis migration
  - Redis Strategy: Stub implementation with SET NX PX patterns and HA considerations
  - Lock Monitoring: Tracks acquisition rates, latency, contention for informed decisions
  - Configuration Examples: Development, staging, and production configurations in YAML format
  - **Architectural Fix**: Lock lease duration (crash recovery) properly separated from acquisition timeout (retry logic)
  - **Async Operations**: All blocking I/O wrapped in `asyncio.to_thread()` for FastAPI compatibility
  - **Enhanced Logging**: Comprehensive debug/info/warning logs for lock operations and stale cleanup
  - **Test Compatibility**: All 47+ test files updated to use config-based storage constructors

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
Please clean up any files that you've created for testing or debugging purposes after they're no longer needed.
ALWAYS sync the data type for Frontend (ts) with backend (python pydantic) with making changes to keep them in sync

## Datetime Handling Guidelines (Python)
Always use **UTC** for any persisted datetime. Never store user-local or client-generated times.
**DO NOT mix** timezone-aware and naive datetimes. Use `datetime.now(timezone.utc)`. Persist datetime values as ISO 8601 UTC Strings! 
However, it is acceptable to use datetime.utcnow().isoformat() ONLY when saving a timestamp as a string immediately (e.g, "created_at" or "update_at")
All datetime parsing and formatting will ASSUME UTC.
Client-side code may only convert UTC to local time for display purpose. No timestamp creation or modification should be on client. 
