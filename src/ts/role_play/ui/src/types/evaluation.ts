// src/ts/role_play/ui/src/types/evaluation.ts
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
