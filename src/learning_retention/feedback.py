from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreResult:
    raw_score: float
    error_penalty: float
    task_score: float
    mastery_weight: float


class FeedbackOrderError(ValueError):
    pass


class FeedbackPolicy:
    def record_feedback(self, attempt: dict, errors: list[str]) -> dict:
        if not attempt.get("output_received"):
            raise FeedbackOrderError("learner output must precede feedback")
        if len(errors) > 2:
            raise ValueError("at most two key errors may be recorded")
        updated = dict(attempt)
        updated["error_patterns"] = list(errors)
        updated["feedback_recorded"] = True
        return updated


def update_mastery(attempts: list[dict]) -> float | None:
    valid = [item for item in attempts if item.get("valid", item.get("task_score") is not None) and item.get("task_score") is not None]
    if not valid:
        return None
    recent = valid[-3:]
    weights = [0.2, 0.3, 0.5][-len(recent):]
    return sum(item["task_score"] * weight for item, weight in zip(recent, weights)) / sum(weights)


def score_attempt(*, passed_criteria: int, total_criteria: int, critical_error_count: int, completion_mode: str) -> ScoreResult:
    if total_criteria <= 0 or not 0 <= passed_criteria <= total_criteria:
        raise ValueError("criteria counts are invalid")
    if critical_error_count > 2:
        raise ValueError("at most two critical errors may be recorded per feedback turn")
    weights = {"first_unprompted": 1.0, "light_prompt": 0.85, "demonstrated": 0.70, "retry": 0.60}
    if completion_mode not in weights:
        raise ValueError("completion_mode is invalid")
    raw = passed_criteria / total_criteria
    penalty = min(0.20, max(0, critical_error_count) * 0.10)
    return ScoreResult(raw, penalty, max(0.0, min(1.0, raw - penalty)), weights[completion_mode])
