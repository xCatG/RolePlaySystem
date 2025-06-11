// Base response interface to match Python BaseResponse
export interface BaseResponse {
  success: boolean;
  message?: string | null;
}

// Scenario types - matches ScenarioInfo and ScenarioListResponse  
export interface ScenarioInfo {
  id: string;
  name: string;
  description: string;
  compatible_character_count: number;
}

export interface ScenarioListResponse extends BaseResponse {
  scenarios: ScenarioInfo[];
}

// Character types - matches CharacterInfo and CharacterListResponse
export interface CharacterInfo {
  id: string;
  name: string;
  description: string;
}

export interface CharacterListResponse extends BaseResponse {
  characters: CharacterInfo[];
}

// Session types - matches SessionInfo and SessionListResponse
export interface SessionInfo {
  session_id: string;
  scenario_id: string;
  scenario_name: string;
  character_id: string;
  character_name: string;
  participant_name: string;
  created_at: string;
  message_count: number;
  jsonl_filename: string;
}

export interface SessionListResponse extends BaseResponse {
  sessions: SessionInfo[];
}

// Request types - matches Python models exactly
export interface CreateSessionRequest {
  scenario_id: string;
  character_id: string;
  participant_name: string;
}

export interface CreateSessionResponse extends BaseResponse {
  session_id: string;
  scenario_id: string;
  scenario_name: string;
  character_id: string;
  character_name: string;
  jsonl_filename: string;
}

export interface ChatMessageRequest {
  message: string;
}

export interface ChatMessageResponse extends BaseResponse {
  response: string;
  session_id: string;
  message_count: number;
}

// Frontend-only types (not in Python backend)
export interface Message {
  role: 'participant' | 'character' | 'system';
  content: string;
  timestamp: string;
}

// Visual Novel specific types
export interface CharacterState {
  character_id: string;
  pose: string;
  expression: string;
  position?: 'left' | 'center' | 'right';
  enter_effect?: 'fade' | 'slide' | 'none';
}

export interface SceneState {
  background: string;
  time_of_day?: 'morning' | 'day' | 'evening' | 'night';
  bgm?: string;
  transition?: 'fade' | 'dissolve' | 'none';
}

export interface VoiceConfig {
  audio_url?: string;
  text_to_speech?: {
    service: 'google' | 'azure' | 'elevenlabs';
    voice_id: string;
    speed?: number;
    pitch?: number;
  };
}

export interface DisplayOptions {
  typing_speed?: number;        // Characters per second
  auto_advance?: boolean;       // Auto-advance after voice playback
  wait_for_input?: boolean;     // Require user input to continue
}

export interface VisualNovelMessage extends Message {
  id: string;
  character_state?: CharacterState;
  scene_state?: SceneState;
  voice?: VoiceConfig;
  display_options?: DisplayOptions;
}

export interface TypewriterConfig {
  baseSpeed: number;          // Characters per second (default: 30)
  punctuationDelay: number;   // Extra delay for . , ! ? (default: 300ms)
  instantOnClick: boolean;    // Show all text on click (default: true)
  soundEffect?: string;       // Play sound per character
}

// Legacy aliases for backward compatibility (will be removed)
export type Scenario = ScenarioInfo;
export type Character = CharacterInfo;
export type Session = SessionInfo;
export type SendMessageRequest = ChatMessageRequest;
export type ChatResponse = ChatMessageResponse;