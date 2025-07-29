# Resource Architecture Design

## Overview
This document describes the resource management architecture for the Role Play System, including the distinction between base resources and user-created content.

## Resource Types

### Base Resources
- **Location**: `/resources/` in storage backend (GCS/S3/File)
- **Purpose**: System-provided scenarios and characters available to all users
- **Management**: Deployed with the application, version controlled
- **Examples**: Medical interview, Customer service scenarios

### User Resources (Future - Script Creator Module)
- **Location**: `/users/{user_id}/resources/` in storage backend
- **Purpose**: User-created scenarios, characters, and scripts
- **Management**: Created and managed by users through Script Creator module
- **Visibility**: Private to user by default (sharing TBD)

## Resource Loading Strategy

### Current Implementation
```python
# ResourceLoader loads from a single base path
loader = ResourceLoader(storage, base_prefix="resources/")
scenarios = await loader.get_scenarios(language="en")
```

### Future Multi-Source Loading (TBD)
Several approaches to consider:

#### Option 1: Merged Resource Lists
```python
# Load base resources and user resources, merge them
base_scenarios = await loader.get_base_scenarios()
user_scenarios = await loader.get_user_scenarios(user_id)
all_scenarios = base_scenarios + user_scenarios
```

#### Option 2: Layered Resource Loading
```python
# User resources override/extend base resources
loader = LayeredResourceLoader(storage, user_id)
# Automatically checks user resources first, falls back to base
scenarios = await loader.get_scenarios()
```

#### Option 3: Explicit Source Selection
```python
# User explicitly chooses resource source
scenarios = await loader.get_scenarios(source="base")
scenarios = await loader.get_scenarios(source="user")
scenarios = await loader.get_scenarios(source="all")
```

## Resource Lifecycle

### User Onboarding
When a new user is created:
1. User directory structure created: `/users/{user_id}/resources/`
2. No automatic copying of base resources (avoid storage duplication)
3. User starts with empty personal library
4. Can browse and use base resources immediately

### Script Creator Workflow (Future)
1. User creates new scenario/character in Script Creator
2. Saved to user's personal resource directory
3. Can reference/extend base resources
4. Can export/share resources (future feature)

## Storage Structure
```
storage/
├── resources/                    # Base resources
│   ├── scenarios/
│   │   ├── scenarios.json
│   │   └── scenarios_zh-TW.json
│   └── characters/
│       ├── characters.json
│       └── characters_zh-TW.json
└── users/
    └── {user_id}/
        ├── resources/           # User-created resources
        │   ├── scenarios/
        │   └── characters/
        ├── chat_logs/
        └── eval_reports/
```

## Implementation TODOs

### Phase 1: Base Resource Management (Current)
- [x] Implement ResourceLoader for base resources
- [x] Support multiple storage backends (File/GCS/S3)
- [x] Language-specific resource loading
- [ ] Add resource versioning/update mechanism
- [ ] Implement resource validation on upload

### Phase 2: User Resource Support
- [ ] Design LayeredResourceLoader or multi-source loader
- [ ] Update API to distinguish base vs user resources
- [ ] Implement resource ownership and permissions
- [ ] Add resource metadata (created_at, updated_at, author)
- [ ] Design resource sharing mechanism

### Phase 3: Script Creator Integration
- [ ] Create Script Creator module
- [ ] Implement resource creation/editing APIs
- [ ] Add resource templates and wizards
- [ ] Implement resource import/export
- [ ] Add collaborative editing support

## API Design Considerations

### Current API
```
GET /api/chat/content/scenarios?language=en
GET /api/chat/content/scenarios/{id}/characters?language=en
```

### Future API (with user resources)
```
# Explicit source parameter
GET /api/content/scenarios?language=en&source=all
GET /api/content/scenarios?language=en&source=base
GET /api/content/scenarios?language=en&source=user

# Or separate endpoints
GET /api/content/base/scenarios
GET /api/content/user/scenarios
GET /api/content/shared/scenarios  # Future: shared resources
```

## Security Considerations
- User resources must be access-controlled
- Validate user ownership before serving user resources
- Sanitize user-created content before storage
- Implement resource size limits
- Rate limit resource creation

## Performance Considerations
- Cache base resources aggressively (rarely change)
- Cache user resources with shorter TTL
- Consider CDN for base resources
- Implement pagination for large resource lists
- Use database for resource metadata (future)

## Migration Path
1. Current: All resources are "base" resources in `/resources/`
2. Phase 1: Add user resource directories, update ResourceLoader
3. Phase 2: Implement Script Creator with user resource support
4. Phase 3: Add sharing, collaboration, marketplace features

## Open Questions
1. Should users be able to modify/extend base resources?
2. How to handle resource versioning and updates?
3. Resource sharing: public/private/group visibility?
4. Should we implement resource templates?
5. How to handle resource dependencies (character requires specific scenario)?