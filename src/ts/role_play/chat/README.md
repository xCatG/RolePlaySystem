# Visual Novel Chat UI Design

## Overview

This document outlines the design for a visual novel-style chat interface that combines character sprites, backgrounds, text display, and voice capabilities to create an immersive roleplay experience.

## Architecture

### 1. Asset System

#### Directory Structure
```
/assets/
├── backgrounds/
│   ├── {scenario_id}/
│   │   ├── default.jpg
│   │   ├── morning.jpg
│   │   ├── evening.jpg
│   │   └── night.jpg
├── characters/
│   ├── {character_id}/
│   │   ├── poses/
│   │   │   ├── standing_neutral.png
│   │   │   ├── standing_confident.png
│   │   │   ├── sitting_relaxed.png
│   │   │   └── sitting_crossed_arms.png
│   │   ├── expressions/
│   │   │   ├── neutral.png
│   │   │   ├── happy.png
│   │   │   ├── surprised.png
│   │   │   ├── angry.png
│   │   │   └── sad.png
│   │   ├── animations/
│   │   │   ├── blink_sequence.png    # Sprite sheet
│   │   │   └── talking_mouth.apng    # Animated PNG
│   │   └── metadata.json
└── audio/
    ├── bgm/
    │   └── {scenario_id}/
    └── sfx/
        ├── text_appear.mp3
        └── transition.mp3
```

#### Character Metadata Format
```json
{
  "character_id": "saki_hogushaki",
  "display_name": "穂久々下 サキ",
  "default_pose": "standing_neutral",
  "default_expression": "neutral",
  "sprite_config": {
    "anchor_point": "bottom_center",
    "scale": 1.0,
    "position": {"x": 0.5, "y": 0.85}
  },
  "animation_config": {
    "blink_interval": [3000, 7000],
    "blink_duration": 200,
    "talking_frame_rate": 12
  }
}
```

### 2. API Extensions

#### Enhanced Chat Message Format
```typescript
interface ChatMessage {
  id: string;
  text: string;
  sender: 'user' | 'character';
  timestamp: string;
  
  // Visual novel additions
  character_state?: {
    character_id: string;
    pose: string;
    expression: string;
    position?: 'left' | 'center' | 'right';
    enter_effect?: 'fade' | 'slide' | 'none';
  };
  
  scene_state?: {
    background: string;
    time_of_day?: 'morning' | 'day' | 'evening' | 'night';
    bgm?: string;
    transition?: 'fade' | 'dissolve' | 'none';
  };
  
  voice?: {
    audio_url?: string;
    text_to_speech?: {
      service: 'google' | 'azure' | 'elevenlabs';
      voice_id: string;
      speed?: number;
      pitch?: number;
    };
  };
  
  display_options?: {
    typing_speed?: number;        // Characters per second
    auto_advance?: boolean;       // Auto-advance after voice playback
    wait_for_input?: boolean;     // Require user input to continue
  };
}
```

### 3. Component Architecture

#### Layer Stack (bottom to top)
1. **Background Layer** - Scene backgrounds with transitions
2. **Character Layer** - Character sprites with poses/expressions
3. **Effects Layer** - Particle effects, screen overlays
4. **UI Layer** - Chat overlay, character name, text box
5. **Control Layer** - Input bar, menu buttons

#### Vue Component Structure
```
ChatInterface.vue
├── BackgroundRenderer.vue
├── CharacterSprite.vue
│   ├── PoseLayer.vue
│   ├── ExpressionLayer.vue
│   └── AnimationController.vue
├── TextDisplay.vue
│   ├── CharacterName.vue
│   ├── DialogueBox.vue
│   └── TypewriterText.vue
├── VoicePlayer.vue
└── InputControls.vue
```

### 4. Animation System

#### Eye Blinking
- Use CSS sprite animation with 4-6 frames
- Random intervals between 3-7 seconds
- 200ms blink duration
- Pause during certain expressions (surprised, closed eyes)

#### Lip Sync
- Simple 3-frame mouth animation (closed, half-open, open)
- Sync to audio amplitude or use phoneme detection
- Fallback to random movement if no audio analysis
- APNG format for smooth animation

#### Character Transitions
- Fade in/out when entering/leaving scene
- Slide for position changes
- Expression morphing using CSS transitions
- Pose changes with quick fade

### 5. Text Display System

#### Typewriter Effect
```typescript
interface TypewriterConfig {
  baseSpeed: number;          // Characters per second (default: 30)
  punctuationDelay: number;   // Extra delay for . , ! ? (default: 300ms)
  instantOnClick: boolean;    // Show all text on click (default: true)
  soundEffect?: string;       // Play sound per character
}
```

#### Text Box Features
- Semi-transparent background with blur
- Character name in separate badge
- Auto-sizing with max height
- History/backlog functionality
- Quick save/load points

### 6. Voice Integration

#### Text-to-Speech Pipeline
1. Send text to TTS service (Google Cloud, Azure, ElevenLabs)
2. Cache generated audio files
3. Preload next message's audio
4. Sync playback with text display
5. Lip sync animation during playback

#### Voice Configuration
```typescript
interface VoiceConfig {
  service: 'google' | 'azure' | 'elevenlabs';
  voiceId: string;
  language: string;
  speakingRate?: number;     // 0.5 - 2.0
  pitch?: number;            // -10 - +10
  volumeGain?: number;       // 0 - 1
  emotionPreset?: string;    // Service-specific
}
```

### 7. Mobile Optimizations

#### Responsive Design
- Touch-friendly controls (40px+ tap targets)
- Swipe gestures for history/menu
- Portrait and landscape layouts
- Dynamic text sizing based on viewport
- Simplified effects on low-end devices

#### Performance
- Lazy load character sprites
- Compress backgrounds (WebP format)
- Preload next scene assets
- Reduce animation complexity on mobile
- Battery-saving mode (reduced animations)

## Implementation Phases

### Phase 1: Core Visual Novel UI (Week 1)
- [ ] Background rendering system
- [ ] Character sprite display (static)
- [ ] Text box with typewriter effect
- [ ] Basic scene transitions

### Phase 2: Character Animation (Week 2)
- [ ] Eye blink animation
- [ ] Expression transitions
- [ ] Pose changes with effects
- [ ] Character enter/exit animations

### Phase 3: Audio Integration (Week 3)
- [ ] Text-to-speech integration
- [ ] Voice playback system
- [ ] Basic lip sync animation
- [ ] Sound effects

### Phase 4: Polish & Mobile (Week 4)
- [ ] Mobile responsive design
- [ ] Touch gestures
- [ ] Performance optimization
- [ ] Settings menu (text speed, volume, etc.)

## Technical Considerations

### Asset Loading Strategy
```typescript
class AssetManager {
  private cache: Map<string, HTMLImageElement | Audio>;
  
  async preloadScene(sceneId: string): Promise<void> {
    // Preload background, character sprites, audio
  }
  
  async getCharacterSprite(
    characterId: string, 
    pose: string, 
    expression: string
  ): Promise<HTMLImageElement> {
    // Composite pose + expression layers
  }
}
```

### State Management
```typescript
interface VisualNovelState {
  currentScene: {
    background: string;
    backgroundEffect?: string;
    characters: Map<string, CharacterState>;
    bgm?: string;
  };
  
  textDisplay: {
    currentMessage: ChatMessage;
    displayedText: string;      // For typewriter
    isTyping: boolean;
    history: ChatMessage[];
  };
  
  audio: {
    voicePlaying: boolean;
    bgmVolume: number;
    voiceVolume: number;
    sfxVolume: number;
  };
}
```

### Performance Targets
- 60 FPS for animations
- < 100ms scene transitions
- < 3MB initial bundle size
- < 500ms time to interactive
- Support for devices 3+ years old

## Future Enhancements

### Advanced Animation
- Live2D integration for dynamic 2D models
- Particle effects (rain, snow, sakura petals)
- Dynamic lighting effects
- Camera movements (zoom, pan)

### Interactive Features
- Choice points with branching dialogue
- Quick-time events
- Mini-games integration
- Character relationship tracking

### Accessibility
- Screen reader support
- Subtitle customization
- Color blind modes
- Keyboard navigation