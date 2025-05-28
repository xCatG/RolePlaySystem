import axios from 'axios';
import type { 
  Scenario, 
  Character, 
  Session, 
  CreateSessionRequest, 
  SendMessageRequest, 
  ChatResponse 
} from '../types/chat';

const API_BASE_URL = 'http://localhost:8000';

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const chatApi = {
  async getScenarios(): Promise<Scenario[]> {
    const response = await axios.get<{ scenarios: Scenario[]; success: boolean }>(`${API_BASE_URL}/chat/content/scenarios`, {
      headers: getAuthHeaders()
    });
    return response.data.scenarios;
  },

  async getCharacters(scenarioId: string): Promise<Character[]> {
    const response = await axios.get<{ characters: Character[]; success: boolean }>(
      `${API_BASE_URL}/chat/content/scenarios/${scenarioId}/characters`, 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data.characters;
  },

  async createSession(request: CreateSessionRequest): Promise<Session> {
    const response = await axios.post<Session>(
      `${API_BASE_URL}/chat/session`, 
      request, 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  },

  async getSessions(): Promise<Session[]> {
    const response = await axios.get<{ sessions: Session[]; success: boolean }>(`${API_BASE_URL}/chat/sessions`, {
      headers: getAuthHeaders()
    });
    return response.data.sessions;
  },

  async sendMessage(sessionId: string, request: SendMessageRequest): Promise<ChatResponse> {
    const response = await axios.post<ChatResponse>(
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