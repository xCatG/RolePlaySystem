<template>
  <div class="visual-novel-container">
    <!-- Layer 1: Background -->
    <BackgroundRenderer 
      :scenario-id="scenarioId"
      :transition="currentTransition"
      :show-time-effect="true"
    />
    
    <!-- Layer 2: Characters -->
    <div class="character-layer">
      <CharacterSprite
        v-for="character in vnStore.allCharacters"
        :key="character.character_id"
        :character="character"
        :is-speaking="isSpeaking(character.character_id)"
      />
    </div>
    
    <!-- Layer 3: Effects (placeholder for future) -->
    <div class="effects-layer">
      <!-- Particle effects, screen overlays, etc. -->
    </div>
    
    <!-- Layer 4: UI -->
    <div class="ui-layer">
      <TextDisplay :config="typewriterConfig" />
      
      <!-- Input controls -->
      <div v-if="showInput" class="input-controls">
        <input
          v-model="userInput"
          @keyup.enter="sendMessage"
          class="message-input"
          placeholder="Type your message..."
          :disabled="!canSendMessage"
        />
        <button 
          @click="sendMessage"
          class="send-button"
          :disabled="!canSendMessage"
        >
          Send
        </button>
      </div>
    </div>
    
    <!-- History overlay -->
    <transition name="slide-up">
      <div v-if="vnStore.ui.showHistory" class="history-overlay">
        <div class="history-header">
          <h2>Message History</h2>
          <button @click="vnStore.toggleHistory" class="close-button">×</button>
        </div>
        <div class="history-content">
          <div
            v-for="msg in vnStore.textDisplay.history"
            :key="msg.id"
            class="history-message"
          >
            <div class="history-character">{{ getCharacterName(msg) }}</div>
            <div class="history-text">{{ msg.content }}</div>
          </div>
        </div>
      </div>
    </transition>
    
    <!-- Settings overlay -->
    <transition name="fade">
      <div v-if="vnStore.ui.showSettings" class="settings-overlay">
        <div class="settings-panel">
          <div class="settings-header">
            <h2>Settings</h2>
            <button @click="vnStore.toggleSettings" class="close-button">×</button>
          </div>
          <div class="settings-content">
            <div class="setting-item">
              <label>Text Speed</label>
              <input
                type="range"
                min="10"
                max="100"
                v-model.number="vnStore.ui.textSpeed"
                @input="vnStore.setTextSpeed($event.target.value)"
              />
              <span>{{ vnStore.ui.textSpeed }} chars/sec</span>
            </div>
            
            <div class="setting-item">
              <label>BGM Volume</label>
              <input
                type="range"
                min="0"
                max="100"
                :value="vnStore.audio.bgmVolume * 100"
                @input="vnStore.setVolume('bgm', $event.target.value / 100)"
              />
              <span>{{ Math.round(vnStore.audio.bgmVolume * 100) }}%</span>
            </div>
            
            <div class="setting-item">
              <label>Voice Volume</label>
              <input
                type="range"
                min="0"
                max="100"
                :value="vnStore.audio.voiceVolume * 100"
                @input="vnStore.setVolume('voice', $event.target.value / 100)"
              />
              <span>{{ Math.round(vnStore.audio.voiceVolume * 100) }}%</span>
            </div>
            
            <div class="setting-item">
              <label>SFX Volume</label>
              <input
                type="range"
                min="0"
                max="100"
                :value="vnStore.audio.sfxVolume * 100"
                @input="vnStore.setVolume('sfx', $event.target.value / 100)"
              />
              <span>{{ Math.round(vnStore.audio.sfxVolume * 100) }}%</span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useVisualNovelStore } from '../../stores/visualNovel';
import { chatApi } from '../../services/chatApi';
import { AssetManager } from '../../services/assetManager';
import BackgroundRenderer from './BackgroundRenderer.vue';
import CharacterSprite from './CharacterSprite.vue';
import TextDisplay from './TextDisplay.vue';
import type { SessionInfo, ChatMessageResponse, VisualNovelMessage } from '../../types/chat';

const props = defineProps<{
  session: SessionInfo;
}>();

const emit = defineEmits<{
  close: [];
}>();

const vnStore = useVisualNovelStore();
const assetManager = AssetManager.getInstance();

const userInput = ref('');
const showInput = ref(true);
const isLoading = ref(false);
const currentSpeakerId = ref<string>('');

const scenarioId = computed(() => {
  // Scenario ID is now provided directly by the session
  return props.session.scenario_id;
});

const currentTransition = computed(() => {
  return vnStore.textDisplay.currentMessage?.scene_state?.transition || 'fade';
});

const typewriterConfig = computed(() => ({
  baseSpeed: vnStore.ui.textSpeed,
  punctuationDelay: 300,
  instantOnClick: true,
  soundEffect: undefined // TODO: Add typing sound effect
}));

const canSendMessage = computed(() => {
  return userInput.value.trim() && !isLoading.value && !vnStore.textDisplay.isTyping;
});

const isSpeaking = (characterId: string) => {
  return currentSpeakerId.value === characterId && vnStore.audio.voicePlaying;
};

const getCharacterName = (message: VisualNovelMessage) => {
  if (message.role === 'user') return props.session.participant_name;
  return message.character_state?.character_id || 'Character';
};

const sendMessage = async () => {
  if (!canSendMessage.value) return;
  
  const message = userInput.value.trim();
  userInput.value = '';
  isLoading.value = true;
  
  try {
    // Add user message to display
    const userMessage: VisualNovelMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    };
    vnStore.setMessage(userMessage);
    
    // Send to server
    const response: ChatMessageResponse = await chatApi.sendMessage(
      props.session.session_id,
      { message }
    );
    
    // Create visual novel message from response
    // TODO: This should come from enhanced API response
    const vnMessage: VisualNovelMessage = {
      id: `assistant_${Date.now()}`,
      role: 'assistant',
      content: response.response,
      timestamp: new Date().toISOString(),
      character_state: {
        character_id: props.session.character_name,
        pose: 'standing_neutral',
        expression: 'neutral',
        position: 'center'
      },
      scene_state: {
        background: 'default',
        time_of_day: 'day'
      }
    };
    
    // Update current speaker
    currentSpeakerId.value = vnMessage.character_state?.character_id || '';
    
    // Set message in store
    vnStore.setMessage(vnMessage);
  } catch (error) {
    console.error('Failed to send message:', error);
    // TODO: Show error message
  } finally {
    isLoading.value = false;
  }
};

const handleAdvance = () => {
  // Logic to load next message or allow user input
  showInput.value = true;
};

const preloadAssets = async () => {
  try {
    // Preload scene assets
    await assetManager.preloadScene(scenarioId.value);
    
    // Preload character assets
    if (props.session.character_name) {
      await assetManager.preloadCharacter(props.session.character_name);
    }
  } catch (error) {
    console.error('Failed to preload assets:', error);
  }
};

onMounted(async () => {
  // Reset store
  vnStore.reset();
  
  // Preload assets
  await preloadAssets();
  
  // Set initial scene
  vnStore.setScene({
    background: 'default',
    time_of_day: 'day'
  });
  
  // Event listeners
  window.addEventListener('vn:advance', handleAdvance);
  
  // TODO: Load chat history if resuming session
});

onUnmounted(() => {
  window.removeEventListener('vn:advance', handleAdvance);
  vnStore.reset();
});
</script>

<style scoped>
.visual-novel-container {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: #000;
}

/* Layers */
.character-layer,
.effects-layer,
.ui-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.ui-layer {
  pointer-events: auto;
}

/* Input controls */
.input-controls {
  position: absolute;
  bottom: 200px;
  left: 50%;
  transform: translateX(-50%);
  width: 90%;
  max-width: 600px;
  display: flex;
  gap: 10px;
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: auto;
}

.visual-novel-container:hover .input-controls {
  opacity: 1;
}

.message-input {
  flex: 1;
  padding: 12px 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 25px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  font-size: 16px;
  outline: none;
  transition: all 0.2s ease;
}

.message-input:focus {
  border-color: rgba(255, 255, 255, 0.6);
  background: rgba(0, 0, 0, 0.9);
}

.send-button {
  padding: 12px 24px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 25px;
  background: rgba(255, 255, 255, 0.1);
  color: white;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.send-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.6);
}

.send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* History overlay */
.history-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 70vh;
  background: rgba(0, 0, 0, 0.95);
  backdrop-filter: blur(10px);
  z-index: 200;
  display: flex;
  flex-direction: column;
}

.history-header,
.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.history-header h2,
.settings-header h2 {
  color: white;
  margin: 0;
}

.close-button {
  background: none;
  border: none;
  color: white;
  font-size: 32px;
  cursor: pointer;
  padding: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s ease;
}

.close-button:hover {
  opacity: 0.7;
}

.history-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.history-message {
  margin-bottom: 20px;
  padding: 15px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.history-character {
  color: #66ccff;
  font-weight: bold;
  margin-bottom: 5px;
}

.history-text {
  color: white;
  line-height: 1.6;
}

/* Settings overlay */
.settings-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-panel {
  background: rgba(0, 0, 0, 0.95);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.settings-content {
  padding: 20px;
}

.setting-item {
  margin-bottom: 25px;
  color: white;
}

.setting-item label {
  display: block;
  margin-bottom: 10px;
  font-weight: bold;
}

.setting-item input[type="range"] {
  width: 70%;
  margin-right: 10px;
}

.setting-item span {
  color: #66ccff;
}

/* Transitions */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease;
}

.slide-up-enter-from {
  transform: translateY(100%);
}

.slide-up-leave-to {
  transform: translateY(100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Mobile styles */
@media (max-width: 768px) {
  .input-controls {
    opacity: 1;
    bottom: 150px;
  }
  
  .history-overlay {
    height: 90vh;
  }
}
</style>