<template>
  <transition :name="enterEffect" @after-enter="onEnterComplete">
    <div
      v-if="isVisible"
      class="character-sprite"
      :class="[positionClass, { 'is-speaking': isSpeaking }]"
      :style="spriteStyle"
    >
      <!-- Pose layer -->
      <img
        v-if="poseImage"
        :src="poseImage"
        class="sprite-layer pose-layer"
        :alt="`${character.character_id} pose`"
      />
      
      <!-- Expression layer -->
      <img
        v-if="expressionImage"
        :src="expressionImage"
        class="sprite-layer expression-layer"
        :alt="`${character.character_id} expression`"
      />
      
      <!-- Blink animation overlay (future implementation) -->
      <div v-if="showBlinkAnimation" class="blink-overlay" />
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import type { CharacterState } from '../../types/chat';
import { AssetManager } from '../../services/assetManager';

const props = defineProps<{
  character: CharacterState;
  isSpeaking?: boolean;
}>();

const assetManager = AssetManager.getInstance();
const isVisible = ref(false);
const poseImage = ref<string>('');
const expressionImage = ref<string>('');
const showBlinkAnimation = ref(false);
const metadata = ref<any>(null);

const positionClass = computed(() => `position-${props.character.position || 'center'}`);

const enterEffect = computed(() => props.character.enter_effect || 'fade');

const spriteStyle = computed(() => {
  if (!metadata.value) return {};
  
  const config = metadata.value.sprite_config;
  return {
    transform: `scale(${config.scale || 1})`,
    '--anchor-x': config.position?.x || 0.5,
    '--anchor-y': config.position?.y || 0.85
  };
});

// Load character assets
const loadCharacterAssets = async () => {
  try {
    // Load metadata
    metadata.value = await assetManager.loadCharacterMetadata(props.character.character_id);
    
    // Load sprites
    const sprites = await assetManager.getCharacterSprite(
      props.character.character_id,
      props.character.pose,
      props.character.expression
    );
    
    poseImage.value = sprites.pose.src;
    expressionImage.value = sprites.expression.src;
    
    // Show character after assets are loaded
    setTimeout(() => {
      isVisible.value = true;
    }, 100);
  } catch (error) {
    console.error('Failed to load character assets:', error);
  }
};

// Watch for pose/expression changes
watch(
  () => [props.character.pose, props.character.expression],
  async ([newPose, newExpression]) => {
    try {
      const sprites = await assetManager.getCharacterSprite(
        props.character.character_id,
        newPose,
        newExpression
      );
      
      // Animate transition
      poseImage.value = sprites.pose.src;
      expressionImage.value = sprites.expression.src;
    } catch (error) {
      console.error('Failed to update character sprite:', error);
    }
  }
);

// Eye blink animation (placeholder for future implementation)
let blinkInterval: number | null = null;

const startBlinkAnimation = () => {
  if (!metadata.value?.animation_config) return;
  
  const config = metadata.value.animation_config;
  const [minInterval, maxInterval] = config.blink_interval || [3000, 7000];
  
  const scheduleNextBlink = () => {
    const interval = Math.random() * (maxInterval - minInterval) + minInterval;
    blinkInterval = window.setTimeout(() => {
      // TODO: Implement actual blink animation
      showBlinkAnimation.value = true;
      setTimeout(() => {
        showBlinkAnimation.value = false;
      }, config.blink_duration || 200);
      
      scheduleNextBlink();
    }, interval);
  };
  
  scheduleNextBlink();
};

const stopBlinkAnimation = () => {
  if (blinkInterval) {
    clearTimeout(blinkInterval);
    blinkInterval = null;
  }
};

const onEnterComplete = () => {
  startBlinkAnimation();
};

onMounted(() => {
  loadCharacterAssets();
});

onUnmounted(() => {
  stopBlinkAnimation();
});
</script>

<style scoped>
.character-sprite {
  position: absolute;
  bottom: 0;
  width: auto;
  height: 80%;
  max-height: 80vh;
  transition: all 0.3s ease;
}

/* Position classes */
.position-left {
  left: 10%;
}

.position-center {
  left: 50%;
  transform: translateX(-50%);
}

.position-right {
  right: 10%;
}

/* Sprite layers */
.sprite-layer {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  height: 100%;
  width: auto;
}

.pose-layer {
  z-index: 1;
}

.expression-layer {
  z-index: 2;
}

/* Speaking animation */
.is-speaking {
  animation: speaking-bounce 0.5s ease-in-out infinite alternate;
}

@keyframes speaking-bounce {
  0% {
    transform: translateY(0) var(--transform, '');
  }
  100% {
    transform: translateY(-5px) var(--transform, '');
  }
}

/* Enter effects */
.fade-enter-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from {
  opacity: 0;
}

.slide-enter-active {
  transition: all 0.5s ease;
}

.slide-enter-from {
  opacity: 0;
  transform: translateX(-50px);
}

.position-right.slide-enter-from {
  transform: translateX(50px);
}

/* Blink overlay (placeholder) */
.blink-overlay {
  position: absolute;
  top: 20%;
  left: 50%;
  transform: translateX(-50%);
  width: 30%;
  height: 10%;
  background: rgba(0, 0, 0, 0.8);
  z-index: 3;
  opacity: 0;
  animation: blink 0.2s ease;
}

@keyframes blink {
  0%, 100% {
    opacity: 0;
  }
  50% {
    opacity: 1;
  }
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .character-sprite {
    height: 70%;
  }
  
  .position-left {
    left: 5%;
  }
  
  .position-right {
    right: 5%;
  }
}
</style>