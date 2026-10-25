import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from learning_retention.gate import ProposalGate
from learning_retention.wiki import WikiLog


class Task09GateWikiTests(unittest.TestCase):
    def test_proposal_keeps_full_snapshot_and_rejected_status(self):
        gate = ProposalGate()
        state = {"strategy_version": "3", "strategy": {"intervals": [1, 3, 7]}}
        proposal = gate.create(state, candidate_strategy={"intervals": [1, 2, 5]})
        rejected = gate.decide(proposal, baseline_score=0.8, candidate_scores=[0.8, 0.8, 0.8])
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["base_strategy_version"], "3")
        self.assertEqual(rejected["base_strategy"], state["strategy"])

    def test_accepted_proposal_increments_strategy_version(self):
        gate = ProposalGate()
        state = {"strategy_version": "3", "strategy": {"intervals": [1, 3, 7]}}
        proposal = gate.create(state, candidate_strategy={"intervals": [1, 2, 5]})
        accepted = gate.decide(proposal, baseline_score=0.8, candidate_scores=[0.82, 0.83, 0.84])
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["new_strategy_version"], "4")

    def test_wiki_log_records_gate_decision_without_rewriting_old_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wiki.jsonl"
            log = WikiLog(path)
            log.append({"event": "practice", "phase": "retention"})
            log.append({"event": "proposal_rejected", "proposal_id": "p1"})
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["event"] for row in rows], ["practice", "proposal_rejected"])


if __name__ == "__main__":
    unittest.main()
