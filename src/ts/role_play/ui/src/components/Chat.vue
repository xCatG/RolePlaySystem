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

      <button 
        @click="startSession" 
        :disabled="!canStartSession"
        class="primary-button"
      >
        {{ $t('chat.startSession') }}
      </button>

      <div v-if="sessions.length > 0" class="existing-sessions">
        <h3>{{ $t('chat.continueExistingSession') }}</h3>
        <div class="sessions-list-container">
          <ul class="sessions-list">
            <li v-for="session in sessions" :key="session.session_id" 
                :class="{ 'session-ended': !session.is_active }"
                class="session-item">
              <button @click="loadSession(session)" 
                      :class="['session-link', { 'ended': !session.is_active }]">
                {{ getSessionLabel(session) }}
                <span v-if="!session.is_active" class="session-status-badge">
                  {{ $t('chat.sessionEnded') }}
                </span>
              </button>
              <div class="session-actions">
                <button v-if="session.is_active" 
                        @click="endSession(session.session_id)" 
                        class="action-button end-button"
                        :title="$t('chat.endSession')">
                  📝
                </button>
                <button @click="deleteSession(session.session_id)" 
                        class="action-button delete-button"
                        :title="$t('chat.deleteSession')">
                  🗑️
                </button>
              </div>
            </li>
          </ul>
        </div>
      </div>
      
      <!-- Error message with internationalization -->
      <div v-if="error" class="error-message">{{ error }}</div>
    </div>

    <ChatWindow 
      v-else 
      :session="activeSession"
      @close="closeSession"
      @session-ended="handleSessionEnded"
      @session-deleted="handleSessionDeleted"
    />
    
    <!-- Delete Confirmation Modal -->
    <ConfirmModal
      v-model="showDeleteModal"
      :message="$t('chat.confirmDeleteSession')"
      :title="$t('chat.deleteSession')"
      :confirm-text="$t('warnings.confirm')"
      :cancel-text="$t('warnings.cancel')"
      @confirm="confirmDeleteSession"
      @cancel="cancelDeleteSession"
    />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { chatApi } from '../services/chatApi';
import ChatWindow from './ChatWindow.vue';
import ConfirmModal from './ConfirmModal.vue';
import type { ScenarioInfo, CharacterInfo, SessionInfo, CreateSessionResponse } from '../types/chat';

export default defineComponent({
  name: 'Chat',
  components: {
    ChatWindow,
    ConfirmModal
  },
  setup() {
    const { locale, t } = useI18n();
    
    const scenarios = ref<ScenarioInfo[]>([]);
    const characters = ref<CharacterInfo[]>([]);
    const sessions = ref<SessionInfo[]>([]);
    const selectedScenarioId = ref('');
    const selectedCharacterId = ref('');
    const participantName = ref('');
    const activeSession = ref<SessionInfo | null>(null);
    const loading = ref(false);
    const error = ref('');
    const showDeleteModal = ref(false);
    const sessionToDelete = ref<string | null>(null);

    const currentLanguage = computed(() => locale.value);

    const selectedScenario = computed(() => 
      scenarios.value.find(s => s.id === selectedScenarioId.value)
    );

    const canStartSession = computed(() => 
      selectedScenarioId.value && 
      selectedCharacterId.value && 
      participantName.value.trim()
    );

    const refreshData = async () => {
      try {
        loading.value = true;
        error.value = '';
        const [scenariosResponse, sessionsResponse] = await Promise.all([
          chatApi.getScenarios(currentLanguage.value),
          chatApi.getSessions()
        ]);
        scenarios.value = scenariosResponse || [];
        sessions.value = sessionsResponse || [];
      } catch (err) {
        error.value = t('errors.loadScenariosFailed');
        console.error(err);
      } finally {
        loading.value = false;
      }
    };

    const loadCharacters = async (scenarioId: string) => {
      if (!scenarioId) {
        characters.value = [];
        return;
      }
      
      try {
        error.value = '';
        const response = await chatApi.getCharacters(scenarioId, currentLanguage.value);
        characters.value = response || [];
      } catch (err) {
        error.value = t('errors.loadCharactersFailed');
        console.error(err);
      }
    };

    const onScenarioChange = async () => {
      selectedCharacterId.value = '';
      await loadCharacters(selectedScenarioId.value);
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
          scenario_name: createResponse.scenario_name,
          character_name: createResponse.character_name,
          participant_name: participantName.value,
          created_at: new Date().toISOString(),
          message_count: 0,
          jsonl_filename: createResponse.jsonl_filename,
          is_active: true,
          ended_at: null,
          ended_reason: null
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
      refreshData(); // Refresh sessions list
    };

    const handleSessionEnded = () => {
      // Session was ended from ChatWindow, refresh data and update current session
      refreshData();
      if (activeSession.value) {
        // Update the current session to reflect it's now ended
        activeSession.value.is_active = false;
        activeSession.value.ended_at = new Date().toISOString();
        activeSession.value.ended_reason = "User ended session";
      }
    };

    const handleSessionDeleted = () => {
      // Session was deleted from ChatWindow, close and refresh
      activeSession.value = null;
      refreshData();
    };

    const getSessionLabel = (session: SessionInfo) => {
      // Format UTC timestamps to local date and time
      const createdDateTime = new Date(session.created_at).toLocaleString();
      if (!session.is_active && session.ended_at) {
        const endedDateTime = new Date(session.ended_at).toLocaleString();
        return `${session.participant_name} - ${session.scenario_name} (Created: ${createdDateTime}, Ended: ${endedDateTime})`;
      }
      return `${session.participant_name} - ${session.scenario_name} (${createdDateTime})`;
    };

    const endSession = async (sessionId: string) => {
      try {
        loading.value = true;
        error.value = '';
        await chatApi.endSession(sessionId);
        
        // Refresh sessions list
        await refreshData();
      } catch (err) {
        error.value = t('errors.endSessionFailed');
        console.error(err);
      } finally {
        loading.value = false;
      }
    };

    const deleteSession = (sessionId: string) => {
      sessionToDelete.value = sessionId;
      showDeleteModal.value = true;
    };

    const confirmDeleteSession = async () => {
      if (!sessionToDelete.value) return;
      
      try {
        loading.value = true;
        error.value = '';
        await chatApi.deleteSession(sessionToDelete.value);
        
        // Refresh sessions list
        await refreshData();
      } catch (err) {
        error.value = 'Failed to delete session';
        console.error(err);
      } finally {
        loading.value = false;
        showDeleteModal.value = false;
        sessionToDelete.value = null;
      }
    };

    const cancelDeleteSession = () => {
      showDeleteModal.value = false;
      sessionToDelete.value = null;
    };

    // Handle language changes from parent
    const handleLanguageChange = async () => {
      // Clear current selections
      selectedScenarioId.value = '';
      selectedCharacterId.value = '';
      characters.value = [];
      
      // Reload content for new language
      await refreshData();
    };

    onMounted(() => {
      refreshData();
    });

    return {
      scenarios,
      characters,
      sessions,
      selectedScenarioId,
      selectedCharacterId,
      participantName,
      activeSession,
      loading,
      error,
      showDeleteModal,
      selectedScenario,
      canStartSession,
      onScenarioChange,
      startSession,
      loadSession,
      closeSession,
      endSession,
      deleteSession,
      confirmDeleteSession,
      cancelDeleteSession,
      handleSessionEnded,
      handleSessionDeleted,
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

.sessions-list-container {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  background: #f8f9fa;
}

.sessions-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid #e9ecef;
  background: white;
  margin-bottom: 0;
}

.session-item:last-child {
  border-bottom: none;
}

.session-item:hover {
  background: #f8f9fa;
}

.session-link {
  background: none;
  border: none;
  color: #007bff;
  cursor: pointer;
  text-decoration: underline;
  font-size: 14px;
  padding: 5px 0;
  text-align: left;
  flex: 1;
  margin-right: 10px;
}

.session-link:hover {
  color: #0056b3;
}

.session-link.ended {
  color: #6c757d;
  opacity: 0.7;
}

.session-link.ended:hover {
  color: #5a6268;
}

.session-ended {
  opacity: 0.8;
}

.session-status-badge {
  display: inline-block;
  background: #6c757d;
  color: white;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 12px;
  margin-left: 8px;
  font-weight: normal;
}

.session-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.action-button {
  background: none;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  min-width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-button:hover {
  background: #f8f9fa;
  border-color: #adb5bd;
}

.end-button:hover {
  background: #fff3cd;
  border-color: #ffeaa7;
}

.delete-button:hover {
  background: #f8d7da;
  border-color: #f5c6cb;
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