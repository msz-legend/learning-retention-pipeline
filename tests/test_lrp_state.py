import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.state import StateStore, StateValidationError


class StateStoreContractTests(unittest.TestCase):
    def test_init_state_creates_a_valid_learn_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state(
                skill_name="Python data analysis",
                skill_context={"goal": "complete a real analysis"},
            )

            self.assertEqual(state["learning_mode"], "")
            self.assertEqual(state["current_phase"], "decompose")
            self.assertEqual(state["skill_type"], "hybrid")
            self.assertEqual(state["skill_types"], ["hybrid"])
            self.assertTrue((Path(tmp) / "skills" / "python-data-analysis" / "progress-state.json").exists())

    def test_invalid_state_is_rejected_without_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            state["current_phase"] = "not-a-phase"
            path = store.state_path(state["state_id"])
            path.write_text(json.dumps(state), encoding="utf-8")

            with self.assertRaises(StateValidationError) as raised:
                store.load(state["state_id"])

            self.assertEqual(raised.exception.code, "STATE_INVALID")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["current_phase"], "not-a-phase")

    def test_save_is_atomic_and_loads_backup_when_primary_is_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            state["last_session_summary"] = "checkpoint"
            store.save(state)
            state["last_session_summary"] = "latest"
            store.save(state)
            path = store.state_path(state["state_id"])
            path.write_text("{broken", encoding="utf-8")

            recovered = store.load(state["state_id"])

            self.assertEqual(recovered["last_session_summary"], "checkpoint")
            self.assertTrue(store.recovery_events_path(state["state_id"]).exists())


if __name__ == "__main__":
    unittest.main()
