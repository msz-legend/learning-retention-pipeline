from datetime import date, timedelta


class DependencyScheduler:
    def next_tasks(self, state: dict) -> list[dict]:
        available = []
        def mastered(skill_id: str, seen: set[str] | None = None) -> bool:
            seen = seen or set()
            if skill_id in seen:
                return False
            seen.add(skill_id)
            item = next((candidate for candidate in state.get("subskills", []) if candidate["id"] == skill_id), None)
            if item is None or item.get("mastery_level", 0.0) < 0.6:
                return False
            return all(mastered(dep, seen.copy()) for dep in item.get("dependencies", []))

        for item in state.get("subskills", []):
            if all(mastered(dep) for dep in item.get("dependencies", [])):
                available.append({"subskill_id": item["id"], "task_type": "retrieval", "dependency_gate": True})
        return available


class SimpleIntervalScheduler:
    INTERVALS = (1, 3, 7, 14, 30)

    def __init__(self, *, today: date | None = None):
        self.today = today or date.today()

    def next_tasks(self, state: dict) -> list[dict]:
        items = state.get("subskills", [])
        if not items:
            return []
        result = [{"subskill_id": items[0]["id"], "task_type": "retrieval", "spacing_days": self.INTERVALS[0]}]
        if len(items) > 1:
            result.append({"subskill_id": items[1]["id"], "task_type": "interleaved", "spacing_days": self.INTERVALS[0]})
        result.append({"subskill_id": items[0]["id"], "task_type": "variation", "spacing_days": self.INTERVALS[0]})
        return result

    def due_date(self, interval_index: int = 0) -> date:
        index = max(0, min(interval_index, len(self.INTERVALS) - 1))
        return self.today + timedelta(days=self.INTERVALS[index])
