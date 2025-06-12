import unittest
from pydantic import ValidationError

from src.python.role_play.evaluation.models import (
    SkillScore,
    ConfidenceScore,
    SpecializedAssessment,
    FinalReviewReport,
)

class TestEvaluationModels(unittest.TestCase):

    def test_skill_score_enum(self):
        self.assertEqual(SkillScore.LOW, 1)
        self.assertEqual(SkillScore.MEDIUM, 2)
        self.assertEqual(SkillScore.HIGH, 3)
        with self.assertRaises(AttributeError):
            SkillScore.VERY_HIGH

    def test_confidence_score_enum(self):
        self.assertEqual(ConfidenceScore.LOW, 1)
        self.assertEqual(ConfidenceScore.MEDIUM, 2)
        self.assertEqual(ConfidenceScore.HIGH, 3)
        with self.assertRaises(AttributeError):
            ConfidenceScore.VERY_HIGH

    def test_specialized_assessment_instantiation(self):
        assessment_data = {
            "assessment_area": "empathy",
            "score": SkillScore.HIGH,
            "confidence": ConfidenceScore.HIGH,
            "positive_points_zh": ["表現出良好的同理心"],
            "improvement_areas_zh": ["無明顯不足"],
            "specific_suggestions_zh": ["繼續保持"],
        }
        assessment = SpecializedAssessment(**assessment_data)
        self.assertEqual(assessment.assessment_area, "empathy")
        self.assertEqual(assessment.score, SkillScore.HIGH)
        self.assertEqual(assessment.confidence, ConfidenceScore.HIGH)
        self.assertIsNone(assessment.notes_zh)

    def test_specialized_assessment_notes_requirement(self):
        # Test that notes_zh is required for MEDIUM confidence
        with self.assertRaises(ValidationError) as context:
            SpecializedAssessment(
                assessment_area="clarity",
                score=SkillScore.MEDIUM,
                confidence=ConfidenceScore.MEDIUM, # Notes should be required
                positive_points_zh=["清晰"],
                improvement_areas_zh=["有些地方可以更簡潔"],
                specific_suggestions_zh=["嘗試用更少的詞"],
                # notes_zh is missing
            )
        # Pydantic v2 includes more details in the error, check for field name
        self.assertIn("'notes_zh'", str(context.exception))
        self.assertIn("Field required", str(context.exception))


        # Test that notes_zh is required for LOW confidence
        with self.assertRaises(ValidationError) as context:
            SpecializedAssessment(
                assessment_area="clarity",
                score=SkillScore.LOW,
                confidence=ConfidenceScore.LOW, # Notes should be required
                positive_points_zh=["部分清晰"],
                improvement_areas_zh=["多數地方不清晰"],
                specific_suggestions_zh=["重組句子結構"],
                # notes_zh is missing
            )
        self.assertIn("'notes_zh'", str(context.exception))
        self.assertIn("Field required", str(context.exception))

        # Test that notes_zh is NOT required for HIGH confidence
        try:
            SpecializedAssessment(
                assessment_area="clarity",
                score=SkillScore.HIGH,
                confidence=ConfidenceScore.HIGH,
                positive_points_zh=["非常清晰"],
                improvement_areas_zh=[],
                specific_suggestions_zh=[],
                # notes_zh is not provided, and should not be required
            )
        except ValidationError:
            self.fail("ValidationError raised unexpectedly for HIGH confidence without notes_zh")

        # Test that notes_zh is accepted when provided
        assessment_with_notes = SpecializedAssessment(
            assessment_area="clarity",
            score=SkillScore.MEDIUM,
            confidence=ConfidenceScore.MEDIUM,
            positive_points_zh=["清晰"],
            improvement_areas_zh=["有些地方可以更簡潔"],
            specific_suggestions_zh=["嘗試用更少的詞"],
            notes_zh="信心度中等，因為評估資料不足"
        )
        self.assertEqual(assessment_with_notes.notes_zh, "信心度中等，因為評估資料不足")


    def test_final_review_report_instantiation(self):
        report_data = {
            "user_id": "user123",
            "scenario_id": "scenario789",
            "chat_session_id": "chat_session_abc",
            "overall_score": 0.85,
            "human_review_recommended": False,
            "overall_assessment_zh": "整體表現良好",
            "key_strengths_demonstrated_zh": ["同理心強", "溝通清晰"],
            "key_areas_for_development_zh": ["語氣可以更堅定"],
            "actionable_next_steps_zh": ["練習在壓力下保持堅定語氣"],
            "progress_notes_from_past_feedback_zh": "在同理心方面有顯著進步",
        }
        report = FinalReviewReport(**report_data)
        self.assertEqual(report.user_id, "user123")
        self.assertEqual(report.overall_score, 0.85)
        self.assertFalse(report.human_review_recommended)

if __name__ == "__main__":
    unittest.main()
