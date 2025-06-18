<template>
  <div class="chat-window">
    <div class="chat-header">
      <h3>{{ session.participant_name }}'s Session
        <span v-if="!session.is_active" class="read-only-indicator">(Read-Only)</span>
      </h3>
      <div class="header-actions">
        <button @click="exportChat" class="secondary-button">{{ $t('chat.exportText') }}</button>
        <button @click="sendToEvaluation" class="secondary-button">{{ $t('chat.sendToEvaluation') }}</button>
        <button v-if="session.is_active" 
                @click="endSession" 
                class="secondary-button end-session-button">
          {{ $t('chat.endSession') }}
        </button>
        <button v-if="!session.is_active"
                @click="deleteSession" 
                class="secondary-button delete-session-button">
          {{ $t('chat.deleteSession') }}
        </button>
        <button @click="$emit('close')" class="secondary-button">Close</button>
      </div>
    </div>
    
    <!-- Read-only banner for ended sessions -->
    <div v-if="!session.is_active" class="read-only-banner">
      <strong>{{ $t('chat.sessionEnded') }}</strong>
      <span v-if="session.ended_at"> - {{ formatDate(session.ended_at) }}</span>
      <span v-if="session.ended_reason"> ({{ session.ended_reason }})</span>
      <br>
      <small>This is a historical session. Messages are read-only.</small>
    </div>

    <div class="messages-container" ref="messagesContainer">
      <div v-if="messages.length === 0" class="no-messages">
        Start the conversation by sending a message below...
      </div>
      <div 
        v-for="(message, index) in messages" 
        :key="index"
        :class="['message', message.role]"
      >
        <div class="message-header">
          <strong>{{ message.role === 'participant' ? session.participant_name : session.character_name }}:</strong>
          <span class="timestamp">{{ formatTimestamp(message.timestamp) }}</span>
        </div>
        <div class="message-content">{{ message.content }}</div>
      </div>
      <div v-if="loading" class="loading-indicator">
        <span>Character is typing...</span>
      </div>
    </div>

    <!-- Hide input for ended sessions -->
    <div v-if="session.is_active" class="input-container">
      <form @submit.prevent="sendMessage">
        <input 
          v-model="newMessage"
          type="text"
          placeholder="Type your message..."
          :disabled="loading"
          class="message-input"
        />
        <button 
          type="submit"
          :disabled="!newMessage.trim() || loading"
          class="send-button"
        >
          Send
        </button>
      </form>
    </div>
    
    <!-- Evaluation Report -->
    <EvaluationReport
      v-if="showEvaluationReport"
      :report="evaluationReport"
      :loading="evaluationLoading"
      :error="evaluationError"
      :is-retrying="isRetrying"
      :retry-count="evaluationRetryCount"
      @close="showEvaluationReport = false"
      @retry="retryEvaluation"
    />
    
    <!-- End Session Confirmation Modal -->
    <ConfirmModal
      v-model="showEndModal"
      :message="$t('chat.confirmEndSession')"
      :title="$t('chat.endSession')"
      :confirm-text="$t('warnings.confirm')"
      :cancel-text="$t('warnings.cancel')"
      @confirm="confirmEndSession"
    />
    
    <!-- Delete Session Confirmation Modal -->
    <ConfirmModal
      v-model="showDeleteModal"
      :message="$t('chat.confirmDeleteSession')"
      :title="$t('chat.deleteSession')"
      :confirm-text="$t('warnings.confirm')"
      :cancel-text="$t('warnings.cancel')"
      @confirm="confirmDeleteSession"
    />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, nextTick, PropType, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { chatApi } from '../services/chatApi';
import { evaluationApi } from '../services/evaluationApi';
import type { SessionInfo, Message } from '../types/chat';
import type { FinalReviewReport } from '../types/evaluation';
import ConfirmModal from './ConfirmModal.vue';
import EvaluationReport from './EvaluationReport.vue';

export default defineComponent({
  name: 'ChatWindow',
  components: {
    ConfirmModal,
    EvaluationReport
  },
  props: {
    session: {
      type: Object as PropType<SessionInfo>,
      required: true
    }
  },
  emits: ['close', 'session-ended', 'session-deleted'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const messages = ref<Message[]>([]);
    const newMessage = ref('');
    const loading = ref(false);
    const messagesContainer = ref<HTMLElement>();
    const showDeleteModal = ref(false);
    const showEndModal = ref(false);
    const showEvaluationReport = ref(false);
    const evaluationReport = ref<FinalReviewReport | null>(null);
    const evaluationLoading = ref(false);
    const evaluationError = ref<string | null>(null);
    const evaluationRetryCount = ref(0);
    const isRetrying = ref(false);

    const scrollToBottom = () => {
      nextTick(() => {
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
        }
      });
    };

    const sendMessage = async () => {
      if (!newMessage.value.trim() || loading.value) return;

      const userMessage: Message = {
        role: 'participant',
        content: newMessage.value,
        timestamp: new Date().toISOString()
      };
      
      messages.value.push(userMessage);
      const messageText = newMessage.value;
      newMessage.value = '';
      scrollToBottom();

      try {
        loading.value = true;
        const response = await chatApi.sendMessage(props.session.session_id, { message: messageText });
        
        const assistantMessage: Message = {
          role: 'character',
          content: response.response,
          timestamp: new Date().toISOString()
        };
        
        messages.value.push(assistantMessage);
        scrollToBottom();
      } catch (error) {
        console.error('Failed to send message:', error);
        // In a real app, show error to user
      } finally {
        loading.value = false;
      }
    };

    const exportChat = async () => {
      try {
        const exportData = await chatApi.exportSession(props.session.session_id);
        // Create a blob and download
        const blob = new Blob([exportData], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-export-${props.session.session_id}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } catch (error) {
        console.error('Failed to export chat:', error);
      }
    };

    const formatTimestamp = (timestamp: string) => {
      return new Date(timestamp).toLocaleTimeString();
    };

    const getErrorMessage = (error: any): string => {
      // Log unexpected error structures for debugging
      if (!error.response && !error.message && !error.code) {
        console.error('Unexpected error structure:', error)
      }
      
      // Network errors (connection issues, timeouts)
      if (!navigator.onLine) {
        return t('evaluation.networkError');
      }
      
      // Handle Axios errors with response
      if (error.response) {
        const status = error.response.status
        
        // Server errors (5xx status codes)
        if (status >= 500) {
          return t('evaluation.serverError');
        }
        
        // Client errors (4xx status codes)
        if (status >= 400) {
          // Safely access nested response data
          const errorData = error.response.data
          if (errorData && typeof errorData === 'object') {
            const detail = errorData.error || errorData.message || errorData.detail
            if (detail && typeof detail === 'string') {
              return detail
            }
          }
          return t('evaluation.failed')
        }
      }
      
      // Network timeout or connection refused
      if (error.code === 'NETWORK_ERROR' || 
          error.code === 'TIMEOUT' || 
          error.code === 'ECONNREFUSED' ||
          !error.response) {
        return t('evaluation.networkError');
      }
      
      // Handle error message strings
      if (error.message && typeof error.message === 'string') {
        // Check if it's a network-related error
        const msg = error.message.toLowerCase()
        if (msg.includes('network') || 
            msg.includes('fetch') ||
            msg.includes('timeout') ||
            msg.includes('connection')) {
          return t('evaluation.networkError');
        }
        return error.message;
      }
      
      // Fallback to localized generic error
      return t('evaluation.failed');
    };

    const performEvaluation = async (): Promise<void> => {
      try {
        const response = await evaluationApi.evaluateSession(props.session.session_id);
        if (response.success && (response.report || response.final_review_report)) {
          evaluationReport.value = response.report || response.final_review_report!;
          evaluationError.value = null;
          evaluationRetryCount.value = 0; // Reset retry count on success
        } else {
          throw new Error(response.error || response.message || t('evaluation.failed'));
        }
      } catch (error: any) {
        console.error('Failed to evaluate session:', error);
        evaluationError.value = getErrorMessage(error);
        throw error; // Re-throw to be handled by caller
      }
    };

    const sendToEvaluation = async () => {
      evaluationError.value = null;
      evaluationReport.value = null;
      showEvaluationReport.value = true;
      evaluationLoading.value = true;
      isRetrying.value = false;
      
      try {
        await performEvaluation();
      } catch (error) {
        // Error is already handled in performEvaluation
      } finally {
        evaluationLoading.value = false;
      }
    };

    const retryEvaluation = async () => {
      // Disable retry if limit reached
      if (evaluationRetryCount.value >= 3) {
        evaluationError.value = t('evaluation.failed') + ' (Max retries reached)';
        return;
      }

      evaluationRetryCount.value++;
      evaluationError.value = null;
      evaluationLoading.value = true;
      isRetrying.value = true;
      
      // Add a small delay before retrying for better UX
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      try {
        await performEvaluation();
      } catch (error) {
        // Error is already handled in performEvaluation
      } finally {
        evaluationLoading.value = false;
        isRetrying.value = false;
      }
    };

    const formatDate = (dateString: string) => {
      return new Date(dateString).toLocaleString();
    };

    const loadMessageHistory = async () => {
      if (!props.session.is_active) {
        try {
          loading.value = true;
          const historyMessages = await chatApi.getSessionMessages(props.session.session_id);
          messages.value = historyMessages;
          scrollToBottom();
        } catch (error) {
          console.error('Failed to load message history:', error);
        } finally {
          loading.value = false;
        }
      }
    };

    const endSession = () => {
      showEndModal.value = true;
    };

    const confirmEndSession = async () => {
      try {
        loading.value = true;
        await chatApi.endSession(props.session.session_id);
        showEndModal.value = false;
        // Emit event to parent to refresh session list
        emit('session-ended');
      } catch (error) {
        console.error('Failed to end session:', error);
      } finally {
        loading.value = false;
      }
    };

    const deleteSession = () => {
      showDeleteModal.value = true;
    };

    const confirmDeleteSession = async () => {
      try {
        loading.value = true;
        await chatApi.deleteSession(props.session.session_id);
        showDeleteModal.value = false;
        // Emit event to parent to refresh and close
        emit('session-deleted');
      } catch (error) {
        console.error('Failed to delete session:', error);
      } finally {
        loading.value = false;
      }
    };

    onMounted(() => {
      loadMessageHistory();
    });

    return {
      messages,
      newMessage,
      loading,
      messagesContainer,
      showDeleteModal,
      showEndModal,
      showEvaluationReport,
      evaluationReport,
      evaluationLoading,
      evaluationError,
      isRetrying,
      sendMessage,
      exportChat,
      sendToEvaluation,
      retryEvaluation,
      endSession,
      confirmEndSession,
      deleteSession,
      confirmDeleteSession,
      formatTimestamp,
      formatDate
    };
  }
});
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
  min-height: 400px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  max-width: 100%;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.chat-header h3 {
  margin: 0;
}

.read-only-indicator {
  font-size: 0.8em;
  color: #6c757d;
  font-weight: normal;
}

.read-only-banner {
  background: #fff3cd;
  border: 1px solid #ffeaa7;
  color: #856404;
  padding: 12px 20px;
  border-top: none;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.secondary-button {
  background: #6c757d;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.secondary-button:hover {
  background: #5a6268;
}

.end-session-button:hover {
  background: #ffc107;
  color: #212529;
}

.delete-session-button {
  background: #dc3545;
}

.delete-session-button:hover {
  background: #c82333;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background: #fafafa;
}

.no-messages {
  text-align: center;
  color: #6c757d;
  font-style: italic;
  padding: 40px;
}

.message {
  margin-bottom: 15px;
  padding: 10px 12px;
  border-radius: 8px;
  max-width: 85%;
}

.message.participant {
  background: #007bff;
  color: white;
  margin-left: auto;
  text-align: right;
}

.message.character {
  background: #e9ecef;
  color: #212529;
  margin-right: auto;
}

.message.system {
  background: #f8f9fa;
  color: #6c757d;
  margin: 0 auto;
  text-align: center;
  font-style: italic;
}

.message-header {
  font-size: 12px;
  margin-bottom: 5px;
  opacity: 0.8;
}

.message-header strong {
  margin-right: 10px;
}

.timestamp {
  font-size: 11px;
}

.message-content {
  white-space: pre-wrap;
  word-wrap: break-word;
}

.loading-indicator {
  text-align: center;
  color: #6c757d;
  font-style: italic;
  padding: 10px;
}

.input-container {
  padding: 15px;
  background: white;
  border-top: 1px solid #e9ecef;
}

.input-container form {
  display: flex;
  gap: 12px;
  align-items: stretch;
}

.message-input {
  flex: 1;
  min-width: 0;
  padding: 12px 16px;
  border: 1px solid #ced4da;
  border-radius: 8px;
  font-size: 16px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  background: white;
}

.message-input:focus {
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}

.send-button {
  background: #007bff;
  color: white;
  border: none;
  padding: 12px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
  white-space: nowrap;
  flex-shrink: 0;
  width: 70px;
}

.send-button:hover:not(:disabled) {
  background: #0056b3;
}

.send-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

/* Mobile-first: Full width on very small screens */
@media (max-width: 480px) {
  .chat-window {
    border-radius: 0;
    box-shadow: none;
    margin: 0;
    height: calc(100vh - 100px);
    max-height: calc(100vh - 100px);
    min-height: calc(100vh - 100px);
  }
  
  .messages-container {
    padding: 8px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
  
  .input-container {
    padding: 12px;
    flex-shrink: 0;
    background: white;
    border-top: 1px solid #e9ecef;
  }
  
  .message {
    max-width: 90%;
    padding: 8px 10px;
  }
}

/* Responsive Styles */
@media (min-width: 768px) {
  .chat-window {
    height: 600px;
  }
  
  .message {
    max-width: 60%;
  }
  
  .input-container {
    padding: 20px;
  }
  
  .input-container form {
    gap: 16px;
  }
  
  .message-input {
    padding: 14px 18px;
  }
  
  .send-button {
    padding: 14px 20px;
    width: 80px;
  }
}

@media (min-width: 1024px) {
  .chat-window {
    height: 700px;
  }
  
  .message {
    max-width: 75%;
  }
  
  .messages-container {
    padding: 30px;
  }
  
  .input-container {
    padding: 24px;
  }
}
</style>