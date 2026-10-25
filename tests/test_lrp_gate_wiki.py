import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.gate import validate_proposal
from learning_retention.mode import ModePolicy, ModePolicyError
from learning_retention.wiki import WikiLog


class LrpGateAndWikiTests(unittest.TestCase):
    def test_wiki_log_appends_events_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = WikiLog(Path(tmp) / "wiki-log.jsonl")
            log.append({"phase": "cognitive", "learner_output": "first"})
            log.append({"phase": "associative", "learner_output": "second"})
            lines = (Path(tmp) / "wiki-log.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn('"learner_output": "first"', lines[0])

    def test_proposal_is_not_gateable_with_fewer_than_three_tasks(self):
        result = validate_proposal(baseline_score=0.6, candidate_scores=[0.9, 0.9])
        self.assertEqual(result.status, "not_gateable")

    def test_proposal_requires_strict_improvement(self):
        result = validate_proposal(baseline_score=0.8, candidate_scores=[0.8, 0.81, 0.8])
        self.assertEqual(result.status, "rejected")

    def test_upgrade_requires_confirmation_and_three_held_out_tasks(self):
        policy = ModePolicy()
        with self.assertRaises(ModePolicyError):
            policy.upgrade({"learning_mode": "learn", "current_phase": "completed"}, confirmed=False, held_out_tasks=[1, 2, 3], baseline_score=0.7)
        upgraded = policy.upgrade(
            {"learning_mode": "learn", "current_phase": "completed"},
            confirmed=True,
            held_out_tasks=[1, 2, 3],
            baseline_score=0.7,
        )
        self.assertEqual(upgraded["learning_mode"], "learn_retain")
        self.assertEqual(upgraded["current_phase"], "retention")


if __name__ == "__main__":
    unittest.main()
