import { defineStore } from 'pinia';
import type { CharacterState, SceneState, VisualNovelMessage } from '../types/chat';

export interface VisualNovelState {
  currentScene: {
    background: string;
    backgroundEffect?: string;
    timeOfDay: 'morning' | 'day' | 'evening' | 'night';
    characters: Map<string, CharacterState>;
    bgm?: string;
  };
  
  textDisplay: {
    currentMessage: VisualNovelMessage | null;
    displayedText: string;      // For typewriter effect
    isTyping: boolean;
    history: VisualNovelMessage[];
    showTextBox: boolean;
  };
  
  audio: {
    voicePlaying: boolean;
    bgmVolume: number;
    voiceVolume: number;
    sfxVolume: number;
    currentBgm: HTMLAudioElement | null;
    currentVoice: HTMLAudioElement | null;
  };
  
  ui: {
    autoMode: boolean;
    skipMode: boolean;
    textSpeed: number;  // Characters per second
    showHistory: boolean;
    showSettings: boolean;
  };
}

export const useVisualNovelStore = defineStore('visualNovel', {
  state: (): VisualNovelState => ({
    currentScene: {
      background: '',
      timeOfDay: 'day',
      characters: new Map(),
      bgm: undefined
    },
    
    textDisplay: {
      currentMessage: null,
      displayedText: '',
      isTyping: false,
      history: [],
      showTextBox: true
    },
    
    audio: {
      voicePlaying: false,
      bgmVolume: 0.5,
      voiceVolume: 1.0,
      sfxVolume: 0.7,
      currentBgm: null,
      currentVoice: null
    },
    
    ui: {
      autoMode: false,
      skipMode: false,
      textSpeed: 30,
      showHistory: false,
      showSettings: false
    }
  }),
  
  getters: {
    allCharacters: (state) => Array.from(state.currentScene.characters.values()),
    
    isTextFullyDisplayed: (state) => {
      if (!state.textDisplay.currentMessage) return true;
      return state.textDisplay.displayedText === state.textDisplay.currentMessage.content;
    },
    
    canAdvance: (state) => {
      return !state.textDisplay.isTyping || state.ui.skipMode;
    }
  },
  
  actions: {
    setScene(sceneState: SceneState) {
      this.currentScene.background = sceneState.background;
      if (sceneState.time_of_day) {
        this.currentScene.timeOfDay = sceneState.time_of_day;
      }
      if (sceneState.bgm !== undefined) {
        this.playBgm(sceneState.bgm);
      }
    },
    
    addCharacter(character: CharacterState) {
      this.currentScene.characters.set(character.character_id, character);
    },
    
    updateCharacter(characterId: string, updates: Partial<CharacterState>) {
      const character = this.currentScene.characters.get(characterId);
      if (character) {
        this.currentScene.characters.set(characterId, { ...character, ...updates });
      }
    },
    
    removeCharacter(characterId: string) {
      this.currentScene.characters.delete(characterId);
    },
    
    setMessage(message: VisualNovelMessage) {
      // Stop current typing if any
      this.textDisplay.isTyping = false;
      
      // Add previous message to history if exists
      if (this.textDisplay.currentMessage) {
        this.textDisplay.history.push(this.textDisplay.currentMessage);
      }
      
      // Set new message
      this.textDisplay.currentMessage = message;
      this.textDisplay.displayedText = '';
      this.textDisplay.isTyping = true;
      
      // Update scene if message has scene state
      if (message.scene_state) {
        this.setScene(message.scene_state);
      }
      
      // Update character if message has character state
      if (message.character_state) {
        this.addCharacter(message.character_state);
      }
      
      // Play voice if available
      if (message.voice?.audio_url) {
        this.playVoice(message.voice.audio_url);
      }
    },
    
    updateDisplayedText(text: string) {
      this.textDisplay.displayedText = text;
    },
    
    completeTyping() {
      if (this.textDisplay.currentMessage) {
        this.textDisplay.displayedText = this.textDisplay.currentMessage.content;
        this.textDisplay.isTyping = false;
      }
    },
    
    async playBgm(bgmPath: string | null) {
      // Stop current BGM
      if (this.audio.currentBgm) {
        this.audio.currentBgm.pause();
        this.audio.currentBgm = null;
      }
      
      if (!bgmPath) return;
      
      try {
        const audio = new Audio(bgmPath);
        audio.volume = this.audio.bgmVolume;
        audio.loop = true;
        await audio.play();
        this.audio.currentBgm = audio;
      } catch (error) {
        console.error('Failed to play BGM:', error);
      }
    },
    
    async playVoice(voicePath: string) {
      // Stop current voice
      if (this.audio.currentVoice) {
        this.audio.currentVoice.pause();
        this.audio.currentVoice = null;
      }
      
      try {
        const audio = new Audio(voicePath);
        audio.volume = this.audio.voiceVolume;
        this.audio.voicePlaying = true;
        
        audio.addEventListener('ended', () => {
          this.audio.voicePlaying = false;
          this.audio.currentVoice = null;
          
          // Auto-advance if enabled
          if (this.ui.autoMode && this.isTextFullyDisplayed) {
            // Emit event for auto-advance
            window.dispatchEvent(new CustomEvent('vn:autoAdvance'));
          }
        }, { once: true });
        
        await audio.play();
        this.audio.currentVoice = audio;
      } catch (error) {
        console.error('Failed to play voice:', error);
        this.audio.voicePlaying = false;
      }
    },
    
    setVolume(type: 'bgm' | 'voice' | 'sfx', volume: number) {
      volume = Math.max(0, Math.min(1, volume));
      
      switch (type) {
        case 'bgm':
          this.audio.bgmVolume = volume;
          if (this.audio.currentBgm) {
            this.audio.currentBgm.volume = volume;
          }
          break;
        case 'voice':
          this.audio.voiceVolume = volume;
          if (this.audio.currentVoice) {
            this.audio.currentVoice.volume = volume;
          }
          break;
        case 'sfx':
          this.audio.sfxVolume = volume;
          break;
      }
    },
    
    toggleAutoMode() {
      this.ui.autoMode = !this.ui.autoMode;
    },
    
    toggleSkipMode() {
      this.ui.skipMode = !this.ui.skipMode;
    },
    
    setTextSpeed(speed: number) {
      this.ui.textSpeed = Math.max(10, Math.min(100, speed));
    },
    
    toggleHistory() {
      this.ui.showHistory = !this.ui.showHistory;
    },
    
    toggleSettings() {
      this.ui.showSettings = !this.ui.showSettings;
    },
    
    reset() {
      // Reset to initial state
      this.currentScene.characters.clear();
      this.currentScene.background = '';
      this.textDisplay.currentMessage = null;
      this.textDisplay.displayedText = '';
      this.textDisplay.history = [];
      
      // Stop audio
      if (this.audio.currentBgm) {
        this.audio.currentBgm.pause();
        this.audio.currentBgm = null;
      }
      if (this.audio.currentVoice) {
        this.audio.currentVoice.pause();
        this.audio.currentVoice = null;
      }
    }
  }
});