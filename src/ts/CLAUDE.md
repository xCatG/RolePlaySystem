# TypeScript/Frontend Implementation Guidelines

## Directory Rules
ONLY create TypeScript source code files under this directory.

## Modular Monolith Architecture

### Philosophy
- **Start Simple**: Single module with domain boundaries to minimize complexity
- **Built-in Seams**: Structure for future module splitting from day one
- **Progressive Complexity**: Split only when file count, team conflicts, or build time demands it

### Domain-Based Organization
```
src/ts/role_play/
├── types/          # Domain-separated types
│   ├── auth.ts     # Auth-specific types
│   ├── chat.ts     # Chat-specific types
│   ├── evaluation.ts
│   └── shared.ts   # Cross-domain types
├── services/       # API clients by domain
│   ├── auth-api.ts
│   ├── chat-api.ts
│   └── evaluation-api.ts
├── stores/         # Domain-specific state
│   ├── auth.ts
│   ├── chat.ts
│   └── evaluation.ts
├── components/     # Grouped by domain
│   ├── shared/     # Cross-domain components
│   ├── auth/
│   ├── chat/
│   └── evaluation/
└── views/          # Page-level components
    ├── auth/
    ├── chat/
    └── evaluation/
```

### Evolution Path
1. **Current**: All code in one module with domain folders
2. **Future**: Mechanical migration when needed:
   - Move domain folder to separate module
   - Update import paths only
   - No structural changes required

### Domain Boundaries
Each domain exports through `index.ts`:
```typescript
// auth/index.ts
export * from './components'
export * from './services'
export * from './stores'
export * from './types'
```

## Type Synchronization

### Backend Pydantic → Frontend TypeScript
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

### API Response Types
```typescript
interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: number;
}
```

## State Management

### Store Pattern
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

## API Integration

### Service Layer
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

### Token Management
```typescript
// Automatic token injection
fetch(url, {
  headers: {
    'Authorization': `Bearer ${authStore.token}`,
    'Content-Type': 'application/json'
  }
});
```

## Component Guidelines

### Domain Components
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

### Cross-Domain Integration
```typescript
// When chat needs to show user info
import { useAuthStore } from '@/stores/auth';
import { useChatStore } from '@/stores/chat';

const authStore = useAuthStore();
const chatStore = useChatStore();

// Access current user from auth domain
const currentUser = computed(() => authStore.user);
```

## Development Patterns

### Environment Variables
```typescript
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
```

### Error Handling
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

### WebSocket Integration (Future)
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

## Build & Development

### Vite Configuration
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

### Type Checking
```bash
npm run type-check  # Run TypeScript compiler without emit
```

## Internationalization (i18n)

### Vue i18n Setup
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

### Language Management
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

### Component Localization
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

### Language-Specific API Types
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