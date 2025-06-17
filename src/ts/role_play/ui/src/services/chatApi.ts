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
  ChatMessageResponse,
  SessionStatusResponse,
  Message,
  MessagesListResponse
} from '../types/chat';
import type { FinalReviewReport } from '../types/evaluation';

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

  async triggerAndFetchEvaluationReport(sessionId: string): Promise<FinalReviewReport> {
    try {
      // Attempt to GET the report first
      const response = await axios.get<FinalReviewReport>(
        apiUrl(`/eval/session/${sessionId}/evaluate`),
        {
          headers: getAuthHeaders()
        }
      );
      return response.data;
    } catch (error) {
      // Check if error is AxiosError and has a 404 status
      if (axios.isAxiosError(error) && error.response && error.response.status === 404) {
        // Report not found, so POST to trigger evaluation
        console.log(`Report for session ${sessionId} not found (404). Triggering evaluation with POST...`);
        try {
          const postResponse = await axios.post<FinalReviewReport>(
            apiUrl(`/eval/session/${sessionId}/evaluate`),
            {}, // Assuming empty body for POST, adjust if API requires payload
            {
              headers: getAuthHeaders()
            }
          );
          // Assuming POST returns the report directly or finishes generation before responding
          return postResponse.data;
        } catch (postError) {
          console.error(`Failed to trigger or fetch evaluation report for session ${sessionId} after POST:`, postError);
          throw postError; // Re-throw error from POST
        }
      } else {
        // Other error (not 404 or not AxiosError)
        console.error(`Failed to fetch evaluation report for session ${sessionId} with initial GET:`, error);
        throw error; // Re-throw original error
      }
    }
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
  },

  async getSessionStatus(sessionId: string): Promise<SessionStatusResponse> {
    const response = await axios.get<SessionStatusResponse>(
      apiUrl(`/chat/session/${sessionId}/status`), 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  },

  async getSessionMessages(sessionId: string): Promise<Message[]> {
    const response = await axios.get<MessagesListResponse>(
      apiUrl(`/chat/session/${sessionId}/messages`), 
      {
        headers: getAuthHeaders()
      }
    );
    return response.data.messages;
  },

  async endSession(sessionId: string): Promise<void> {
    await axios.post(
      apiUrl(`/chat/session/${sessionId}/end`), 
      {},
      {
        headers: getAuthHeaders()
      }
    );
  },

  async deleteSession(sessionId: string): Promise<void> {
    await axios.delete(
      apiUrl(`/chat/session/${sessionId}`), 
      {
        headers: getAuthHeaders()
      }
    );
  }
};