import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.feedback import FeedbackPolicy
from learning_retention.mode import ModePolicy
from learning_retention.retention import RetentionPolicy
from learning_retention.scheduler import SimpleIntervalScheduler
from learning_retention.state import StateStore


class Task11ACoreE2ETests(unittest.TestCase):
    def test_learn_mode_survives_two_sessions_and_completes_without_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {"goal": "complete a real analysis"})
            state = ModePolicy().apply_selection(state, "learn", confirmed=True)
            state["subskills"] = [
                {"id": "import", "dependencies": [], "mastery_level": 0.6},
                {"id": "clean", "dependencies": ["import"], "mastery_level": 0.8},
                {"id": "explain", "dependencies": [], "mastery_level": 0.8},
            ]
            state["current_phase"] = "associative"
            state["last_session_summary"] = "正在交错练习导入与解释"
            store.save(state)

            resumed = store.load(state["state_id"])
            self.assertEqual(resumed["last_session_summary"], "正在交错练习导入与解释")
            resumed = ModePolicy().complete_autonomous(resumed, real_task_passed=True, output_ref="outputs/real-1/metadata.json")
            store.save(resumed)
            completed = store.load(resumed["state_id"])
            self.assertEqual(completed["current_phase"], "completed")
            self.assertNotIn("retention_due", completed)
            self.assertEqual(completed["scheduler_state"]["queue"], [])

    def test_retain_mode_runs_due_test_and_requires_held_out_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {"goal": "retain skill"})
            state = ModePolicy().apply_selection(state, "learn_retain", confirmed=True)
            state.update({
                "current_phase": "autonomous",
                "held_out_tasks": [{"id": "h1"}, {"id": "h2"}, {"id": "h3"}],
                "baseline_retention_score": 0.7,
            })
            state = ModePolicy().complete_autonomous(state, real_task_passed=True, output_ref="outputs/real-1/metadata.json")
            state["retention_due"] = "2026-01-01"
            store.save(state)
            resumed = store.load(state["state_id"])
            self.assertEqual(len(RetentionPolicy().schedule(resumed, today=date(2026, 1, 2))), 1)

    def test_practice_contract_and_interleaved_plan_are_observable(self):
        policy = FeedbackPolicy()
        attempt = policy.record_feedback({"output_received": True}, ["missing acceptance criterion"])
        self.assertTrue(attempt["feedback_recorded"])
        state = {"subskills": [
            {"id": "a", "dependencies": [], "mastery_level": 0.7},
            {"id": "b", "dependencies": [], "mastery_level": 0.7},
        ]}
        tasks = SimpleIntervalScheduler(today=date(2026, 1, 1)).next_tasks(state)
        task_types = {task["task_type"] for task in tasks}
        self.assertTrue({"retrieval", "variation", "interleaved"}.issubset(task_types))


if __name__ == "__main__":
    unittest.main()
