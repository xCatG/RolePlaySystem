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
  scenario_name: string;
  character_name: string;
  participant_name: string;
  created_at: string;
  message_count: number;
  jsonl_filename: string;
  is_active: boolean;
  goal?: string | null;
  session_type?: 'freeform' | 'scripted';
  ended_at?: string | null;
  ended_reason?: string | null;
}

export interface SessionListResponse extends BaseResponse {
  sessions: SessionInfo[];
}

// Request types - matches Python models exactly
export interface CreateSessionRequest {
  scenario_id: string;
  character_id?: string;
  script_id?: string;
  participant_name: string;
}

export interface CreateSessionResponse extends BaseResponse {
  session_id: string;
  scenario_name: string;
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

// Session status types
export interface SessionStatusResponse extends BaseResponse {
  status: 'active' | 'ended';
  ended_at?: string | null;
  ended_reason?: string | null;
}

// Message types - now matches backend Message model
export interface Message {
  role: 'participant' | 'character' | 'system';
  content: string;
  timestamp: string;
  message_number?: number;
}

export interface MessagesListResponse extends BaseResponse {
  messages: Message[];
  session_id: string;
}

// Script types - minimal info for frontend display
export interface ScriptInfo {
  id: string;
  scenario_id: string;
  character_id: string;
  language: string;
  goal: string;
}

export interface ScriptListResponse extends BaseResponse {
  scripts: ScriptInfo[];
}

// Legacy aliases for backward compatibility (will be removed)
export type Scenario = ScenarioInfo;
export type Character = CharacterInfo;
export type Session = SessionInfo;
export type SendMessageRequest = ChatMessageRequest;
export type ChatResponse = ChatMessageResponse;