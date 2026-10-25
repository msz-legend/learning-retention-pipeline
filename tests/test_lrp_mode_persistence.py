import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.mode import ModePolicy, ModePolicyError


class ModePersistenceTests(unittest.TestCase):
    def test_confirmed_mode_selection_updates_state_and_keeps_decompose_phase(self):
        state = {"learning_mode": "", "current_phase": "decompose"}
        updated = ModePolicy().apply_selection(state, "learn_retain", confirmed=True)
        self.assertEqual(updated["learning_mode"], "learn_retain")
        self.assertEqual(updated["current_phase"], "decompose")

    def test_unconfirmed_mode_selection_does_not_mutate_state(self):
        state = {"learning_mode": "", "current_phase": "decompose"}
        with self.assertRaises(ModePolicyError):
            ModePolicy().apply_selection(state, "learn", confirmed=False)
        self.assertEqual(state["learning_mode"], "")


if __name__ == "__main__":
    unittest.main()
