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

## Implementation TODO List

### Base Infrastructure
- [ ] Create `role_play/common/__init__.py`
- [ ] Create `role_play/common/models.py` - Shared data models
- [ ] Create `role_play/common/exceptions.py` - Custom exceptions
- [ ] Create `role_play/common/storage.py` - Storage abstraction (FileStorage, S3Storage)
- [ ] Create `role_play/common/auth.py` - AuthManager, TokenData, UserRole, AuthProvider, User model

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
- [ ] Create `tests/` directory structure
- [ ] Create `tests/conftest.py` - Pytest fixtures
- [ ] Create `tests/test_auth.py` - Authentication tests (local + OAuth)
- [ ] Create `tests/test_handlers.py` - Handler registration tests
- [ ] Create `tests/test_oauth.py` - OAuth flow tests
- [ ] Create `tests/test_multi_env.py` - Multi-environment config tests

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
