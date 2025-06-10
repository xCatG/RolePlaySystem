import axios from 'axios';
import { apiUrl, getAuthHeaders } from './apiConfig';
import type { 
  ScenarioInfo,
  ScenarioListResponse,
  CharacterInfo,
  CharacterListResponse,
  SessionInfo,
  SessionListResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  ChatMessageRequest,
  ChatMessageResponse
} from '../types/chat';

export const chatApi = {
  async getScenarios(language: string = 'en'): Promise<ScenarioInfo[]> {
    const response = await axios.get<ScenarioListResponse>(
      apiUrl(`/chat/content/scenarios?language=${encodeURIComponent(language)}`), 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data.scenarios;
  },

  async getCharacters(scenarioId: string, language: string = 'en'): Promise<CharacterInfo[]> {
    const response = await axios.get<CharacterListResponse>(
      apiUrl(`/chat/content/scenarios/${scenarioId}/characters?language=${encodeURIComponent(language)}`), 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data.characters;
  },

  async createSession(request: CreateSessionRequest): Promise<CreateSessionResponse> {
    const response = await axios.post<CreateSessionResponse>(
      apiUrl('/chat/session'), 
      request, 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  },

  async getSessions(): Promise<SessionInfo[]> {
    const response = await axios.get<SessionListResponse>(
      apiUrl('/chat/sessions'), 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data.sessions;
  },

  async sendMessage(sessionId: string, request: ChatMessageRequest): Promise<ChatMessageResponse> {
    const response = await axios.post<ChatMessageResponse>(
      apiUrl(`/chat/session/${sessionId}/message`), 
      request, 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  },

  async exportSession(sessionId: string): Promise<string> {
    const response = await axios.get<string>(
      apiUrl(`/chat/session/${sessionId}/export-text`), 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  }
};