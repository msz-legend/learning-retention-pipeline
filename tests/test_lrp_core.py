import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.feedback import score_attempt
from learning_retention.mode import ModePolicy, ModePolicyError
from learning_retention.scheduler import DependencyScheduler, SimpleIntervalScheduler


class LrpCoreContractTests(unittest.TestCase):
    def test_score_uses_criteria_penalty_and_completion_weight(self):
        result = score_attempt(
            passed_criteria=4,
            total_criteria=5,
            critical_error_count=2,
            completion_mode="first_unprompted",
        )
        self.assertAlmostEqual(result.task_score, 0.6)
        self.assertEqual(result.mastery_weight, 1.0)

    def test_learn_completion_has_no_retention_schedule(self):
        state = {"learning_mode": "learn", "current_phase": "autonomous", "retention_due": None}
        updated = ModePolicy().complete_autonomous(state, real_task_passed=True)
        self.assertEqual(updated["current_phase"], "completed")
        self.assertNotIn("retention_due", updated)

    def test_dependency_scheduler_hides_blocked_tasks(self):
        state = {"subskills": [
            {"id": "a", "dependencies": [], "mastery_level": 0.4},
            {"id": "b", "dependencies": ["a"], "mastery_level": 0.0},
        ]}
        tasks = DependencyScheduler().next_tasks(state)
        self.assertEqual([task["subskill_id"] for task in tasks], ["a"])

    def test_interval_scheduler_emits_spacing_retrieval_variation_interleaving(self):
        state = {"learning_mode": "learn", "scheduler_state": {"interval_index": 0}, "subskills": [
            {"id": "a", "dependencies": [], "mastery_level": 0.7, "retention_due": None},
            {"id": "b", "dependencies": [], "mastery_level": 0.7, "retention_due": None},
        ]}
        tasks = SimpleIntervalScheduler(today=date(2026, 1, 1)).next_tasks(state)
        kinds = {task["task_type"] for task in tasks}
        self.assertTrue({"retrieval", "variation", "interleaved"}.issubset(kinds))

    def test_invalid_mode_change_is_rejected(self):
        with self.assertRaises(ModePolicyError):
            ModePolicy().downgrade({"learning_mode": "learn", "current_phase": "completed"}, confirmed=True)


if __name__ == "__main__":
    unittest.main()
