import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.mode import ModePolicy, ModePolicyError
from learning_retention.transition import PhaseTransitionError, can_enter_cognitive, can_enter_associative, can_enter_autonomous
from learning_retention.validation import validate_decomposition


class Task04ContractTests(unittest.TestCase):
    def test_decomposition_requires_user_confirmation_before_cognitive(self):
        state = {
            "learning_mode": "learn",
            "decomposition_confirmed": False,
            "subskills": [
                {"id": "a", "dependencies": [], "acceptance_criteria": ["criterion"]},
                {"id": "b", "dependencies": ["a"], "acceptance_criteria": ["criterion"]},
                {"id": "c", "dependencies": [], "acceptance_criteria": ["criterion"]},
            ],
        }
        self.assertFalse(can_enter_cognitive(state))
        state["decomposition_confirmed"] = True
        self.assertTrue(can_enter_cognitive(state))

    def test_cognitive_exit_requires_all_dependency_free_skills_at_point_six(self):
        state = {
            "subskills": [
                {"id": "a", "dependencies": [], "mastery_level": 0.6},
                {"id": "b", "dependencies": ["a"], "mastery_level": 0.0},
                {"id": "c", "dependencies": [], "mastery_level": 0.59},
            ]
        }
        self.assertFalse(can_enter_associative(state))
        state["subskills"][2]["mastery_level"] = 0.6
        self.assertTrue(can_enter_associative(state))

    def test_autonomous_exit_requires_mastery_and_variation(self):
        state = {"subskills": [
            {"mastery_level": 0.8}, {"mastery_level": 0.9}
        ], "variation_test_passed": False}
        self.assertFalse(can_enter_autonomous(state))
        state["variation_test_passed"] = True
        self.assertTrue(can_enter_autonomous(state))

    def test_mode_selection_rejects_empty_mode_and_accepts_explicit_mode(self):
        policy = ModePolicy()
        with self.assertRaises(ModePolicyError):
            policy.select_mode("", confirmed=True)
        self.assertEqual(policy.select_mode("learn", confirmed=True), "learn")
        self.assertEqual(policy.select_mode("learn_retain", confirmed=True), "learn_retain")

    def test_decomposition_requires_three_to_five_valid_subskills(self):
        result = validate_decomposition([
            {"id": "a", "dependencies": [], "acceptance_criteria": ["x"]},
            {"id": "b", "dependencies": [], "acceptance_criteria": ["y"]},
        ])
        self.assertFalse(result.valid)
        self.assertIn("subskill_count", result.errors)


if __name__ == "__main__":
    unittest.main()
