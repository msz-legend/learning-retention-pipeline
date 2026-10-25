import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.feedback import FeedbackPolicy, FeedbackOrderError, update_mastery


class Task05FeedbackTests(unittest.TestCase):
    def test_feedback_cannot_be_recorded_before_learner_output(self):
        policy = FeedbackPolicy()
        with self.assertRaises(FeedbackOrderError):
            policy.record_feedback({"output_received": False}, ["missing key"])

    def test_feedback_records_at_most_two_key_errors(self):
        policy = FeedbackPolicy()
        with self.assertRaises(ValueError):
            policy.record_feedback({"output_received": True}, ["e1", "e2", "e3"])

    def test_mastery_uses_recent_three_weighted_valid_attempts(self):
        attempts = [
            {"task_score": 0.4, "mastery_weight": 1.0},
            {"task_score": 0.8, "mastery_weight": 1.0},
            {"task_score": 1.0, "mastery_weight": 1.0},
        ]
        self.assertAlmostEqual(update_mastery(attempts), 0.82)

    def test_non_output_attempt_does_not_change_mastery(self):
        attempts = [{"task_score": None, "valid": False}]
        self.assertIsNone(update_mastery(attempts))


if __name__ == "__main__":
    unittest.main()
