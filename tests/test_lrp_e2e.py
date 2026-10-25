import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class LrpEndToEndTests(unittest.TestCase):
    def test_learn_path_reaches_completed_without_retention(self):
        sys.path.insert(0, str(ROOT / "src"))
        from learning_retention.mode import ModePolicy
        state = {"learning_mode": "learn", "current_phase": "autonomous", "retention_due": None}
        state = ModePolicy().complete_autonomous(state, real_task_passed=True)
        self.assertEqual((state["current_phase"], state["learning_mode"]), ("completed", "learn"))
        self.assertNotIn("retention_due", state)
        self.assertEqual(state.get("scheduler_state", {}).get("queue", []), [])

    def test_learn_retain_path_reaches_retention_with_baseline(self):
        sys.path.insert(0, str(ROOT / "src"))
        from learning_retention.mode import ModePolicy
        state = {
            "learning_mode": "learn_retain",
            "current_phase": "autonomous",
            "held_out_tasks": [{"id": "h1"}, {"id": "h2"}, {"id": "h3"}],
            "baseline_retention_score": 0.7,
        }
        updated = ModePolicy().complete_autonomous(state, real_task_passed=True)
        self.assertEqual(updated["current_phase"], "retention")

    def test_validate_state_cli_returns_machine_readable_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({"state_id": "x", "skill_name": "x", "skill_type": "hybrid", "learning_mode": "", "current_phase": "decompose", "subskills": []}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate-state.py"), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["ok"], True)


if __name__ == "__main__":
    unittest.main()
