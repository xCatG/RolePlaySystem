export enum Score {
  low = "low",
  med = "med",
  high = "high"
}

export interface FinalReviewReport {
  chat_session_id: string;
  overall_score: number;
  human_review_recommended: boolean;
  overall_assessment: string;
  key_strengths_demonstrated: string[];
  key_areas_for_development: string[];
  actionable_next_steps: string[];
  progress_notes_from_past_feedback: string;
}

export interface EvaluationRequest {
  session_id: string;
}

export interface EvaluationResponse {
  success: boolean;
  session_id: string;
  evaluation_type?: string;
  message?: string | null;
  report?: FinalReviewReport;
  final_review_report?: FinalReviewReport;
  error?: string;
}

export interface StoredEvaluationReport {
  success: boolean;
  report_id: string;
  chat_session_id: string;
  created_at: string;
  evaluation_type: string;
  report: FinalReviewReport;
}

export interface EvaluationReportSummary {
  report_id: string;
  chat_session_id: string;
  created_at: string;
  evaluation_type: string;
}

export interface EvaluationReportListResponse {
  success: boolean;
  reports: EvaluationReportSummary[];
}