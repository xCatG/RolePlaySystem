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

### 10. **Testing Strategy**
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
- [ ] Create `role_play/server/base_handler.py` - BaseHandler abstract class
- [ ] Create `role_play/server/base_server.py` - BaseServer with auto-registration
- [ ] Create `role_play/server/auth_decorators.py` - @auth_required, @admin_only
- [ ] Create `role_play/server/dependencies.py` - Dependency injection factories
- [ ] Create `role_play/server/websocket.py` - WebSocket connection manager
- [ ] Refactor `role_play/server/config.py` - Add HandlerConfig, AuthConfig, OAuthConfig
- [ ] Refactor `role_play/server/role_play_server.py` - Inherit from BaseServer

### Authentication Module
- [ ] Create `role_play/auth/__init__.py`
- [ ] Create `role_play/auth/handler.py` - AuthHandler with login/register/OAuth endpoints
- [ ] Create `role_play/auth/models.py` - LoginRequest, RegisterRequest, OAuth response models
- [ ] Create `role_play/auth/oauth_client.py` - OAuth client wrapper for multiple providers

### Chat Module
- [ ] Refactor `role_play/chat/handler.py` - ChatHandler extending BaseHandler
- [ ] Create `role_play/chat/models.py` - Chat-specific request/response models
- [ ] Create `role_play/chat/audio_processor.py` - Audio format conversion, buffering
- [ ] Create `role_play/chat/gemini_client.py` - Gemini Live API integration

### Scripter Module
- [ ] Create `role_play/scripter/__init__.py`
- [ ] Create `role_play/scripter/handler.py` - ScripterHandler (admin only)
- [ ] Create `role_play/scripter/models.py` - Script models
- [ ] Create `role_play/scripter/storage.py` - Script persistence

### Evaluator Module
- [ ] Create `role_play/evaluator/__init__.py`
- [ ] Create `role_play/evaluator/handler.py` - EvaluatorHandler
- [ ] Create `role_play/evaluator/models.py` - Evaluation models
- [ ] Create `role_play/evaluator/engine.py` - Evaluation logic

### Configuration & Environment
- [ ] Create `config/dev.yaml` - Development configuration
- [ ] Create `config/beta.yaml` - Beta/staging configuration
- [ ] Create `config/prod.yaml` - Production configuration
- [ ] Update `.env.example` with required variables (JWT_SECRET_KEY, GOOGLE_CLIENT_ID, etc.)
- [ ] Create `role_play/server/config_loader.py` - Environment-aware config loading with template substitution

### Testing Infrastructure
- [x] Create `test/python/` directory structure (unit/integration/e2e/fixtures)
- [x] Create `test/python/conftest.py` - Pytest configuration and shared fixtures
- [x] Create `test/python/fixtures/` - Test data factories and helper functions
- [x] Create `test/python/unit/common/` - Unit tests for models, storage, auth, exceptions
- [ ] Create `test/python/unit/server/` - Unit tests for base handlers, decorators, dependencies
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
- **Comprehensive Test Suite**: 98 tests with 92.53% code coverage
- **Multi-Language Structure**: `/test/python/` ready for future `/test/ts/`, `/test/android/`
- **Test Categories**: Unit tests (67), Integration tests (31) with proper separation
- **Coverage Breakdown**: AuthManager (97%), FileStorage (88%), Models/Exceptions (100%)
- **Real Validation**: All FileStorage CRUD operations and AuthManager workflows tested
- **Performance Tests**: Including large dataset scenarios marked with `@pytest.mark.slow`
- **Test Documentation**: Complete testing guide in `/test/README.md`
- **Pytest Configuration**: Async support, coverage reporting, test markers, fixtures

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
Please clean up any files that you've created for testing or debugging purposes after they're no longer needed.