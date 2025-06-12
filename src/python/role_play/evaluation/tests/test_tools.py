import unittest
from unittest import mock # Correct import for mock
from typing import List, Dict

from src.python.role_play.evaluation.tools import (
    get_chat_history,
    get_scenario_details,
    get_user_past_summaries,
    store_final_review,
)

class TestEvaluationTools(unittest.TestCase):

    def test_get_chat_history(self):
        session_id = "test_session_123"
        # Since it's a placeholder, just check if it runs and returns a string
        with mock.patch("builtins.print") as mock_print: # Suppress print
            result = get_chat_history(session_id)
            self.assertIsInstance(result, str)
            self.assertIn(session_id, result)
            mock_print.assert_called_with(f"Fetching chat history for session_id: {session_id}")

    def test_get_scenario_details(self):
        scenario_id = "test_scenario_abc"
        language = "zh-TW"
        # Check if it runs and returns a dict
        with mock.patch("builtins.print") as mock_print: # Suppress print
            result = get_scenario_details(scenario_id, language)
            self.assertIsInstance(result, Dict)
            self.assertEqual(result.get("scenario_id"), scenario_id)
            mock_print.assert_called_with(f"Fetching scenario details for scenario_id: {scenario_id}, language: {language}")

    def test_get_user_past_summaries(self):
        user_id = "test_user_789"
        # Check if it runs and returns a list
        with mock.patch("builtins.print") as mock_print: # Suppress print
            result = get_user_past_summaries(user_id)
            self.assertIsInstance(result, List)
            # Placeholder returns a list with one item
            self.assertTrue(len(result) >= 0)
            if len(result) > 0:
                self.assertIsInstance(result[0], Dict)
            mock_print.assert_called_with(f"Fetching past summaries for user_id: {user_id}")

    def test_store_final_review(self):
        user_id = "test_user_xyz"
        session_id = "test_session_pqr"
        review_data = {"overall_score": 0.9, "feedback": "Excellent"}
        # Check if it runs (returns None)
        with mock.patch("builtins.print") as mock_print: # Suppress print
            result = store_final_review(user_id, session_id, review_data)
            self.assertIsNone(result)
            mock_print.assert_called_with(f"Storing final review for user_id: {user_id}, session_id: {session_id}, review: {review_data}")

if __name__ == "__main__":
    unittest.main()
