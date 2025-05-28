import axios from 'axios';
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

const API_BASE_URL = 'http://localhost:8000';

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const chatApi = {
  async getScenarios(): Promise<ScenarioInfo[]> {
    const response = await axios.get<ScenarioListResponse>(`${API_BASE_URL}/chat/content/scenarios`, {
      headers: getAuthHeaders()
    });
    return response.data.scenarios;
  },

  async getCharacters(scenarioId: string): Promise<CharacterInfo[]> {
    const response = await axios.get<CharacterListResponse>(
      `${API_BASE_URL}/chat/content/scenarios/${scenarioId}/characters`, 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data.characters;
  },

  async createSession(request: CreateSessionRequest): Promise<CreateSessionResponse> {
    const response = await axios.post<CreateSessionResponse>(
      `${API_BASE_URL}/chat/session`, 
      request, 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  },

  async getSessions(): Promise<SessionInfo[]> {
    const response = await axios.get<SessionListResponse>(`${API_BASE_URL}/chat/sessions`, {
      headers: getAuthHeaders()
    });
    return response.data.sessions;
  },

  async sendMessage(sessionId: string, request: ChatMessageRequest): Promise<ChatMessageResponse> {
    const response = await axios.post<ChatMessageResponse>(
      `${API_BASE_URL}/chat/session/${sessionId}/message`, 
      request, 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  },

  async exportSession(sessionId: string): Promise<string> {
    const response = await axios.get<string>(
      `${API_BASE_URL}/chat/session/${sessionId}/export-text`, 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  }
};