"""Regression tests for review fixes (state-id boundary, hardening, recovery)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.gate import ProposalGate
from learning_retention.retention import RetentionPolicy, RetentionPatchError, postpone_due
import learning_retention.state as lr_state
from learning_retention.state import StateLockTimeout, StateStore, StateValidationError, _lock_fd, _unlock_fd, safe_skill_id
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


class LockingTests(unittest.TestCase):
    def test_save_times_out_without_deadlock_when_lock_is_held_manually(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            with open(store.lock_path(state["state_id"]), "a+") as held:
                _lock_fd(held)
                try:
                    with self.assertRaises(StateLockTimeout) as raised:
                        store.save(state, timeout=0.25)
                    self.assertEqual(raised.exception.code, "STATE_LOCK_TIMEOUT")
                    self.assertEqual(raised.exception.timeout, 0.25)
                finally:
                    _unlock_fd(held)
            store.save(state)
            self.assertEqual(store.load(state["state_id"])["state_id"], state["state_id"])

    def test_init_state_times_out_and_this_state_file_is_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            path = store.state_path(state["state_id"])
            before = path.read_text(encoding="utf-8")
            with open(store.lock_path(state["state_id"]), "a+") as held:
                _lock_fd(held)
                try:
                    with self.assertRaises(StateLockTimeout):
                        store.init_state("Python data analysis", {}, timeout=0.25)
                finally:
                    _unlock_fd(held)
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_rescue_of_corrupt_primary_survives_concurrent_holder(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            state["last_session_summary"] = "checkpoint"
            store.save(state)
            state["last_session_summary"] = "latest"
            store.save(state)
            path = store.state_path(state["state_id"])
            path.write_text("{broken", encoding="utf-8")
            with open(store.lock_path(state["state_id"]), "a+") as held:
                _lock_fd(held)
                try:
                    recovered = store.load(state["state_id"])
                finally:
                    _unlock_fd(held)
            self.assertEqual(recovered["last_session_summary"], "checkpoint")

    def test_concurrent_process_saves_end_with_valid_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(__file__).parents[1] / "src"
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            mid = state["state_id"]
            worker = Path(tmp) / "worker.py"
            worker.write_text(
                "\n".join([
                    "import sys",
                    "sys.path.insert(0, sys.argv[1])",
                    "from learning_retention.state import StateStore",
                    "store = StateStore()",
                    "for i in range(12):",
                    "    current = store.load(sys.argv[2])",
                    "    current['last_session_summary'] = f'{sys.argv[3]}-{i}'",
                    "    store.save(current, timeout=10)",
                ]),
                encoding="utf-8",
            )
            procs = [
                subprocess.Popen(
                    [sys.executable, str(worker), str(src), mid, f"worker{n}"],
                    env={**os.environ, "LRP_DATA_DIR": str(Path(tmp))},
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for n in range(4)
            ]
            for proc in procs:
                _, stderr = proc.communicate(timeout=90)
                self.assertEqual(proc.returncode, 0, stderr.decode("utf-8", "replace"))
            final = store.load(mid)
            self.assertIsInstance(final, dict)
            self.assertTrue((Path(tmp) / "skills" / mid / "progress-state.json").exists())
            self.assertFalse(store.recovery_events_path(mid).exists())


class WikiLogPathTests(unittest.TestCase):
    def legacy(self, wiki_value, data_dir="C:\\Users\\Ad\\data\\learning-retention-pipeline", mid="py"):
        return {
            "wiki_log_path": wiki_value,
            "data_dir": data_dir,
            "state_id": mid,
        }

    def test_relative_forms_of_all_three_os_storage_shapes_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            posix_rel = {"state_id": "py", "wiki_log_path": "wiki-log.jsonl"}
            self.assertEqual(store.wiki_log_path(posix_rel), Path(tmp) / "skills" / "py" / "wiki-log.jsonl")
            nested = {"state_id": "py", "wiki_log_path": "logs/wiki-log.jsonl"}
            self.assertEqual(store.wiki_log_path(nested), Path(tmp) / "skills" / "py" / "logs" / "wiki-log.jsonl")
            windows_rel = {"state_id": "py", "wiki_log_path": "logs\\wiki-log.jsonl"}
            self.assertEqual(store.wiki_log_path(windows_rel), Path(tmp) / "skills" / "py" / "logs" / "wiki-log.jsonl")
            empty = {"state_id": "py", "wiki_log_path": ""}
            self.assertEqual(store.wiki_log_path(empty), Path(tmp) / "skills" / "py" / "wiki-log.jsonl")

    def test_absolute_wiki_log_path_resolves_as_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            absolute = {"state_id": "py", "wiki_log_path": "C:\\logs\\wiki.jsonl"}
            result = store.wiki_log_path(absolute)
            self.assertFalse(result.is_relative_to(Path(tmp)))
            self.assertEqual(str(result), str(Path("C:\\logs\\wiki.jsonl")) if os.name == "nt" else result)
            self.assertEqual(str(result).replace("/", "\\"), "C:\\logs\\wiki.jsonl")

    def test_migrate_relativizes_legacy_absolute_paths_per_os(self):
        windows_state = self.legacy(
            "C:\\Users\\Ad\\data\\learning-retention-pipeline\\skills\\py\\wiki-log.jsonl",
            data_dir="C:\\Users\\Ad\\data\\learning-retention-pipeline",
        )
        self.assertEqual(StateStore.migrate(windows_state)["wiki_log_path"], "wiki-log.jsonl")
        posix_state = self.legacy(
            "/home/ad/.local/share/learning-retention-pipeline/skills/py/wiki-log.jsonl",
            data_dir="/home/ad/.local/share/learning-retention-pipeline",
        )
        self.assertEqual(StateStore.migrate(posix_state)["wiki_log_path"], "wiki-log.jsonl")
        rel_backslash = self.legacy("logs\\wiki-log.jsonl")
        self.assertEqual(StateStore.migrate(rel_backslash)["wiki_log_path"], "logs/wiki-log.jsonl")
        unchanged = self.legacy("wiki-log.jsonl")
        self.assertEqual(StateStore.migrate(unchanged)["wiki_log_path"], "wiki-log.jsonl")

    def test_migrate_keeps_unrelativizable_values_without_crash(self):
        foreign = self.legacy("D:\\Other\\wiki-log.jsonl")
        self.assertEqual(StateStore.migrate(foreign)["wiki_log_path"], "D:\\Other\\wiki-log.jsonl")
        unanchored = self.legacy("/somewhere/else/wiki-log.jsonl", data_dir="")
        self.assertEqual(StateStore.migrate(unanchored)["wiki_log_path"], "/somewhere/else/wiki-log.jsonl")
        blank = self.legacy("")
        self.assertEqual(StateStore.migrate(blank)["wiki_log_path"], "")

    def test_load_repairs_legacy_wiki_path_and_template_validation_stays_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            legacy = dict(state)
            legacy["wiki_log_path"] = str(Path(tmp) / "skills" / state["state_id"] / "wiki-log.jsonl")
            path = store.state_path(state["state_id"])
            path.write_text(json.dumps(legacy), encoding="utf-8")
            resumed = store.load(state["state_id"])
            self.assertEqual(resumed["wiki_log_path"], "wiki-log.jsonl")


class TransientReadFailureTests(unittest.TestCase):
    """Root-cause regression: a transient Windows share lock on the primary
    must never be treated as corruption (no recovery event, no backup rollback)."""

    def test_brief_permission_error_is_tolerated_without_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            state["last_session_summary"] = "fresh"
            store.save(state)
            calls = {"n": 0}
            primary = store.state_path(state["state_id"])
            real_read = Path.read_text

            def flaky_read(path_self, *args, **kwargs):
                if path_self == primary and calls["n"] < 2:
                    calls["n"] += 1
                    raise PermissionError(13, "transient share lock")
                return real_read(path_self, *args, **kwargs)

            # Patch one level below the helper so the product retry loop itself
            # runs; only reads of the primary file are intercepted.
            with mock.patch.object(Path, "read_text", flaky_read):
                resumed = store.load(state["state_id"])
            self.assertEqual(calls["n"], 2)
            self.assertEqual(resumed["last_session_summary"], "fresh")
            self.assertFalse(store.recovery_events_path(state["state_id"]).exists())

    def test_persistent_permission_error_rolls_back_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            state["last_session_summary"] = "latest"
            store.save(state)
            path = store.state_path(state["state_id"])
            before = path.read_text(encoding="utf-8")
            real_read = Path.read_text

            def locked_read(path_self, *args, **kwargs):
                if path_self == path:
                    raise PermissionError(13, "held share lock")
                return real_read(path_self, *args, **kwargs)

            with mock.patch.object(Path, "read_text", locked_read):
                with self.assertRaises(PermissionError):
                    store.load(state["state_id"])
            self.assertEqual(path.read_text(encoding="utf-8"), before)
            self.assertFalse(store.recovery_events_path(state["state_id"]).exists())

    @unittest.skipUnless(os.name == "nt", "Windows region lock semantics")
    def test_windows_region_lock_on_primary_briefly_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp))
            state = store.init_state("Python data analysis", {})
            state["last_session_summary"] = "held only briefly"
            store.save(state)
            primary = store.state_path(state["state_id"])
            import msvcrt

            def release():
                holder.seek(0)
                msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, 1)

            holder = open(primary, "a+")
            releaser = threading.Timer(0.3, release)
            try:
                holder.seek(0)
                msvcrt.locking(holder.fileno(), msvcrt.LK_NBLCK, 1)  # blocks foreign readers of byte 0
                holder.seek(0)
                releaser.start()
                resumed = store.load(state["state_id"])
            finally:
                releaser.join(timeout=2)
                try:
                    release()
                except OSError:
                    pass
                holder.close()
            self.assertEqual(resumed["last_session_summary"], "held only briefly")
            self.assertFalse(store.recovery_events_path(state["state_id"]).exists())


if __name__ == "__main__":
    unittest.main()
