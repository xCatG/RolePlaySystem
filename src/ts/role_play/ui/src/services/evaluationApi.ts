import axios from 'axios';
import { apiUrl, getAuthHeaders } from './apiConfig';
import type { 
  EvaluationRequest, 
  EvaluationResponse, 
  StoredEvaluationReport,
  EvaluationReportListResponse 
} from '@/types/evaluation';

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
  },

  async getLatestReport(sessionId: string): Promise<StoredEvaluationReport | null> {
    try {
      const response = await axios.get<StoredEvaluationReport>(
        apiUrl(`/eval/session/${sessionId}/report`),
        {
          headers: getAuthHeaders()
        }
      );
      
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  },

  async createNewEvaluation(sessionId: string, evaluationType: string = 'comprehensive'): Promise<EvaluationResponse> {
    const response = await axios.post<EvaluationResponse>(
      apiUrl(`/eval/session/${sessionId}/evaluate?evaluation_type=${evaluationType}`),
      {},
      {
        headers: getAuthHeaders()
      }
    );
    
    return response.data;
  },

  async listAllReports(sessionId: string): Promise<EvaluationReportListResponse> {
    const response = await axios.get<EvaluationReportListResponse>(
      apiUrl(`/eval/session/${sessionId}/all_reports`),
      {
        headers: getAuthHeaders()
      }
    );
    
    return response.data;
  },

  async getReportById(reportId: string): Promise<StoredEvaluationReport> {
    const response = await axios.get<StoredEvaluationReport>(
      apiUrl(`/eval/reports/${reportId}`),
      {
        headers: getAuthHeaders()
      }
    );
    
    return response.data;
  }
};