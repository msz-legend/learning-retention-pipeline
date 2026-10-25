import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.interaction import parse_signal, progress_summary
from learning_retention.mode import ModePolicy
from learning_retention.retention import RetentionPolicy


class Task11BFullE2ETests(unittest.TestCase):
    def test_required_user_signals_map_to_actions(self):
        expected = {
            "太难了": "too_difficult", "太简单了": "too_easy", "没时间": "no_time",
            "暂停": "pause", "继续": "resume", "我学到哪了": "progress",
            "我想继续保持": "upgrade", "我不想保持了": "downgrade", "我懂了": "claims_understanding",
        }
        for text, action in expected.items():
            with self.subTest(text=text):
                self.assertEqual(parse_signal(text), action)

    def test_upgrade_and_downgrade_are_explicit_and_audited(self):
        policy = ModePolicy()
        completed = {"learning_mode": "learn", "current_phase": "completed"}
        upgraded = policy.upgrade(completed, confirmed=True, held_out_tasks=[{"id": "h1"}, {"id": "h2"}, {"id": "h3"}], baseline_score=0.7)
        self.assertEqual(upgraded["current_phase"], "retention")
        self.assertEqual(upgraded["upgrade_history"][-1]["action"], "upgrade")
        downgraded = policy.downgrade(upgraded, confirmed=True)
        self.assertEqual((downgraded["learning_mode"], downgraded["current_phase"]), ("learn", "completed"))
        self.assertEqual(downgraded["upgrade_history"][-1]["action"], "downgrade")

    def test_completed_state_has_no_retention_schedule_or_pressure_language(self):
        state = {"current_phase": "completed", "learning_mode": "learn", "subskills": []}
        self.assertEqual(RetentionPolicy().schedule(state, today=date(2026, 1, 2)), [])
        summary = progress_summary(state)
        self.assertIn("已完成", summary)
        self.assertNotIn("该复习了", summary)


if __name__ == "__main__":
    unittest.main()
