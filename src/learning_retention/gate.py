from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid4


class ProposalGate:
    def create(self, state: dict, *, candidate_strategy: dict) -> dict:
        return {
            "proposal_id": f"proposal-{uuid4().hex[:8]}",
            "base_strategy_version": state.get("strategy_version", "1"),
            "base_strategy": deepcopy(state.get("strategy", {})),
            "candidate_strategy": deepcopy(candidate_strategy),
            "status": "proposed",
        }

    def decide(self, proposal: dict, *, baseline_score: float, candidate_scores: list[float]) -> dict:
        decided = deepcopy(proposal)
        result = validate_proposal(baseline_score=baseline_score, candidate_scores=candidate_scores)
        decided["status"] = result.status
        if result.status in {"accepted", "rejected"}:
            decided["baseline_score"] = result.baseline_score
            decided["candidate_score"] = result.candidate_score
        if result.status == "accepted":
            decided["new_strategy_version"] = str(int(proposal["base_strategy_version"]) + 1)
        return decided


@dataclass(frozen=True)
class GateResult:
    status: str
    baseline_score: float
    candidate_score: float | None
    reason: str


def validate_proposal(*, baseline_score: float, candidate_scores: list[float]) -> GateResult:
    if len(candidate_scores) < 3:
        return GateResult("not_gateable", baseline_score, None, "at least three held-out tasks are required")
    candidate = sum(candidate_scores) / len(candidate_scores)
    if candidate >= baseline_score + 0.01:
        return GateResult("accepted", baseline_score, candidate, "strict improvement")
    return GateResult("rejected", baseline_score, candidate, "candidate did not exceed baseline by 0.01")
