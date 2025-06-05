<template>
  <div 
    v-if="vnStore.textDisplay.showTextBox"
    class="text-display"
    @click="handleClick"
  >
    <!-- Character name badge -->
    <div v-if="characterName" class="character-name">
      {{ characterName }}
    </div>
    
    <!-- Dialogue box -->
    <div class="dialogue-box">
      <div class="dialogue-text">
        {{ displayedText }}
        <span v-if="isTyping" class="typing-cursor">▼</span>
      </div>
      
      <!-- Control indicators -->
      <div class="control-indicators">
        <span v-if="vnStore.ui.autoMode" class="indicator auto">AUTO</span>
        <span v-if="vnStore.ui.skipMode" class="indicator skip">SKIP</span>
        <span v-if="vnStore.audio.voicePlaying" class="indicator voice">🔊</span>
      </div>
    </div>
    
    <!-- Quick menu -->
    <div class="quick-menu">
      <button @click.stop="toggleAuto" class="menu-button">
        {{ vnStore.ui.autoMode ? 'Auto Off' : 'Auto On' }}
      </button>
      <button @click.stop="toggleSkip" class="menu-button">
        {{ vnStore.ui.skipMode ? 'Skip Off' : 'Skip On' }}
      </button>
      <button @click.stop="showHistory" class="menu-button">History</button>
      <button @click.stop="showSettings" class="menu-button">Settings</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useVisualNovelStore } from '../../stores/visualNovel';
import type { TypewriterConfig } from '../../types/chat';

const vnStore = useVisualNovelStore();

const props = withDefaults(defineProps<{
  config?: TypewriterConfig;
}>(), {
  config: () => ({
    baseSpeed: 30,
    punctuationDelay: 300,
    instantOnClick: true,
    soundEffect: undefined
  })
});

const displayedText = computed(() => vnStore.textDisplay.displayedText);
const isTyping = computed(() => vnStore.textDisplay.isTyping);

const characterName = computed(() => {
  const message = vnStore.textDisplay.currentMessage;
  if (!message || message.role !== 'assistant') return '';
  
  // TODO: Get character name from character metadata
  return message.character_state?.character_id || 'Character';
});

let typewriterInterval: number | null = null;
let currentIndex = 0;

const startTypewriter = () => {
  if (!vnStore.textDisplay.currentMessage) return;
  
  const fullText = vnStore.textDisplay.currentMessage.content;
  const speed = vnStore.textDisplay.currentMessage.display_options?.typing_speed || props.config.baseSpeed;
  const charDelay = 1000 / speed; // Convert characters per second to ms per character
  
  currentIndex = 0;
  vnStore.updateDisplayedText('');
  
  const typeNextChar = () => {
    if (currentIndex >= fullText.length) {
      vnStore.completeTyping();
      stopTypewriter();
      return;
    }
    
    const char = fullText[currentIndex];
    const nextChar = fullText[currentIndex + 1];
    
    // Add character
    vnStore.updateDisplayedText(fullText.slice(0, currentIndex + 1));
    currentIndex++;
    
    // Play sound effect if configured
    if (props.config.soundEffect && char !== ' ') {
      playTypingSound();
    }
    
    // Calculate delay for next character
    let delay = charDelay;
    if (['.', '!', '?', ','].includes(char) && nextChar === ' ') {
      delay += props.config.punctuationDelay;
    }
    
    // Skip mode - no delay
    if (vnStore.ui.skipMode) {
      delay = 0;
    }
    
    typewriterInterval = window.setTimeout(typeNextChar, delay);
  };
  
  typeNextChar();
};

const stopTypewriter = () => {
  if (typewriterInterval) {
    clearTimeout(typewriterInterval);
    typewriterInterval = null;
  }
};

const playTypingSound = () => {
  // TODO: Implement sound effect playback
  // const audio = new Audio(props.config.soundEffect);
  // audio.volume = vnStore.audio.sfxVolume;
  // audio.play().catch(() => {});
};

const handleClick = () => {
  if (isTyping.value && props.config.instantOnClick) {
    vnStore.completeTyping();
    stopTypewriter();
  } else if (!isTyping.value) {
    // Advance to next message
    window.dispatchEvent(new CustomEvent('vn:advance'));
  }
};

const toggleAuto = () => {
  vnStore.toggleAutoMode();
};

const toggleSkip = () => {
  vnStore.toggleSkipMode();
};

const showHistory = () => {
  vnStore.toggleHistory();
};

const showSettings = () => {
  vnStore.toggleSettings();
};

// Watch for new messages
watch(
  () => vnStore.textDisplay.currentMessage,
  (newMessage) => {
    if (newMessage) {
      stopTypewriter();
      startTypewriter();
    }
  }
);

// Watch for skip mode changes
watch(
  () => vnStore.ui.skipMode,
  (skipMode) => {
    if (skipMode && isTyping.value) {
      vnStore.completeTyping();
      stopTypewriter();
    }
  }
);

// Auto-advance handler
const handleAutoAdvance = () => {
  if (vnStore.ui.autoMode && !isTyping.value) {
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent('vn:advance'));
    }, 1000); // Wait 1 second before auto-advancing
  }
};

onMounted(() => {
  window.addEventListener('vn:autoAdvance', handleAutoAdvance);
  if (vnStore.textDisplay.currentMessage) {
    startTypewriter();
  }
});

onUnmounted(() => {
  window.removeEventListener('vn:autoAdvance', handleAutoAdvance);
  stopTypewriter();
});
</script>

<style scoped>
.text-display {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20px;
  z-index: 100;
}

.character-name {
  background: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 8px 20px;
  border-radius: 20px;
  display: inline-block;
  margin-bottom: 10px;
  font-weight: bold;
  font-size: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
}

.dialogue-box {
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(10px);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  padding: 25px 30px;
  min-height: 120px;
  position: relative;
  cursor: pointer;
  transition: background 0.2s ease;
}

.dialogue-box:hover {
  background: rgba(0, 0, 0, 0.85);
}

.dialogue-text {
  color: white;
  font-size: 20px;
  line-height: 1.6;
  text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
}

.typing-cursor {
  display: inline-block;
  animation: cursor-blink 0.8s ease-in-out infinite;
  margin-left: 2px;
  font-size: 14px;
  vertical-align: middle;
}

@keyframes cursor-blink {
  0%, 100% {
    opacity: 0;
  }
  50% {
    opacity: 1;
  }
}

.control-indicators {
  position: absolute;
  top: 10px;
  right: 20px;
  display: flex;
  gap: 10px;
}

.indicator {
  padding: 4px 12px;
  border-radius: 15px;
  font-size: 12px;
  font-weight: bold;
  text-transform: uppercase;
}

.indicator.auto {
  background: #4CAF50;
  color: white;
}

.indicator.skip {
  background: #FF9800;
  color: white;
}

.indicator.voice {
  background: #2196F3;
  color: white;
  padding: 4px 8px;
}

.quick-menu {
  position: absolute;
  bottom: 100%;
  right: 0;
  margin-bottom: 10px;
  display: flex;
  gap: 10px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.text-display:hover .quick-menu {
  opacity: 1;
}

.menu-button {
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.menu-button:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.5);
}

/* Mobile styles */
@media (max-width: 768px) {
  .text-display {
    padding: 10px;
  }
  
  .character-name {
    font-size: 16px;
    padding: 6px 15px;
  }
  
  .dialogue-box {
    padding: 20px;
    min-height: 100px;
  }
  
  .dialogue-text {
    font-size: 18px;
  }
  
  .quick-menu {
    opacity: 1;
    position: relative;
    bottom: auto;
    margin-top: 10px;
    margin-bottom: 0;
  }
  
  .menu-button {
    font-size: 12px;
    padding: 5px 12px;
  }
}
</style>