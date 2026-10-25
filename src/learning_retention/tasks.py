import hashlib
import json
import re
from copy import deepcopy


def _normalize(value):
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip().lower())
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(value[key]) for key in sorted(value)}
    return value


def task_fingerprint(task: dict) -> str:
    payload = {
        "prompt": task.get("prompt", ""),
        "acceptance_criteria": task.get("acceptance_criteria", []),
        "variation": task.get("variation", {}),
    }
    encoded = json.dumps(_normalize(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def unique_held_out_tasks(tasks: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for task in tasks:
        fingerprint = task_fingerprint(task)
        if fingerprint not in seen:
            item = deepcopy(task)
            item["is_held_out"] = True
            item["content_hash"] = fingerprint
            result.append(item)
            seen.add(fingerprint)
    return result
