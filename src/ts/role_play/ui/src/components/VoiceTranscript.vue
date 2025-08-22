<template>
  <div class="voice-transcript">
    <!-- Transcript Display -->
    <div class="transcript-container" ref="transcriptContainer">
      <div class="transcript-content">
        <!-- Final transcript messages -->
        <div
          v-for="message in finalMessages"
          :key="message.id"
          :class="['message', `message--${message.role}`]"
        >
          <div class="message__header">
            <span class="message__role">{{ formatRole(message.role) }}</span>
            <span class="message__timestamp">{{ formatTimestamp(message.timestamp) }}</span>
            <span v-if="message.duration" class="message__duration">
              {{ formatDuration(message.duration) }}
            </span>
          </div>
          <div class="message__text">{{ message.text }}</div>
          <div v-if="message.isVoice" class="message__voice-indicator">
            <span class="voice-badge">🎤 Voice</span>
            <span v-if="message.confidence" class="confidence-score">
              {{ Math.round(message.confidence * 100) }}%
            </span>
          </div>
        </div>

        <!-- Partial transcript (live updates) -->
        <div
          v-if="partialMessage && partialMessage.text.trim()"
          :class="['message', 'message--partial', `message--${partialMessage.role}`]"
        >
          <div class="message__header">
            <span class="message__role">{{ formatRole(partialMessage.role) }}</span>
            <span class="message__status">{{ $t('chat.voice.speaking') }}</span>
          </div>
          <div class="message__text">
            {{ partialMessage.text }}
            <span 
              class="stability-indicator"
              :style="{ opacity: partialMessage.stability }"
              :title="`${$t('chat.voice.stability')}: ${Math.round((partialMessage.stability || 0) * 100)}%`"
            >
              ●
            </span>
          </div>
        </div>

        <!-- Typing indicator -->
        <div v-if="isProcessing" class="typing-indicator">
          <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="typing-text">{{ $t('chat.voice.processing') }}</span>
        </div>
      </div>
    </div>

    <!-- Voice Controls -->
    <div class="voice-controls">
      <button
        v-if="!isConnected"
        @click="connect"
        :disabled="isConnecting"
        class="voice-btn voice-btn--connect"
      >
        <span v-if="isConnecting">{{ $t('chat.voice.connecting') }}</span>
        <span v-else>{{ $t('chat.voice.connect') }}</span>
      </button>

      <template v-else>
        <!-- Recording Controls -->
        <div class="recording-controls">
          <button
            @click="toggleRecording"
            :class="['voice-btn', 'voice-btn--record', { 'voice-btn--recording': isRecording }]"
            :disabled="!canRecord"
          >
            <span v-if="isRecording">{{ $t('chat.voice.stop') }}</span>
            <span v-else>{{ $t('chat.voice.startRecording') }}</span>
          </button>

          <!-- Text Input Fallback -->
          <div class="text-input-fallback">
            <input
              v-model="textInput"
              @keyup.enter="sendText"
              :placeholder="$t('chat.voice.textFallback')"
              class="text-input"
            />
            <button 
              @click="sendText"
              :disabled="!textInput.trim()"
              class="voice-btn voice-btn--send"
            >
              {{ $t('chat.voice.send') }}
            </button>
          </div>
        </div>

        <!-- Session Controls -->
        <div class="session-controls">
          <button
            @click="disconnect"
            class="voice-btn voice-btn--disconnect"
          >
            {{ $t('chat.voice.disconnect') }}
          </button>
        </div>
      </template>
    </div>

    <!-- Connection Status -->
    <div v-if="connectionStatus" :class="['status-indicator', `status--${connectionStatus.type}`]">
      {{ connectionStatus.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTranscriptBuffer } from '../composables/useTranscriptBuffer'
import { useVoiceWebSocket } from '../composables/useVoiceWebSocket'
import type { TranscriptMessage, VoiceStatus } from '../types/voice'

// Component Props
interface Props {
  sessionId: string
  token: string
  autoConnect?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  autoConnect: false
})

// Composables
const { t } = useI18n()
const {
  finalMessages,
  partialMessage,
  addPartialTranscript,
  addFinalTranscript,
  clear
} = useTranscriptBuffer()

const {
  isConnected,
  isConnecting,
  isRecording,
  canRecord,
  connectionStatus,
  connect: connectWS,
  disconnect: disconnectWS,
  startRecording,
  stopRecording,
  sendTextMessage
} = useVoiceWebSocket({
  sessionId: props.sessionId,
  token: props.token,
  onPartialTranscript: addPartialTranscript,
  onFinalTranscript: addFinalTranscript,
  onStatusChange: (status: VoiceStatus) => {
    console.log('Voice status:', status)
  }
})

// Local state
const textInput = ref('')
const isProcessing = ref(false)
const transcriptContainer = ref<HTMLElement>()

// Methods
const connect = async () => {
  try {
    await connectWS()
  } catch (error) {
    console.error('Failed to connect:', error)
  }
}

const disconnect = async () => {
  await disconnectWS()
  clear()
}

const toggleRecording = async () => {
  if (isRecording.value) {
    await stopRecording()
  } else {
    await startRecording()
  }
}

const sendText = async () => {
  if (!textInput.value.trim()) return
  
  try {
    await sendTextMessage(textInput.value)
    textInput.value = ''
  } catch (error) {
    console.error('Failed to send text:', error)
  }
}

const formatRole = (role: string): string => {
  return role === 'user' ? t('chat.voice.you') : t('chat.voice.character')
}

const formatTimestamp = (timestamp: string): string => {
  return new Date(timestamp).toLocaleTimeString()
}

const formatDuration = (duration: number): string => {
  return `${(duration / 1000).toFixed(1)}s`
}

// Auto-scroll to bottom when new messages arrive
const scrollToBottom = async () => {
  await nextTick()
  if (transcriptContainer.value) {
    transcriptContainer.value.scrollTop = transcriptContainer.value.scrollHeight
  }
}

// Watch for new messages and scroll
const messageCount = computed(() => finalMessages.value.length)
watch(messageCount, scrollToBottom)
watch(() => partialMessage.value?.text, scrollToBottom)

// Lifecycle
onMounted(() => {
  if (props.autoConnect) {
    connect()
  }
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.voice-transcript {
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #ffffff;
}

.transcript-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  max-height: 400px;
}

.transcript-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
}

.message--user {
  background: #e3f2fd;
  margin-left: 20%;
  align-self: flex-end;
}

.message--assistant {
  background: #f5f5f5;
  margin-right: 20%;
  align-self: flex-start;
}

.message--partial {
  border: 2px dashed #2196f3;
  animation: pulse 2s infinite;
}

.message__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 0.85em;
  color: #666;
}

.message__role {
  font-weight: 600;
}

.message__timestamp {
  font-family: monospace;
}

.message__duration {
  font-size: 0.8em;
  background: #e0e0e0;
  padding: 2px 6px;
  border-radius: 12px;
}

.message__status {
  font-style: italic;
  color: #2196f3;
}

.message__text {
  font-size: 1em;
  line-height: 1.4;
  position: relative;
}

.message__voice-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 0.8em;
}

.voice-badge {
  background: #4caf50;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75em;
}

.confidence-score {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 8px;
  font-family: monospace;
}

.stability-indicator {
  color: #2196f3;
  font-weight: bold;
  animation: pulse 1s infinite;
  margin-left: 4px;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f9f9f9;
  border-radius: 8px;
  font-style: italic;
  color: #666;
}

.typing-dots {
  display: flex;
  gap: 4px;
}

.typing-dots span {
  width: 4px;
  height: 4px;
  background: #2196f3;
  border-radius: 50%;
  animation: typing-dots 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }

.voice-controls {
  padding: 16px;
  border-top: 1px solid #e0e0e0;
  background: #fafafa;
  border-radius: 0 0 8px 8px;
}

.recording-controls {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.text-input-fallback {
  display: flex;
  gap: 8px;
}

.text-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.9em;
}

.session-controls {
  display: flex;
  justify-content: flex-end;
}

.voice-btn {
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-size: 0.9em;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.voice-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.voice-btn--connect {
  background: #4caf50;
  color: white;
}

.voice-btn--connect:hover:not(:disabled) {
  background: #43a047;
}

.voice-btn--record {
  background: #2196f3;
  color: white;
}

.voice-btn--record:hover:not(:disabled) {
  background: #1976d2;
}

.voice-btn--recording {
  background: #f44336;
  animation: pulse 1.5s infinite;
}

.voice-btn--send {
  background: #2196f3;
  color: white;
}

.voice-btn--disconnect {
  background: #f44336;
  color: white;
}

.voice-btn--disconnect:hover {
  background: #d32f2f;
}

.status-indicator {
  padding: 8px 16px;
  font-size: 0.85em;
  border-top: 1px solid #e0e0e0;
}

.status--connected {
  background: #e8f5e8;
  color: #2e7d32;
}

.status--error {
  background: #ffebee;
  color: #c62828;
}

.status--connecting {
  background: #fff3e0;
  color: #f57c00;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

@keyframes typing-dots {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}
</style>