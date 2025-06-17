import axios from 'axios';
import { apiUrl, getAuthHeaders } from './apiConfig';
import type { EvaluationResponse } from '../types/evaluation';

export const evaluationApi = {
  async evaluateSession(sessionId: string): Promise<EvaluationResponse> {
    const response = await axios.post<EvaluationResponse>(
      apiUrl('/eval/session/evaluate'),
      { session_id: sessionId },
      {
        headers: getAuthHeaders()
      }
    );
    return response.data;
  }
};
