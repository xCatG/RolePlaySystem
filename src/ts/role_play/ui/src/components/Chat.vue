<template>
  <div class="chat-container">
    <div v-if="!activeSession" class="session-setup">
      <h2>{{ $t('chat.startSession') }}</h2>
      
      <div class="form-group">
        <label>{{ $t('chat.selectScenario') }}:</label>
        <select v-model="selectedScenarioId" @change="onScenarioChange">
          <option value="">-- {{ $t('chat.selectScenario') }} --</option>
          <option v-for="scenario in scenarios" :key="scenario.id" :value="scenario.id">
            {{ scenario.name }}
          </option>
        </select>
      </div>

      <div v-if="selectedScenarioId" class="scenario-details">
        <p>{{ selectedScenario?.description }}</p>
      </div>

      <div v-if="characters.length > 0" class="form-group">
        <label>{{ $t('chat.selectCharacter') }}:</label>
        <select v-model="selectedCharacterId">
          <option value="">-- {{ $t('chat.selectCharacter') }} --</option>
          <option v-for="character in characters" :key="character.id" :value="character.id">
            {{ character.name }}
          </option>
        </select>
      </div>

      <div v-if="selectedCharacterId" class="form-group">
        <label>{{ $t('auth.username') }}:</label>
        <input v-model="participantName" type="text" :placeholder="$t('auth.username')" />
      </div>

      <div v-if="selectedCharacterId" class="form-group">
        <label>Chat Mode:</label>
        <select v-model="chatMode">
          <option value="standard">Standard Chat</option>
          <option value="visual-novel">Visual Novel</option>
        </select>
      </div>

      <button 
        @click="startSession" 
        :disabled="!canStartSession"
        class="primary-button"
      >
        {{ $t('chat.startSession') }}
      </button>

      <div v-if="sessions.length > 0" class="existing-sessions">
        <h3>{{ $t('chat.continueExistingSession') }}</h3>
        <ul>
          <li v-for="session in sessions" :key="session.session_id">
            <button @click="loadSession(session)" class="session-link">
              {{ getSessionLabel(session) }}
            </button>
          </li>
        </ul>
      </div>
      
      <!-- Error message with internationalization -->
      <div v-if="error" class="error-message">{{ error }}</div>
    </div>

    <div v-else>
      <VisualNovelChat
        v-if="chatMode === 'visual-novel'"
        :session="activeSession"
        @close="closeSession"
      />
      
      <ChatWindow
        v-else
        :session="activeSession"
        @close="closeSession"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { chatApi } from '../services/chatApi';
import ChatWindow from './ChatWindow.vue';
import VisualNovelChat from './visualNovel/VisualNovelChat.vue';
import type { ScenarioInfo, CharacterInfo, SessionInfo, CreateSessionResponse } from '../types/chat';

export default defineComponent({
  name: 'Chat',
  components: {
    ChatWindow,
    VisualNovelChat
  },
  setup() {
    const { locale, t } = useI18n();
    
    const scenarios = ref<ScenarioInfo[]>([]);
    const characters = ref<CharacterInfo[]>([]);
    const sessions = ref<SessionInfo[]>([]);
    const selectedScenarioId = ref('');
    const selectedCharacterId = ref('');
    const participantName = ref('');
    const chatMode = ref<'standard' | 'visual-novel'>('standard');
    const activeSession = ref<SessionInfo | null>(null);
    const loading = ref(false);
    const error = ref('');

    const currentLanguage = computed(() => locale.value);

    const selectedScenario = computed(() => 
      scenarios.value.find(s => s.id === selectedScenarioId.value)
    );

    const canStartSession = computed(() => 
      selectedScenarioId.value && 
      selectedCharacterId.value && 
      participantName.value.trim()
    );

    const loadInitialData = async () => {
      try {
        loading.value = true;
        error.value = '';
        const [scenariosData, sessionsData] = await Promise.all([
          chatApi.getScenarios(currentLanguage.value),
          chatApi.getSessions()
        ]);
        scenarios.value = scenariosData;
        sessions.value = sessionsData;
      } catch (err) {
        error.value = t('errors.loadScenariosFailed');
        console.error(err);
      } finally {
        loading.value = false;
      }
    };

    const onScenarioChange = async () => {
      selectedCharacterId.value = '';
      characters.value = [];
      
      if (selectedScenarioId.value) {
        try {
          error.value = '';
          characters.value = await chatApi.getCharacters(selectedScenarioId.value, currentLanguage.value);
        } catch (err) {
          error.value = t('errors.loadCharactersFailed');
          console.error(err);
        }
      }
    };

    const startSession = async () => {
      try {
        loading.value = true;
        error.value = '';
        const createResponse = await chatApi.createSession({
          scenario_id: selectedScenarioId.value,
          character_id: selectedCharacterId.value,
          participant_name: participantName.value
        });
        
        // Convert CreateSessionResponse to SessionInfo for consistent UI handling
        const sessionInfo: SessionInfo = {
          session_id: createResponse.session_id,
          scenario_id: createResponse.scenario_id,
          scenario_name: createResponse.scenario_name,
          character_id: createResponse.character_id,
          character_name: createResponse.character_name,
          participant_name: participantName.value,
          created_at: new Date().toISOString(),
          message_count: 0,
          jsonl_filename: createResponse.jsonl_filename
        };
        
        activeSession.value = sessionInfo;
      } catch (err) {
        error.value = t('errors.createSessionFailed');
        console.error(err);
      } finally {
        loading.value = false;
      }
    };

    const loadSession = (session: SessionInfo) => {
      activeSession.value = session;
    };

    const closeSession = () => {
      activeSession.value = null;
      loadInitialData(); // Refresh sessions list
    };

    const getSessionLabel = (session: SessionInfo) => {
      return `${session.participant_name} - ${session.scenario_name} (${new Date(session.created_at).toLocaleDateString()})`;
    };

    // Handle language changes from parent
    const handleLanguageChange = async () => {
      // Clear current selections
      selectedScenarioId.value = '';
      selectedCharacterId.value = '';
      characters.value = [];
      
      // Reload content for new language
      await loadInitialData();
    };

    onMounted(() => {
      loadInitialData();
    });

    return {
      scenarios,
      characters,
      sessions,
      selectedScenarioId,
      selectedCharacterId,
      participantName,
      chatMode,
      activeSession,
      loading,
      error,
      selectedScenario,
      canStartSession,
      onScenarioChange,
      startSession,
      loadSession,
      closeSession,
      getSessionLabel,
      handleLanguageChange
    };
  }
});
</script>

<style scoped>
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.session-setup {
  background: white;
  border-radius: 8px;
  padding: 30px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group select,
.form-group input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}

.scenario-details {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.primary-button {
  background: #007bff;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.primary-button:hover:not(:disabled) {
  background: #0056b3;
}

.primary-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.existing-sessions {
  margin-top: 40px;
  padding-top: 30px;
  border-top: 1px solid #eee;
}

.existing-sessions ul {
  list-style: none;
  padding: 0;
}

.existing-sessions li {
  margin-bottom: 10px;
}

.session-link {
  background: none;
  border: none;
  color: #007bff;
  cursor: pointer;
  text-decoration: underline;
  font-size: 16px;
  padding: 5px 0;
}

.session-link:hover {
  color: #0056b3;
}

.error-message {
  background: #f8d7da;
  color: #721c24;
  padding: 12px 16px;
  border-radius: 6px;
  margin-top: 20px;
  border: 1px solid #f5c6cb;
}
</style>