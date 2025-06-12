"""
This module defines the Pydantic data models for the multi-agent evaluation system.

These models enforce a consistent, structured data format for communication between
the evaluation agents and for storing the final results.
"""

from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class SkillScore(IntEnum):
    """Enumeration for skill assessment scoring."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class ConfidenceScore(IntEnum):
    """Enumeration for an agent's confidence in its assessment."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class SpecializedAssessment(BaseModel):
    """Structured output for a specialized review agent."""

    assessment_area: str = Field(
        description="The area being assessed, e.g., 'empathy'."
    )
    language: str = Field(
        description="The language for the assessment, e.g., 'English', 'Traditional Chinese'."
    )
    score: SkillScore = Field(
        description="A score for this area: 1 (Low), 2 (Medium), or 3 (High)."
    )
    confidence: ConfidenceScore = Field(
        description="The model's confidence in its score: 1 (Low), 2 (Medium), or 3 (High)."
    )
    positive_points: List[str] = Field(
        description="List of observed strengths. The text must be in the specified language."
    )
    improvement_areas: List[str] = Field(
        description="List of areas for improvement. The text must be in the specified language."
    )
    specific_suggestions: List[str] = Field(
        description="Concrete suggestions for the user. The text must be in the specified language."
    )
    notes: Optional[str] = Field(
        default=None,
        description=(
            "MUST be provided if confidence is Medium or Low, explaining the reason for the uncertainty. "
            "The text must be in the specified language."
        ),
    )


class FinalReviewReport(BaseModel):
    """
    Defines the structure for the final, consolidated review report that is
    synthesized by the ReviewSummarizerAgent and stored.
    """
    user_id: str
    scenario_id: str
    chat_session_id: str
    language: str = Field(
        description="The full language name for the report, e.g., 'English', 'Traditional Chinese'."
    )
    overall_score: float = Field(
        description="Aggregated and normalized score from all reviewers, ranging from 0.0 to 1.0."
    )
    human_review_recommended: bool = Field(
        description="True if all specialized reviewers reported low confidence, flagging this session for manual review."
    )
    overall_assessment: str = Field(
        description="A holistic, narrative summary of the user's performance in localized language."
    )
    key_strengths_demonstrated: List[str] = Field(
        description="A synthesized list of key strengths from all assessments, in localized language."
    )
    key_areas_for_development: List[str] = Field(
        description="A synthesized list of key areas for development from all assessments, in localized language."
    )
    actionable_next_steps: List[str] = Field(
        description="A list of 3-5 concrete, actionable steps for the user to take next, in localized language."
    )
    progress_notes_from_past_feedback: str = Field(
        description="Notes on the user's progress or recurring themes when compared to past feedback, in localized language."
    )


