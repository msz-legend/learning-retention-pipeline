"""Regression tests for review fixes (state-id boundary, hardening, recovery)."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.gate import ProposalGate
from learning_retention.retention import RetentionPolicy, RetentionPatchError, postpone_due
from learning_retention.state import StateStore, StateValidationError, safe_skill_id
from learning_retention.transition import can_enter_associative


class SafeSkillIdTests(unittest.TestCase):
    def test_ascii_names_keep_original_sanitized_form(self):
        self.assertEqual(safe_skill_id("Python data analysis"), "python-data-analysis")
        self.assertEqual(safe_skill_id("  Git!Basics  "), "git-basics")

    def test_cjk_only_names_produce_unique_stable_ids(self):
        first = safe_skill_id("\u6d4b\u8bd5\u6280\u80fd")
        second = safe_skill_id("\u5b8c\u5168\u4e2d\u6587")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("skill-"))
        self.assertEqual(first, safe_skill_id("\u6d4b\u8bd5\u6280\u80fd"), "id must be deterministic")

    def test_windows_reserved_names_are_prefixed(self):
        self.assertTrue(safe_skill_id("CON").startswith("skill-"))
        self.assertNotEqual(safe_skill_id("CON"), safe_skill_id("prn"))


class StateIdBoundaryTests(unittest.TestCase):
    def test_load_rejects_path_traversal_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            with self.assertRaises(StateValidationError) as raised:
                store.load("..\\..\\evil")
            self.assertEqual(raised.exception.code, "STATE_ID_INVALID")

    def test_load_rejects_absolute_and_slash_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            for bad in ("C:\\.Temp\\x", "C:/Temp/x", "a/../b", "a/b", "", "a b", "UPPER"):
                with self.assertRaises(StateValidationError) as raised:
                    store.load(bad)
                self.assertEqual(raised.exception.code, "STATE_ID_INVALID", bad)

    def test_save_conflicts_cannot_escape_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            tampered = dict(state)
            tampered["state_id"] = "..\\..\\injected"
            with self.assertRaises(StateValidationError) as raised:
                store.save(tampered)
            self.assertEqual(raised.exception.code, "STATE_ID_INVALID")
            skills_root = Path(tmp) / "skills"
            leaked = [p for p in skills_root.iterdir() if p.name != "python-data-analysis"]
            self.assertEqual(leaked, [])

    def test_init_state_guard_against_name_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            store.init_state("Git basics!", {})
            with self.assertRaises(StateValidationError) as raised:
                store.init_state("Git basics?", {})
            self.assertEqual(raised.exception.code, "SKILL_ID_COLLISION")

    def test_same_name_reinit_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            store.init_state("Python data analysis", {})
            again = store.init_state("Python data analysis", {})
            self.assertEqual(again["state_id"], "python-data-analysis")


class ValidationHardeningTests(unittest.TestCase):
    def mangled(self, **overrides):
        base = {
            "state_id": "x", "skill_name": "x", "skill_type": "hybrid", "skill_types": ["hybrid"],
            "learning_mode": "learn", "current_phase": "cognitive",
            "subskills": [{"id": "a", "dependencies": [], "mastery_level": 0.0}],
        }
        base.update(overrides)
        return base

    def test_non_dict_subskills_is_a_field_error_not_typeerror(self):
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(self.mangled(subskills="a,b,c"))
        self.assertIn("subskills", raised.exception.fields)

    def test_string_mastery_level_is_a_field_error_not_typeerror(self):
        state = self.mangled(subskills=[{"id": "a", "dependencies": [], "mastery_level": "very-high"}])
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(state)
        self.assertIn("subskills[0].mastery_level", raised.exception.fields)

    def test_unhashable_learning_mode_is_a_field_error_not_typeerror(self):
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(self.mangled(learning_mode=["learn"]))
        self.assertIn("learning_mode", raised.exception.fields)

    def test_malformed_retention_due_is_a_field_error(self):
        with self.assertRaises(StateValidationError) as raised:
            StateStore.validate(self.mangled(current_phase="retention", learning_mode="learn_retain", subskills=[], retention_due="not-a-date"))
        self.assertIn("retention_due", raised.exception.fields)

    def test_iso_datetime_retention_due_is_accepted(self):
        state = self.mangled(current_phase="retention", learning_mode="learn_retain", subskills=[], retention_due="2026-01-01T08:00:00")
        StateStore.validate(state)


class RecoverySelfHealTests(unittest.TestCase):
    def test_recovery_rewrites_primary_and_records_event_once(self):
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

            repaired = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(repaired["last_session_summary"], "checkpoint")

            store.load(state["state_id"])
            again = store.load(state["state_id"])
            self.assertEqual(again["last_session_summary"], "checkpoint")
            self.assertEqual(len(store.recovery_events_path(state["state_id"]).read_text(encoding="utf-8").splitlines()), 1)


class RetentionHardeningTests(unittest.TestCase):
    def test_apply_patch_with_none_baseline_does_not_crash(self):
        policy = RetentionPolicy()
        state = {"learning_mode": "learn_retain", "current_phase": "retention", "strategy_version": "1", "best_retention_score": None}
        proposal = policy.propose_patch(state, score=0.5, best_score=0.8)
        updated = policy.apply_patch(state, proposal, confirmed=True, held_out_scores=[0.9, 0.9, 0.9])
        self.assertEqual(updated["strategy_version"], "2")

    def test_schedule_ignores_malformed_due(self):
        policy = RetentionPolicy()
        memes = dict(learning_mode="learn_retain", current_phase="retention", retention_due="rubbish")
        self.assertEqual(policy.schedule(memes, today=date(2026, 1, 2)), [])

    def test_postpone_due_reports_invalid_due(self):
        with self.assertRaises(RetentionPatchError):
            postpone_due({"retention_due": "rubbish"})


class GateDryTests(unittest.TestCase):
    def test_decide_matches_shared_threshold_function(self):
        gate = ProposalGate()
        proposal = gate.create({"strategy_version": "3", "strategy": {"a": 1}}, candidate_strategy={"a": 2})
        accepted = gate.decide(proposal, baseline_score=0.8, candidate_scores=[0.82, 0.83, 0.84])
        self.assertEqual((accepted["status"], accepted["new_strategy_version"]), ("accepted", "4"))
        rejected = gate.decide(proposal, baseline_score=0.9, candidate_scores=[0.85, 0.85, 0.85])
        self.assertEqual(rejected["status"], "rejected")
        not_gateable = gate.decide(proposal, baseline_score=0.8, candidate_scores=[0.99])
        self.assertEqual(not_gateable["status"], "not_gateable")


class TransitionGuardTests(unittest.TestCase):
    def test_empty_subskills_cannot_enter_associative(self):
        self.assertFalse(can_enter_associative({"subskills": []}))


if __name__ == "__main__":
    unittest.main()
