from pydantic import BaseModel, Field
from typing import List, Optional
from enum import IntEnum

class SkillScore(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class ConfidenceScore(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class SpecializedAssessment(BaseModel):
    assessment_area: str = Field(description="The area being assessed, e.g., 'empathy'.")
    score: SkillScore = Field(description="A score for this area: 1 (Low), 2 (Medium), or 3 (High).")
    confidence: ConfidenceScore = Field(description="The model's confidence in its score: 1 (Low), 2 (Medium), or 3 (High).")
    positive_points_zh: List[str] = Field(description="List of observed strengths in Traditional Chinese.")
    improvement_areas_zh: List[str] = Field(description="List of areas for improvement in Traditional Chinese.")
    specific_suggestions_zh: List[str] = Field(description="Concrete suggestions for the user in Traditional Chinese.")
    notes_zh: Optional[str] = Field(default=None, description="MUST be provided if confidence is Medium or Low, explaining the reason for the uncertainty.")

class FinalReviewReport(BaseModel):
    user_id: str
    scenario_id: str
    chat_session_id: str
    overall_score: float = Field(description="Aggregated and normalized score from all reviewers, ranging from 0.0 to 1.0.")
    human_review_recommended: bool = Field(description="True if all specialized reviewers reported low confidence, flagging this session for manual review.")
    overall_assessment_zh: str
    key_strengths_demonstrated_zh: List[str]
    key_areas_for_development_zh: List[str]
    actionable_next_steps_zh: List[str]
    progress_notes_from_past_feedback_zh: str
