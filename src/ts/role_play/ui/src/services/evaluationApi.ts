import axios from 'axios';
import { apiUrl, getAuthHeaders } from './apiConfig';
import type { EvaluationRequest, EvaluationResponse } from '@/types/evaluation';

export const evaluationApi = {
  async evaluateSession(sessionId: string): Promise<EvaluationResponse> {
    const request: EvaluationRequest = { session_id: sessionId };
    
    const response = await axios.post<EvaluationResponse>(
      apiUrl('/eval/session/evaluate'),
      request,
      {
        headers: getAuthHeaders()
      }
    );
    
    return response.data;
  }
};