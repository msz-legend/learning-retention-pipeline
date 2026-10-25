from copy import deepcopy
from datetime import date, timedelta
from dataclasses import dataclass


class RetentionPatchError(ValueError):
    pass


class RetentionPolicy:
    DOSES = {
        "procedural": {"minutes": 20, "interval_days": 7},
        "knowledge": {"minutes": 10, "interval_days": 28},
        "social": {"minutes": 10, "interval_days": 30},
        "hybrid": {"minutes": 20, "interval_days": 14},
    }

    def minimum_dose(self, skill_type: str) -> dict:
        if skill_type not in self.DOSES:
            raise ValueError("unknown skill type")
        return dict(self.DOSES[skill_type])

    def schedule(self, state: dict, *, today: date | None = None) -> list[dict]:
        if state.get("learning_mode") != "learn_retain" or state.get("current_phase") != "retention":
            return []
        due = state.get("retention_due")
        if due is None or not isinstance(due, str):
            return []
        try:
            due_date = date.fromisoformat(due)
        except ValueError:
            return []
        if (today or date.today()) < due_date:
            return []
        return [{"task_type": "retention", "due": due}]

    def propose_patch(self, state: dict, *, score: float, best_score: float) -> dict:
        assessment = assess_retention(score=score, best_score=best_score)
        return {"repair_triggered": assessment.repair_triggered, "reason": assessment.reason, "candidate_strategy": {"interval_index_delta": -1}}

    def apply_patch(self, state: dict, proposal: dict, *, confirmed: bool, held_out_scores: list[float], baseline_score: float | None = None) -> dict:
        if not proposal.get("repair_triggered"):
            raise RetentionPatchError("no repair is required")
        if not confirmed:
            raise RetentionPatchError("explicit confirmation required")
        baseline = baseline_score if baseline_score is not None else state.get("best_retention_score")
        # init_state leaves best_retention_score as None; a missing/None or
        # non-numeric baseline must not crash the gate, it simply holds 0.0.
        if not isinstance(baseline, (int, float)) or isinstance(baseline, bool):
            baseline = 0.0
        if len(held_out_scores) < 3:
            raise RetentionPatchError("at least three held-out scores are required")
        candidate = sum(held_out_scores) / len(held_out_scores)
        if candidate < baseline + 0.01:
            raise RetentionPatchError("patch failed held-out gate")
        updated = deepcopy(state)
        updated["strategy_version"] = str(int(updated.get("strategy_version", "1")) + 1)
        updated["last_patch"] = proposal
        return updated


@dataclass(frozen=True)
class RetentionAssessment:
    repair_triggered: bool
    reason: str


def assess_retention(*, score: float, best_score: float | None) -> RetentionAssessment:
    if best_score is None:
        return RetentionAssessment(False, "baseline")
    triggered = score < best_score * 0.85 and score < 0.6
    return RetentionAssessment(triggered, "degradation" if triggered else "stable")


def next_retention_due(start: date, *, interval_index: int = 0) -> date:
    intervals = (1, 3, 7, 14, 30)
    index = max(0, min(interval_index, len(intervals) - 1))
    return start + timedelta(days=intervals[index])


def postpone_due(state: dict, *, days: int = 1) -> dict:
    updated = deepcopy(state)
    try:
        due = date.fromisoformat(updated["retention_due"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RetentionPatchError("retention_due is missing or invalid") from exc
    updated["retention_due"] = (due + timedelta(days=days)).isoformat()
    scheduler = updated.setdefault("scheduler_state", {})
    scheduler["postponements"] = scheduler.get("postponements", 0) + 1
    return updated
