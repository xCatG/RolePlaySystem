/**
 * TypeScript type definitions for voice chat functionality.
 */

export interface VoiceConfig {
  type: 'config'
  audio_format: string
  sample_rate: number
  channels: number
  bit_depth: number
  language: string
  voice_name: string
  output_audio_format: string
}

export interface VoiceStatus {
  type: 'status' | 'connected' | 'ready' | 'error' | 'disconnected' | 'connecting'
  message: string
  timestamp: string
}

export interface PartialTranscript {
  type: 'transcript_partial'
  text: string
  role: 'user' | 'assistant'
  stability: number
  timestamp: string
}

export interface FinalTranscript {
  type: 'transcript_final'
  text: string
  role: 'user' | 'assistant'
  duration_ms: number
  confidence: number
  metadata: Record<string, any>
  timestamp: string
}

export interface AudioChunk {
  type: 'audio'
  data: string // base64 encoded audio
  mime_type: string
  sequence?: number
  timestamp: string
}

export interface TurnStatus {
  type: 'turn_status'
  turn_complete: boolean
  interrupted: boolean
  timestamp: string
}

export interface VoiceError {
  type: 'error'
  error: string
  code?: string
  timestamp: string
}

export interface TranscriptMessage {
  id: string
  text: string
  role: 'user' | 'assistant'
  timestamp: string
  isVoice: boolean
  duration?: number
  confidence?: number
  metadata?: Record<string, any>
}

export interface VoiceSessionInfo {
  session_id: string
  user_id: string
  character_id?: string
  scenario_id?: string
  language: string
  started_at?: string
  transcript_available: boolean
}

export interface VoiceSessionStats {
  session_id: string
  started_at: string
  ended_at?: string
  duration_ms?: number
  audio_chunks_sent: number
  audio_chunks_received: number
  transcripts_processed: number
  total_utterances: number
  total_partials: number
  errors: number
}

export interface VoiceClientRequest {
  mime_type: string
  data: string // base64 encoded
  end_session: boolean
}

// Union types for WebSocket messages
export type VoiceServerMessage = 
  | VoiceConfig
  | VoiceStatus
  | PartialTranscript
  | FinalTranscript
  | AudioChunk
  | TurnStatus
  | VoiceError

export type VoiceClientMessage = VoiceClientRequest

// Audio processing types
export interface AudioBufferInfo {
  sampleRate: number
  channels: number
  length: number
  duration: number
}

export interface AudioProcessingOptions {
  sampleRate?: number
  channels?: number
  bitDepth?: number
  chunkSize?: number
  enableEchoCancellation?: boolean
  enableNoiseSuppression?: boolean
  enableAutoGainControl?: boolean
}

// Transcript buffer configuration
export interface TranscriptBufferConfig {
  stabilityThreshold?: number
  finalizationTimeout?: number
  minUtteranceLength?: number
  maxPartialAge?: number
}

// Voice chat statistics
export interface VoiceChatStatistics {
  totalMessages: number
  voiceMessages: number
  textMessages: number
  averageConfidence: number
  totalDurationMs: number
  totalDurationSeconds: number
}

// WebSocket connection states
export type WebSocketState = 'connecting' | 'connected' | 'disconnecting' | 'disconnected' | 'error'

// Audio recording states
export type RecordingState = 'idle' | 'starting' | 'recording' | 'stopping' | 'error'

// Audio playback states
export type PlaybackState = 'idle' | 'playing' | 'paused' | 'buffering' | 'error'