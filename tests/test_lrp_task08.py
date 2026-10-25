import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.retention import (
    RetentionPolicy,
    RetentionPatchError,
    assess_retention,
    next_retention_due,
)


class Task08RetentionTests(unittest.TestCase):
    def test_skill_type_controls_minimum_dose(self):
        policy = RetentionPolicy()
        self.assertEqual(policy.minimum_dose("procedural")["minutes"], 20)
        self.assertEqual(policy.minimum_dose("knowledge")["interval_days"], 28)
        self.assertEqual(policy.minimum_dose("social")["interval_days"], 30)

    def test_only_learn_retain_can_schedule_retention(self):
        policy = RetentionPolicy()
        learn = {"learning_mode": "learn", "current_phase": "completed"}
        self.assertEqual(policy.schedule(learn), [])
        retain = {"learning_mode": "learn_retain", "current_phase": "retention", "retention_due": "2026-01-01"}
        self.assertEqual(len(policy.schedule(retain, today=date(2026, 1, 2))), 1)

    def test_due_date_advances_by_interval_after_success(self):
        self.assertEqual(next_retention_due(date(2026, 1, 1), interval_index=0).isoformat(), "2026-01-02")
        self.assertEqual(next_retention_due(date(2026, 1, 1), interval_index=4).isoformat(), "2026-01-31")

    def test_degradation_patch_requires_user_confirmation(self):
        policy = RetentionPolicy()
        state = {"learning_mode": "learn_retain", "current_phase": "retention", "strategy_version": "1"}
        proposal = policy.propose_patch(state, score=0.5, best_score=0.8)
        self.assertTrue(proposal["repair_triggered"])
        with self.assertRaises(RetentionPatchError):
            policy.apply_patch(state, proposal, confirmed=False, held_out_scores=[0.9, 0.9, 0.9])
        updated = policy.apply_patch(state, proposal, confirmed=True, held_out_scores=[0.9, 0.9, 0.9])
        self.assertEqual(updated["strategy_version"], "2")

    def test_patch_rejected_when_held_out_tasks_do_not_improve(self):
        policy = RetentionPolicy()
        state = {"learning_mode": "learn_retain", "current_phase": "retention", "strategy_version": "1"}
        proposal = policy.propose_patch(state, score=0.5, best_score=0.8)
        with self.assertRaises(RetentionPatchError):
            policy.apply_patch(state, proposal, confirmed=True, held_out_scores=[0.8, 0.8, 0.8], baseline_score=0.8)


if __name__ == "__main__":
    unittest.main()
