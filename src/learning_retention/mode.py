from copy import deepcopy


class ModePolicyError(ValueError):
    pass


class ModePolicy:
    def select_mode(self, mode: str, *, confirmed: bool) -> str:
        if mode not in {"learn", "learn_retain"} or not confirmed:
            raise ModePolicyError("explicit learn or learn_retain confirmation is required")
        return mode

    def apply_selection(self, state: dict, mode: str, *, confirmed: bool) -> dict:
        selected = self.select_mode(mode, confirmed=confirmed)
        updated = deepcopy(state)
        updated["learning_mode"] = selected
        updated.setdefault("current_phase", "decompose")
        return updated

    def complete_autonomous(self, state: dict, *, real_task_passed: bool, output_ref: str | None = None) -> dict:
        if not real_task_passed:
            raise ModePolicyError("real task must pass before completion")
        updated = deepcopy(state)
        if output_ref:
            updated["completion_evidence"] = output_ref
        if updated.get("learning_mode") == "learn":
            updated["current_phase"] = "completed"
            updated.pop("retention_due", None)
            updated["scheduler_state"] = {"queue": [], "interval_index": 0, "postponements": 0}
            return updated
        if updated.get("learning_mode") == "learn_retain":
            if len(updated.get("held_out_tasks", [])) < 3 or updated.get("baseline_retention_score") is None:
                raise ModePolicyError("retention baseline is not established")
            updated["current_phase"] = "retention"
            return updated
        raise ModePolicyError("learning mode must be explicitly selected")

    def upgrade(self, state: dict, *, confirmed: bool, held_out_tasks: list, baseline_score: float) -> dict:
        if state.get("learning_mode") != "learn" or state.get("current_phase") != "completed":
            raise ModePolicyError("only completed learn states can be upgraded")
        if not confirmed:
            raise ModePolicyError("explicit confirmation required")
        if len(held_out_tasks) < 3 or baseline_score is None:
            raise ModePolicyError("three held-out tasks and a baseline are required")
        updated = deepcopy(state)
        updated["learning_mode"] = "learn_retain"
        updated["current_phase"] = "retention"
        updated["held_out_tasks"] = deepcopy(held_out_tasks)
        updated["baseline_retention_score"] = baseline_score
        updated["best_retention_score"] = baseline_score
        updated["upgrade_history"] = updated.get("upgrade_history", []) + [{"action": "upgrade", "confirmed": True}]
        return updated

    def downgrade(self, state: dict, *, confirmed: bool) -> dict:
        if state.get("learning_mode") != "learn_retain":
            raise ModePolicyError("only learn_retain can be downgraded")
        if not confirmed:
            raise ModePolicyError("explicit confirmation required")
        updated = deepcopy(state)
        updated["learning_mode"] = "learn"
        updated["current_phase"] = "completed"
        updated.pop("retention_due", None)
        updated.setdefault("upgrade_history", []).append({"action": "downgrade", "confirmed": True})
        return updated

