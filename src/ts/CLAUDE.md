# TypeScript/Frontend Implementation Guidelines

## Directory Rules
ONLY create TypeScript source code files under this directory.

## Architecture Overview

### Current Structure
- **Domain-Based Organization**: Separated by feature (auth/, chat/, evaluation/)
- **Composable Patterns**: Reusable Vue composables for common workflows
- **Type Safety**: Full TypeScript with backend Pydantic model sync

### Domain Organization
```
src/ts/role_play/
├── types/          # TypeScript interfaces
├── services/       # API clients
├── composables/    # Reusable Vue logic
├── components/     # UI components by domain
└── views/          # Page-level components
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

## Composable Patterns

### Reusable Vue Composables
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

## Evaluation System Integration

### Evaluation API Types
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

### Evaluation Service Implementation
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

### Smart Report Loading Pattern
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

### Re-evaluation UI Pattern
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