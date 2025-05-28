export interface Scenario {
  id: string;
  name: string;
  description: string;
  compatible_character_count: number;
}

export interface Character {
  id: string;
  name: string;
  description: string;
}

export interface Session {
  session_id: string;
  scenario_name: string;
  character_name: string;
  participant_name: string;
  created_at: string;
  message_count: number;
  jsonl_filename: string;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface CreateSessionRequest {
  scenario_id: string;
  character_id: string;
  participant_name: string;
}

export interface SendMessageRequest {
  message: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
}