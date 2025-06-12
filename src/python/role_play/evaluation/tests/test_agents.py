import unittest
from unittest import mock # Correct import for mock

from src.python.role_play.evaluation.agents import (
    LlmAgent, # Placeholder base
    SpecializedReviewAgent,
    ReviewSummarizerAgent,
    ReviewCoordinatorAgent,
)
from src.python.role_play.evaluation.models import SkillScore, ConfidenceScore, SpecializedAssessment, FinalReviewReport

# Define a concrete LlmAgent for testing if needed, or mock its process method directly
class ConcreteLlmAgent(LlmAgent):
    def process(self, data: dict) -> dict:
        return super().process(data)

class TestEvaluationAgents(unittest.TestCase):

    def test_specialized_review_agent_initialization(self):
        config = {"name": "TestClarityAgent", "skill": "clarity", "prompt": "Evaluate clarity."}
        agent = SpecializedReviewAgent(config)
        self.assertEqual(agent.config, config)
        self.assertEqual(agent.skill, "clarity")

    def test_specialized_review_agent_process_placeholder(self):
        config = {"skill": "empathy"}
        agent = SpecializedReviewAgent(config)

        # Since it's a placeholder, it returns a fixed dict
        # We mock print to avoid console output during tests
        with mock.patch("builtins.print") as mock_print:
            result = agent.process({"chat_history": "...", "scenario_details": "{}"})

        self.assertIsInstance(result, dict)
        self.assertEqual(result["assessment_area"], "empathy")
        self.assertIn("score", result)
        self.assertIn("confidence", result)
        self.assertIn("positive_points_zh", result)
        self.assertIn("improvement_areas_zh", result)
        self.assertIn("specific_suggestions_zh", result)

        # Test notes_zh presence based on confidence (as per placeholder logic)
        if result["confidence"] in [ConfidenceScore.LOW, ConfidenceScore.MEDIUM]:
            self.assertIsNotNone(result.get("notes_zh"))
            self.assertIn("信心度", result["notes_zh"]) # Placeholder note contains this
        else:
            # Current placeholder always returns MEDIUM, so this branch may not be hit
            # without modifying the placeholder or mocking its internal logic
            self.assertNotIn("notes_zh", result)


    def test_review_summarizer_agent_initialization(self):
        config = {"name": "TestSummarizer"} # Example config
        agent = ReviewSummarizerAgent(config)
        self.assertEqual(agent.config, config)

    def test_review_summarizer_agent_process_placeholder(self):
        agent = ReviewSummarizerAgent({}) # Empty config for placeholder

        sample_assessment_1 = SpecializedAssessment(
            assessment_area="clarity", score=SkillScore.HIGH, confidence=ConfidenceScore.HIGH,
            positive_points_zh=["p1"], improvement_areas_zh=["i1"], specific_suggestions_zh=["s1"]
        )
        sample_assessment_2 = SpecializedAssessment(
            assessment_area="empathy", score=SkillScore.MEDIUM, confidence=ConfidenceScore.MEDIUM,
            positive_points_zh=["p2"], improvement_areas_zh=["i2"], specific_suggestions_zh=["s2"],
            notes_zh="note2"
        )

        input_data = {
            "assessments": [sample_assessment_1, sample_assessment_2],
            "past_summaries": [{"summary_id": "s1", "report": "Past report"}],
            "human_review_recommended": False,
            "user_id": "user1",
            "scenario_id": "scene1",
            "chat_session_id": "session1"
        }

        with mock.patch("builtins.print") as mock_print: # Suppress print
            result = agent.process(input_data)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["user_id"], "user1")
        self.assertEqual(result["scenario_id"], "scene1")
        self.assertEqual(result["chat_session_id"], "session1")
        self.assertFalse(result["human_review_recommended"])

        # Overall score calculation: (HIGH (3) + MEDIUM (2)) / (2 assessments * 3 max_score) = 5 / 6
        expected_score = (SkillScore.HIGH.value + SkillScore.MEDIUM.value) / (2 * 3)
        self.assertAlmostEqual(result["overall_score"], expected_score)

        self.assertIn("overall_assessment_zh", result)
        self.assertIsInstance(result["key_strengths_demonstrated_zh"], list)
        self.assertIsInstance(result["key_areas_for_development_zh"], list)
        self.assertIsInstance(result["actionable_next_steps_zh"], list)
        self.assertIn("progress_notes_from_past_feedback_zh", result)

    def test_review_coordinator_agent_initialization(self):
        coordinator_config = {"name": "MainCoordinator"}
        mock_specialized_agent = mock.Mock(spec=SpecializedReviewAgent)
        agent = ReviewCoordinatorAgent(coordinator_config, [mock_specialized_agent])

        self.assertEqual(agent.config, coordinator_config)
        self.assertEqual(len(agent.specialized_agents), 1)
        self.assertEqual(agent.specialized_agents[0], mock_specialized_agent)

    @mock.patch("src.python.role_play.evaluation.agents.store_final_review")
    @mock.patch("src.python.role_play.evaluation.agents.get_user_past_summaries")
    @mock.patch("src.python.role_play.evaluation.agents.get_scenario_details")
    @mock.patch("src.python.role_play.evaluation.agents.get_chat_history")
    def test_review_coordinator_agent_process_flow(
        self,
        mock_get_chat_history,
        mock_get_scenario_details,
        mock_get_user_past_summaries,
        mock_store_final_review
    ):
        # Mock data returned by tools
        mock_get_chat_history.return_value = "Full chat transcript"
        mock_get_scenario_details.return_value = {"id": "scenario1", "details": "Details..."}
        mock_get_user_past_summaries.return_value = [{"report_id": "rep1", "feedback": "Old feedback"}]

        # Mock Specialized Agents
        mock_spec_agent1 = mock.Mock(spec=SpecializedReviewAgent)
        mock_spec_agent1.process.return_value = { # This needs to be a dict, not an object
            "assessment_area": "clarity", "score": SkillScore.HIGH, "confidence": ConfidenceScore.HIGH,
            "positive_points_zh": ["p1"], "improvement_areas_zh": ["i1"], "specific_suggestions_zh": ["s1"]
        }

        mock_spec_agent2 = mock.Mock(spec=SpecializedReviewAgent)
        mock_spec_agent2.process.return_value = {
            "assessment_area": "empathy", "score": SkillScore.LOW, "confidence": ConfidenceScore.LOW,
            "positive_points_zh": ["p2"], "improvement_areas_zh": ["i2"], "specific_suggestions_zh": ["s2"],
            "notes_zh": "Low confidence due to insufficient data."
        }

        # Mock ReviewSummarizerAgent
        # The coordinator instantiates this, so we need to patch its constructor and process
        mock_summarizer_instance = mock.Mock(spec=ReviewSummarizerAgent)
        mock_summarizer_instance.process.return_value = { # Expected dict for FinalReviewReport
            "user_id": "user123", "scenario_id": "scene123", "chat_session_id": "sess123",
            "overall_score": 0.6, "human_review_recommended": True, # Based on Low confidence from spec_agent2
            "overall_assessment_zh": "Needs improvement.",
            "key_strengths_demonstrated_zh": [], "key_areas_for_development_zh": ["empathy"],
            "actionable_next_steps_zh": ["practice empathy"], "progress_notes_from_past_feedback_zh": "None"
        }

        coordinator_config = {"name": "TestCoordinator"}

        with mock.patch("src.python.role_play.evaluation.agents.ReviewSummarizerAgent", return_value=mock_summarizer_instance) as mock_summarizer_class:
            coordinator = ReviewCoordinatorAgent(coordinator_config, [mock_spec_agent1, mock_spec_agent2])

            result = coordinator.process(session_id="sess123", user_id="user123", scenario_id="scene123")

        # Assertions
        mock_get_chat_history.assert_called_once_with("sess123")
        mock_get_scenario_details.assert_called_once_with("scene123", language="zh-TW")
        mock_get_user_past_summaries.assert_called_once_with("user123")

        mock_spec_agent1.process.assert_called_once()
        mock_spec_agent2.process.assert_called_once()

        # Check human_review_recommended logic (one LOW confidence should trigger it)
        # The summarizer agent is called with human_review_recommended=True
        summarizer_input_data = mock_summarizer_instance.process.call_args[0][0]
        self.assertTrue(summarizer_input_data["human_review_recommended"])

        mock_summarizer_class.assert_called_once_with({}) # Check it was initialized (config is {} in coordinator)
        mock_summarizer_instance.process.assert_called_once()

        # Check that store_final_review was called with a FinalReviewReport instance (or its dict representation)
        mock_store_final_review.assert_called_once()
        args, _ = mock_store_final_review.call_args
        self.assertEqual(args[0], "user123") # user_id
        self.assertEqual(args[1], "sess123") # session_id
        self.assertIsInstance(args[2], dict) # final_report.dict()
        self.assertEqual(args[2]["overall_score"], 0.6) # From mock_summarizer_instance

        self.assertEqual(result, {"status": "success", "report_id": "sess123"})


    def test_review_coordinator_human_review_logic(self):
        # Test human_review_recommended logic more directly
        mock_assessment_low_conf = SpecializedAssessment(
            assessment_area="clarity", score=SkillScore.MEDIUM, confidence=ConfidenceScore.LOW,
            positive_points_zh=[], improvement_areas_zh=[], specific_suggestions_zh=[], notes_zh="low conf"
        )
        mock_assessment_high_conf = SpecializedAssessment(
            assessment_area="empathy", score=SkillScore.HIGH, confidence=ConfidenceScore.HIGH,
            positive_points_zh=[], improvement_areas_zh=[], specific_suggestions_zh=[]
        )

        # Scenario 1: All LOW confidence
        with mock.patch("src.python.role_play.evaluation.agents.SpecializedAssessment", side_effect=[mock_assessment_low_conf, mock_assessment_low_conf]):
            # We need to mock the process methods of the specialized agents within the coordinator
            mock_spec_agent_returns_low_conf = mock.Mock(spec=SpecializedReviewAgent)
            mock_spec_agent_returns_low_conf.process.return_value = mock_assessment_low_conf.dict()

            mock_summarizer_instance = mock.Mock(spec=ReviewSummarizerAgent)
            mock_summarizer_instance.process.return_value = FinalReviewReport(
                 user_id="u", scenario_id="s", chat_session_id="c", overall_score=0.1, human_review_recommended=True,
                 overall_assessment_zh="oa", key_strengths_demonstrated_zh=[], key_areas_for_development_zh=[],
                 actionable_next_steps_zh=[], progress_notes_from_past_feedback_zh="p"
            ).dict()

            with mock.patch("src.python.role_play.evaluation.agents.get_chat_history", return_value=""), \
                 mock.patch("src.python.role_play.evaluation.agents.get_scenario_details", return_value={}), \
                 mock.patch("src.python.role_play.evaluation.agents.get_user_past_summaries", return_value=[]), \
                 mock.patch("src.python.role_play.evaluation.agents.store_final_review"), \
                 mock.patch("src.python.role_play.evaluation.agents.ReviewSummarizerAgent", return_value=mock_summarizer_instance):

                coordinator = ReviewCoordinatorAgent({}, [mock_spec_agent_returns_low_conf, mock_spec_agent_returns_low_conf])
                coordinator.process("s1", "u1", "sc1")

                call_args_to_summarizer = mock_summarizer_instance.process.call_args[0][0]
                self.assertTrue(call_args_to_summarizer["human_review_recommended"])


        # Scenario 2: Mixed confidence (one LOW, one HIGH)
        mock_spec_agent_low = mock.Mock(spec=SpecializedReviewAgent)
        mock_spec_agent_low.process.return_value = mock_assessment_low_conf.dict()
        mock_spec_agent_high = mock.Mock(spec=SpecializedReviewAgent)
        mock_spec_agent_high.process.return_value = mock_assessment_high_conf.dict()

        mock_summarizer_instance_mixed = mock.Mock(spec=ReviewSummarizerAgent)
        mock_summarizer_instance_mixed.process.return_value = FinalReviewReport(
             user_id="u", scenario_id="s", chat_session_id="c", overall_score=0.5, human_review_recommended=False, # Should be False if not ALL LOW
             overall_assessment_zh="oa", key_strengths_demonstrated_zh=[], key_areas_for_development_zh=[],
             actionable_next_steps_zh=[], progress_notes_from_past_feedback_zh="p"
        ).dict()

        with mock.patch("src.python.role_play.evaluation.agents.get_chat_history", return_value=""), \
             mock.patch("src.python.role_play.evaluation.agents.get_scenario_details", return_value={}), \
             mock.patch("src.python.role_play.evaluation.agents.get_user_past_summaries", return_value=[]), \
             mock.patch("src.python.role_play.evaluation.agents.store_final_review"), \
             mock.patch("src.python.role_play.evaluation.agents.ReviewSummarizerAgent", return_value=mock_summarizer_instance_mixed):

            coordinator = ReviewCoordinatorAgent({}, [mock_spec_agent_low, mock_spec_agent_high])
            coordinator.process("s2", "u2", "sc2")

            call_args_to_summarizer_mixed = mock_summarizer_instance_mixed.process.call_args[0][0]
            # human_review_recommended is True if ALL specialized reviewers reported low confidence.
            # In this case, one is LOW, one is HIGH, so it should be False.
            self.assertFalse(call_args_to_summarizer_mixed["human_review_recommended"])


if __name__ == "__main__":
    unittest.main()
