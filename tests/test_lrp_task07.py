import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.mode import ModePolicy, ModePolicyError
from learning_retention.transition import can_enter_autonomous


class Task07AutonomousTests(unittest.TestCase):
    def test_real_task_failure_cannot_leave_autonomous(self):
        state = {"learning_mode": "learn", "current_phase": "autonomous"}
        with self.assertRaises(ModePolicyError):
            ModePolicy().complete_autonomous(state, real_task_passed=False)
        self.assertEqual(state["current_phase"], "autonomous")

    def test_learn_success_records_completion_evidence_and_no_retention_fields(self):
        state = {"learning_mode": "learn", "current_phase": "autonomous", "active_task": {"task_id": "real-1"}}
        updated = ModePolicy().complete_autonomous(state, real_task_passed=True, output_ref="outputs/real-1/metadata.json")
        self.assertEqual(updated["current_phase"], "completed")
        self.assertEqual(updated["completion_evidence"], "outputs/real-1/metadata.json")
        self.assertNotIn("retention_due", updated)
        self.assertEqual(updated["scheduler_state"]["queue"], [])

    def test_learn_retain_success_requires_three_held_out_tasks_and_baseline(self):
        state = {
            "learning_mode": "learn_retain", "current_phase": "autonomous",
            "held_out_tasks": [{"id": "1"}, {"id": "2"}], "baseline_retention_score": 0.7,
        }
        with self.assertRaises(ModePolicyError):
            ModePolicy().complete_autonomous(state, real_task_passed=True)

        state["held_out_tasks"].append({"id": "3"})
        updated = ModePolicy().complete_autonomous(state, real_task_passed=True, output_ref="outputs/real-1/metadata.json")
        self.assertEqual(updated["current_phase"], "retention")
        self.assertEqual(updated["completion_evidence"], "outputs/real-1/metadata.json")


if __name__ == "__main__":
    unittest.main()
