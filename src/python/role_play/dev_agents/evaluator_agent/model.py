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
    """
    Defines the structured output for a specialized review agent (e.g., Empathy, Clarity).
    Each agent instance will produce one of these objects.
    """
    assessment_area: str = Field(
        description="The specific skill or area being assessed, e.g., 'empathy'."
    )
    score: SkillScore = Field(
        description="A score for this area: 1 (Low), 2 (Medium), or 3 (High)."
    )
    confidence: ConfidenceScore = Field(
        description="The model's confidence in its score: 1 (Low), 2 (Medium), or 3 (High)."
    )
    positive_points: List[str] = Field(
        description="List of observed strengths in localized language."
    )
    improvement_areas: List[str] = Field(
        description="List of areas needing improvement in localized language."
    )
    specific_suggestions: List[str] = Field(
        description="Concrete, actionable suggestions for the user in localized language."
    )
    notes: Optional[str] = Field(
        default=None,
        description="MUST be provided if confidence is Medium or Low, explaining the reason for the uncertainty."
    )


class FinalReviewReport(BaseModel):
    """
    Defines the structure for the final, consolidated review report that is
    synthesized by the ReviewSummarizerAgent and stored.
    """
    user_id: str = Field(description="The unique identifier for the user.")
    scenario_id: str = Field(description="The unique identifier for the scenario.")
    chat_session_id: str = Field(description="The unique identifier for the chat session being evaluated.")
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

