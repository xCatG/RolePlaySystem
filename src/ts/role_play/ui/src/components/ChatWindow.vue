<template>
  <div class="chat-window">
    <div class="chat-header">
      <h3>{{ session.participant_name }}'s Session</h3>
      <div class="header-actions">
        <button @click="exportChat" class="secondary-button">Export</button>
        <button @click="$emit('close')" class="secondary-button">Close</button>
      </div>
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
          <strong>{{ message.role === 'user' ? session.participant_name : 'Character' }}:</strong>
          <span class="timestamp">{{ formatTimestamp(message.timestamp) }}</span>
        </div>
        <div class="message-content">{{ message.content }}</div>
      </div>
      <div v-if="loading" class="loading-indicator">
        <span>Character is typing...</span>
      </div>
    </div>

    <div class="input-container">
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
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, nextTick, PropType } from 'vue';
import { chatApi } from '../services/chatApi';
import type { Session, Message } from '../types/chat';

export default defineComponent({
  name: 'ChatWindow',
  props: {
    session: {
      type: Object as PropType<Session>,
      required: true
    }
  },
  emits: ['close'],
  setup(props) {
    const messages = ref<Message[]>([]);
    const newMessage = ref('');
    const loading = ref(false);
    const messagesContainer = ref<HTMLElement>();

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
        role: 'user',
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
          role: 'assistant',
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

    return {
      messages,
      newMessage,
      loading,
      messagesContainer,
      sendMessage,
      exportChat,
      formatTimestamp
    };
  }
});
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 600px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
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

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
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
  padding: 10px 15px;
  border-radius: 8px;
  max-width: 70%;
}

.message.user {
  background: #007bff;
  color: white;
  margin-left: auto;
  text-align: right;
}

.message.assistant {
  background: #e9ecef;
  color: #212529;
  margin-right: auto;
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
  gap: 10px;
}

.message-input {
  flex: 1;
  padding: 10px 15px;
  border: 1px solid #ced4da;
  border-radius: 20px;
  font-size: 16px;
  outline: none;
  transition: border-color 0.2s;
}

.message-input:focus {
  border-color: #007bff;
}

.send-button {
  background: #007bff;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 20px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.2s;
}

.send-button:hover:not(:disabled) {
  background: #0056b3;
}

.send-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>