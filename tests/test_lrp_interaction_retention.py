import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.feedback import score_attempt
from learning_retention.interaction import parse_signal, progress_summary
from learning_retention.retention import assess_retention, postpone_due
from learning_retention.validation import validate_decomposition


class LrpInteractionRetentionTests(unittest.TestCase):
    def test_feedback_rejects_more_than_two_critical_errors(self):
        with self.assertRaises(ValueError):
            score_attempt(passed_criteria=3, total_criteria=5, critical_error_count=3, completion_mode="retry")

    def test_decomposition_rejects_dependency_cycle(self):
        result = validate_decomposition([
            {"id": "a", "dependencies": ["b"], "acceptance_criteria": ["x"]},
            {"id": "b", "dependencies": ["a"], "acceptance_criteria": ["y"]},
            {"id": "c", "dependencies": [], "acceptance_criteria": ["z"]},
        ])
        self.assertFalse(result.valid)
        self.assertIn("dependency_cycle", result.errors)

    def test_due_postponement_does_not_fake_success(self):
        updated = postpone_due({"scheduler_state": {"postponements": 0}, "retention_due": "2026-01-01"})
        self.assertEqual(updated["retention_due"], "2026-01-02")
        self.assertEqual(updated["scheduler_state"]["postponements"], 1)

    def test_retention_decline_triggers_repair(self):
        result = assess_retention(score=0.5, best_score=0.8)
        self.assertTrue(result.repair_triggered)

    def test_signal_and_progress_are_natural_language(self):
        self.assertEqual(parse_signal("太难了"), "too_difficult")
        text = progress_summary({"current_phase": "associative", "learning_mode": "learn", "subskills": []})
        self.assertIn("联结阶段", text)
        self.assertNotEqual(text.strip(), "{}")


if __name__ == "__main__":
    unittest.main()
