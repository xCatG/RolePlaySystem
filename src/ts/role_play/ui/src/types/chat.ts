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

// Frontend-only types (not in Python backend)
export interface Message {
  role: 'participant' | 'character' | 'system';
  content: string;
  timestamp: string;
}

// Legacy aliases for backward compatibility (will be removed)
export type Scenario = ScenarioInfo;
export type Character = CharacterInfo;
export type Session = SessionInfo;
export type SendMessageRequest = ChatMessageRequest;
export type ChatResponse = ChatMessageResponse;