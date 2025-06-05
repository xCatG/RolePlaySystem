<template>
  <div class="background-renderer">
    <transition :name="transitionName" mode="out-in">
      <div
        v-if="backgroundUrl"
        :key="backgroundUrl"
        class="background-image"
        :style="backgroundStyle"
      />
    </transition>
    
    <!-- Time of day overlay effect -->
    <div 
      v-if="showTimeEffect"
      class="time-overlay"
      :class="timeOfDay"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useVisualNovelStore } from '../../stores/visualNovel';
import { AssetManager } from '../../services/assetManager';

const vnStore = useVisualNovelStore();
const assetManager = AssetManager.getInstance();

const backgroundUrl = ref<string>('');
const isLoading = ref(false);
const transitionName = ref('fade');

const props = defineProps<{
  scenarioId: string;
  transition?: 'fade' | 'dissolve' | 'none';
  showTimeEffect?: boolean;
}>();

const timeOfDay = computed(() => vnStore.currentScene.timeOfDay);

const backgroundStyle = computed(() => ({
  backgroundImage: backgroundUrl.value ? `url(${backgroundUrl.value})` : 'none'
}));

// Watch for scene changes
watch(
  () => vnStore.currentScene.background,
  async (newBackground) => {
    if (!newBackground || !props.scenarioId) return;
    
    isLoading.value = true;
    transitionName.value = props.transition || 'fade';
    
    try {
      const bgPath = assetManager.getBackgroundPath(props.scenarioId, vnStore.currentScene.timeOfDay);
      await assetManager.loadImage(bgPath);
      backgroundUrl.value = bgPath;
    } catch (error) {
      console.error('Failed to load background:', error);
      // Try default background as fallback
      try {
        const defaultPath = assetManager.getBackgroundPath(props.scenarioId, 'default');
        await assetManager.loadImage(defaultPath);
        backgroundUrl.value = defaultPath;
      } catch (fallbackError) {
        console.error('Failed to load default background:', fallbackError);
      }
    } finally {
      isLoading.value = false;
    }
  },
  { immediate: true }
);

// Watch for time of day changes
watch(
  () => vnStore.currentScene.timeOfDay,
  async (newTimeOfDay) => {
    if (!vnStore.currentScene.background || !props.scenarioId) return;
    
    try {
      const bgPath = assetManager.getBackgroundPath(props.scenarioId, newTimeOfDay);
      await assetManager.loadImage(bgPath);
      backgroundUrl.value = bgPath;
    } catch (error) {
      // Keep current background if time variant doesn't exist
      console.warn(`No ${newTimeOfDay} variant for current background`);
    }
  }
);
</script>

<style scoped>
.background-renderer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.background-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

/* Time overlay effects */
.time-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  transition: opacity 2s ease;
}

.time-overlay.morning {
  background: linear-gradient(
    to bottom,
    rgba(255, 200, 100, 0.1),
    rgba(255, 220, 150, 0.05)
  );
}

.time-overlay.day {
  background: none;
}

.time-overlay.evening {
  background: linear-gradient(
    to bottom,
    rgba(255, 100, 50, 0.15),
    rgba(255, 150, 100, 0.1)
  );
}

.time-overlay.night {
  background: linear-gradient(
    to bottom,
    rgba(0, 0, 50, 0.3),
    rgba(0, 0, 100, 0.2)
  );
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 1s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.dissolve-enter-active,
.dissolve-leave-active {
  transition: opacity 2s ease, filter 2s ease;
}

.dissolve-enter-from {
  opacity: 0;
  filter: blur(10px);
}

.dissolve-leave-to {
  opacity: 0;
  filter: blur(10px);
}

.none-enter-active,
.none-leave-active {
  transition: none;
}
</style>