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
- **Evolution Path**: FileStorage (POC) → S3Storage (Production)
- **User Storage**: Support for user profiles, auth methods, and sessions
- **Location**: `role_play/common/storage.py`

### 8. **Multi-Environment Support**
- **Environment Configs**: Separate configs for dev/beta/prod
- **OAuth Flexibility**: Localhost support for dev, HTTPS for production
- **Feature Flags**: Environment-based feature enablement
- **Config Loading**: Template substitution for environment variables

### 9. **Data Model Location**
- **Data Class Placement**: Data class for each functionality should stay in each feature package, don't add to common unless actually shared among all classes or multiple classes/features

### 10. **Chat System ADK Integration**
- **Dual Setup Approach**: Development agent for `adk web` testing + Production FastAPI integration
- **Hybrid ADK Usage**: Leverage ADK for agent execution, custom SessionService for roleplay-specific storage
- **Custom SessionService**: Extends base ADK SessionService (not DatabaseSessionService) for JSONL evaluation format
- **Operator Workflow**: Operator creates sessions with scenario + character + participant → real-time JSONL logging
- **Storage Format**: `user_id_participant_scenario_id_datetime.jsonl` files for immediate evaluation access
- **Session Management**: ADK Session objects with roleplay metadata in state, custom event handling

### 11. **Frontend Architecture - Modular Monolith**
- **Start Simple Philosophy**: Begin with single module to minimize learning curve and development complexity
- **Built-in Seams**: Structure code with domain boundaries (auth/, chat/, evaluation/) from day one
- **Clear Evolution Path**: Each domain organized as future module with index.ts exports for clean APIs
- **Domain-Based Organization**: Components, stores, services, views grouped by domain within single module
- **Mechanical Migration**: When splitting needed, move files maintaining exact structure with only import path changes
- **Future-Proof Boundaries**: Service layer contracts, store interfaces, and component exports designed for modularity
- **Progressive Complexity**: Split modules only when file count, team conflicts, or build time demands it

### 12. **Testing Strategy**
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
- [x] Create `role_play/common/storage.py` - Storage abstraction (FileStorage, S3Storage)
- [x] Create `role_play/common/auth.py` - AuthManager, TokenData, UserRole, AuthProvider, User model

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

### Chat Module (ADK Integration) - POC Approach
- [ ] Create `role_play/dev_agents/roleplay_agent/` - Development agent for `adk web` testing
  - [ ] `role_play/dev_agents/roleplay_agent/__init__.py` - Package initialization
  - [ ] `role_play/dev_agents/roleplay_agent/agent.py` - Simple `root_agent` for ADK web UI
  - [ ] `role_play/dev_agents/roleplay_agent/.env` - Development environment config
- [ ] Create `role_play/chat/session_service.py` - Custom SessionService extending ADK base with JSONL storage
- [ ] Create `role_play/chat/adk_client.py` - ADK Agent and Runner management with roleplay context
- [ ] Create `role_play/chat/agent_config.py` - ADK agent configuration and setup
- [ ] Create `role_play/chat/handler.py` - ChatHandler extending BaseHandler with session creation endpoints
- [ ] Create `role_play/chat/models.py` - Chat request/response models with session metadata
- [ ] Add ADK dependencies to requirements: `pip install google-adk`
- [ ] **POC Simplifications**:
  - [ ] Create `role_play/chat/content_loader.py` - Load scenarios/characters from static JSON file
  - [ ] Create `data/scenarios.json` - Fixed scenario and character definitions
  - [ ] Implement HTTP-based chat (no WebSocket needed for POC)
  - [ ] Create simple text export endpoint: GET /chat/session/{id}/export-text
  - [ ] Basic session listing: GET /chat/sessions (no complex filtering)
- [ ] Create operator session creation workflow: POST /chat/session with scenario + character + participant
- [ ] Implement real-time JSONL logging for evaluation (append on each message exchange)

### Scripter Module
- [ ] Create `role_play/scripter/__init__.py`
- [ ] Create `role_play/scripter/handler.py` - ScripterHandler (admin only)
- [ ] Create `role_play/scripter/models.py` - Script models
- [ ] Create `role_play/scripter/storage.py` - Script persistence

### Evaluation Module (POC - Simple Export)
- [ ] Create `role_play/evaluation/__init__.py`
- [ ] Create `role_play/evaluation/handler.py` - Simple evaluation handler with text export
- [ ] Create `role_play/evaluation/export.py` - Text export utilities
- [ ] **POC Simplifications**:
  - [ ] Simple text export: Convert JSONL to readable conversation format
  - [ ] Basic session import from chat: Copy session IDs to evaluation queue
  - [ ] Download endpoint: GET /evaluation/session/{id}/download - Returns text file
  - [ ] Session list: GET /evaluation/sessions - Simple list for selection
  - [ ] No complex analytics, scoring, or batch operations for POC

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
- [ ] Create `config/dev.yaml` - Development configuration
- [ ] Create `config/beta.yaml` - Beta/staging configuration
- [ ] Create `config/prod.yaml` - Production configuration
- [ ] Update `.env.example` with required variables (JWT_SECRET_KEY, GOOGLE_CLIENT_ID, etc.)

### Testing Infrastructure
- [x] Create `test/python/` directory structure (unit/integration/e2e/fixtures)
- [x] Create `test/python/conftest.py` - Pytest configuration and shared fixtures
- [x] Create `test/python/fixtures/` - Test data factories and helper functions
- [x] Create `test/python/unit/common/` - Unit tests for models, storage, auth, exceptions
- [x] Create `test/python/unit/server/` - Unit tests for base handlers, decorators, dependencies
- [x] Create `test/python/integration/storage/` - Storage backend integration tests
- [x] Create `test/python/integration/auth/` - OAuth flow and auth integration tests
- [ ] Create `test/python/integration/handlers/` - Handler registration and dependency injection tests
- [ ] Create `test/python/e2e/api/` - End-to-end API workflow tests
- [x] Set up pytest configuration with coverage reporting and async support
- [x] Create `test/README.md` - Comprehensive testing guide and documentation

### Documentation
- [ ] Update README.md with architecture overview
- [ ] Create API.md with endpoint documentation
- [ ] Create DEPLOYMENT.md with deployment instructions
- [ ] Create OAUTH_SETUP.md with Google OAuth setup guide
- [ ] Create ENVIRONMENTS.md with multi-environment setup

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

### Testing Infrastructure (COMPLETED)
- **Comprehensive Test Suite**: 125 tests with 92.41% code coverage  
- **Multi-Language Structure**: `/test/python/` ready for future `/test/ts/`, `/test/android/`
- **Test Categories**: Unit tests (99), Integration tests (26) with proper separation
- **Coverage Breakdown**: AuthManager (96%), FileStorage (88%), Models/Exceptions (100%), Auth Decorators (100%)
- **Real Validation**: All FileStorage CRUD operations and AuthManager workflows tested
- **Performance Tests**: Including large dataset scenarios marked with `@pytest.mark.slow`
- **Test Documentation**: Complete testing guide in `/test/README.md`
- **Pytest Configuration**: Async support, coverage reporting, test markers, fixtures

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

### Configuration System (COMPLETED)
- **Unified Config Loader**: Environment-aware YAML + .env loading with template substitution
- **Environment Validation**: Enum-based environment support (DEV/BETA/PROD) with fail-fast validation
- **Dynamic Handler Registration**: Importlib-based handler loading from configuration
- **Fallback Warnings**: Clear feedback when YAML configs are missing or using defaults
- **Fail-Fast Validation**: Storage path and configuration validation at server startup
- **No Global State**: Eliminated global variables in dependencies, pure factory functions
- **Production Ready**: JWT secret validation, proper error handling, concurrency warnings

### Chat System Architecture (POC APPROACH)
- **Simplified POC Strategy**: Focus on core chat functionality with minimal complexity
- **Static Content**: Scenarios and characters loaded from JSON file (no CRUD needed)
- **HTTP-Based Chat**: Simple request/response chat (no WebSocket for POC)
- **JSONL + Text Export**: Maintain JSONL for structure, export as readable text for evaluation
- **Fixed Data**: `data/scenarios.json` with predefined roleplay scenarios and characters
- **Core Workflow**: Operator selects from dropdown → creates session → text-based chat → export for evaluation

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
Please clean up any files that you've created for testing or debugging purposes after they're no longer needed.