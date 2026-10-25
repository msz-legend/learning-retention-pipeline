import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.state import StateStore, StateValidationError


class Task10ValidatorTests(unittest.TestCase):
    def test_invalid_dependency_reference_is_reported(self):
        state = {
            "state_id": "x", "skill_name": "x", "skill_type": "hybrid", "skill_types": ["hybrid"],
            "learning_mode": "learn", "current_phase": "cognitive",
            "subskills": [{"id": "a", "dependencies": ["missing"], "mastery_level": 0.0}],
        }
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(state)
        self.assertIn("subskills[0].dependencies", raised.exception.fields)

    def test_mastery_level_outside_range_is_rejected(self):
        state = {
            "state_id": "x", "skill_name": "x", "skill_type": "hybrid", "skill_types": ["hybrid"],
            "learning_mode": "learn", "current_phase": "cognitive",
            "subskills": [{"id": "a", "dependencies": [], "mastery_level": 1.2}],
        }
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(state)
        self.assertIn("subskills[0].mastery_level", raised.exception.fields)

    def test_completed_state_must_not_have_retention_schedule(self):
        state = {
            "state_id": "x", "skill_name": "x", "skill_type": "hybrid", "skill_types": ["hybrid"],
            "learning_mode": "learn", "current_phase": "completed", "retention_due": "2026-01-01",
            "subskills": [],
        }
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(state)
        self.assertIn("retention_due", raised.exception.fields)

    def test_retention_state_requires_retain_mode(self):
        state = {
            "state_id": "x", "skill_name": "x", "skill_type": "hybrid", "skill_types": ["hybrid"],
            "learning_mode": "learn", "current_phase": "retention", "subskills": [],
        }
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(state)
        self.assertIn("learning_mode", raised.exception.fields)

    def test_invalid_iso_date_is_rejected(self):
        state = {
            "state_id": "x", "skill_name": "x", "skill_type": "hybrid", "skill_types": ["hybrid"],
            "learning_mode": "learn", "current_phase": "decompose", "completed_at": "not-a-date",
            "subskills": [],
        }
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(state)
        self.assertIn("completed_at", raised.exception.fields)


if __name__ == "__main__":
    unittest.main()
