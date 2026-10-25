"""State persistence, validation, and recovery for LRP."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PHASES = {"decompose", "cognitive", "associative", "autonomous", "retention", "completed"}
MODES = {"", "learn", "learn_retain"}
SKILL_TYPES = {"procedural", "knowledge", "social", "hybrid"}
_SAFE_ID = re.compile(r"[^a-z0-9]+")
_STATE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *{f"com{i}" for i in range(1, 10)}, *{f"lpt{i}" for i in range(1, 10)}}


class StateValidationError(ValueError):
    def __init__(self, message: str, code: str = "STATE_INVALID", fields: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.fields = fields or []


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_data_dir() -> Path:
    if os.name == "nt":
        platform_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if platform_data:
            return Path(platform_data) / "learning-retention-pipeline"
    return Path.home() / ".local" / "share" / "learning-retention-pipeline"


def safe_skill_id(skill_name: str) -> str:
    value = _SAFE_ID.sub("-", skill_name.strip().lower()).strip("-")
    if value:
        return f"skill-{value}" if value in _WINDOWS_RESERVED else value
    digest = hashlib.sha256(skill_name.strip().casefold().encode("utf-8")).hexdigest()[:10]
    return f"skill-{digest}"


def validate_state_id(state_id: object) -> str:
    """Validate a state id at the persistence boundary.

    Accepts exactly what ``safe_skill_id`` emits (lowercase letters, digits,
    dashes) and rejects path-traversal or drive-absolute forms such as
    ``../x``, ``a:b``, empty/blank segments, backslashes, and Windows
    reserved device names. Raise ``StateValidationError`` (code
    ``STATE_ID_INVALID``) otherwise.
    """
    if (
        not isinstance(state_id, str)
        or not _STATE_ID.fullmatch(state_id)
        or state_id in _WINDOWS_RESERVED
    ):
        raise StateValidationError(
            "Invalid state id; expected lowercase letters, digits, and dashes without path separators",
            code="STATE_ID_INVALID",
        )
    return state_id


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    for parse in (date.fromisoformat, datetime.fromisoformat):
        try:
            parse(value)
            return True
        except ValueError:
            continue
    return False


class StateStore:
    def __init__(self, data_dir: Path | str | None = None):
        configured = data_dir or os.environ.get("LRP_DATA_DIR")
        self.data_dir = Path(configured).expanduser() if configured else _default_data_dir()

    def skill_dir(self, state_or_id: dict[str, Any] | str) -> Path:
        # Persistence boundary: every state-derived path element must pass
        # validate_state_id, which confines the directory tree to data_dir/skills.
        if isinstance(state_or_id, dict):
            return self.skill_dir(state_or_id["state_id"])
        return self.data_dir / "skills" / validate_state_id(state_or_id)

    def state_path(self, state_id: str) -> Path:
        return self.skill_dir(state_id) / "progress-state.json"

    def backup_path(self, state_id: str) -> Path:
        return self.skill_dir(state_id) / "progress-state.json.bak"

    def recovery_events_path(self, state_id: str) -> Path:
        return self.skill_dir(state_id) / "recovery-events.jsonl"

    def init_state(self, skill_name: str, skill_context: dict[str, Any]) -> dict[str, Any]:
        state_id = safe_skill_id(skill_name)
        if self.state_path(state_id).exists():
            existing_name = self._existing_skill_name(state_id)
            if existing_name is not None and existing_name != skill_name:
                raise StateValidationError(
                    f"state id '{state_id}' already exists for skill '{existing_name}'",
                    code="SKILL_ID_COLLISION",
                    fields=["state_id"],
                )
        now = _now()
        state: dict[str, Any] = {
            "schema_version": "0.1.0",
            "state_id": state_id,
            "skill_name": skill_name,
            "skill_type": "hybrid",
            "skill_types": ["hybrid"],
            "learning_mode": "",
            "current_phase": "decompose",
            "subskills": [],
            "baseline_retention_score": None,
            "best_retention_score": None,
            "held_out_tasks": [],
            "wiki_log_path": str(self.skill_dir(state_id) / "wiki-log.jsonl"),
            "completed_at": None,
            "upgrade_history": [],
            "created_at": now,
            "updated_at": now,
            "data_dir": str(self.data_dir),
            "skill_context": copy.deepcopy(skill_context),
            "time_budget": {"sessions_per_week": None, "minutes_per_session": None},
            "output_preference": None,
            "active_task": None,
            "paused_at": None,
            "pause_reason": None,
            "last_session_summary": None,
            "scheduler_state": {"queue": [], "interval_index": 0, "postponements": 0},
            "strategy_version": "1",
            "privacy_policy": "summary",
            "privacy_policy_history": [],
        }
        self.validate(state)
        self.save(state)
        return state

    def _existing_skill_name(self, state_id: str) -> str | None:
        try:
            existing = json.loads(self.state_path(state_id).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(existing, dict):
            name = existing.get("skill_name")
            return name if isinstance(name, str) else None
        return None

    def load(self, state_id: str) -> dict[str, Any]:
        path = self.state_path(state_id)
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            state = self.migrate(state)
            self.validate(state)
            return state
        except (OSError, json.JSONDecodeError, StateValidationError) as primary_error:
            if isinstance(primary_error, StateValidationError) and primary_error.code == "STATE_INVALID":
                raise
            backup = self.backup_path(state_id)
            try:
                recovered = json.loads(backup.read_text(encoding="utf-8"))
                recovered = self.migrate(recovered)
                self.validate(recovered)
            except (OSError, json.JSONDecodeError, StateValidationError) as backup_error:
                fields = getattr(primary_error, "fields", [])
                raise StateValidationError(
                    f"State is unreadable; primary={primary_error}; backup={backup_error}",
                    code="STATE_DIAGNOSTIC_ONLY",
                    fields=fields,
                ) from primary_error
            self._append_recovery_event(state_id, primary_error)
            self._repair_primary(recovered)
            return recovered

    def _repair_primary(self, recovered: dict[str, Any]) -> None:
        """Best-effort rewrite of the corrupt primary from a validated backup.

        Without this, every subsequent load re-reads the broken primary and
        appends another recovery event. Never touches the backup itself.
        """
        try:
            self._atomic_write(recovered, backup=False)
        except OSError:
            pass

    def save(self, state: dict[str, Any]) -> None:
        self.validate(state)
        self._atomic_write(state, backup=True)

    def _atomic_write(self, state: dict[str, Any], *, backup: bool) -> None:
        state["updated_at"] = _now()
        directory = self.skill_dir(state)
        directory.mkdir(parents=True, exist_ok=True)
        target = self.state_path(state["state_id"])
        fd, temp_name = tempfile.mkstemp(prefix="progress-state-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if backup and target.exists():
                shutil.copy2(target, self.backup_path(state["state_id"]))
            Path(temp_name).replace(target)
        finally:
            Path(temp_name).unlink(missing_ok=True)

    @staticmethod
    def migrate(state: dict[str, Any]) -> dict[str, Any]:
        migrated = copy.deepcopy(state)
        if "skill_types" not in migrated and "skill_type" in migrated:
            migrated["skill_types"] = [migrated["skill_type"]]
        return migrated

    @staticmethod
    def validate(state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise StateValidationError("State must be a JSON object", fields=["state"])
        required = {"state_id", "skill_name", "skill_type", "skill_types", "learning_mode", "current_phase", "subskills"}
        missing = sorted(required - state.keys())
        if missing:
            raise StateValidationError("Missing required state fields", fields=missing)
        fields: list[str] = []
        if not isinstance(state["state_id"], str) or not state["state_id"].strip():
            fields.append("state_id")
        if not isinstance(state["skill_name"], str) or not state["skill_name"].strip():
            fields.append("skill_name")
        phase = state["current_phase"]
        mode = state["learning_mode"]
        skill_type = state["skill_type"]
        if not isinstance(phase, str) or phase not in PHASES:
            fields.append("current_phase")
        if not isinstance(mode, str) or mode not in MODES:
            fields.append("learning_mode")
        if not isinstance(skill_type, str) or skill_type not in SKILL_TYPES:
            fields.append("skill_type")
        skill_types = state["skill_types"]
        if not isinstance(skill_types, list) or not skill_types or any(
            not isinstance(item, str) or item not in SKILL_TYPES for item in skill_types
        ):
            fields.append("skill_types")
        elif skill_type in SKILL_TYPES and skill_type not in skill_types:
            fields.append("skill_type")
        if phase == "completed" and mode != "learn":
            fields.extend(["current_phase", "learning_mode"])
        if phase == "completed" and state.get("retention_due") is not None:
            fields.append("retention_due")
        if phase == "retention" and mode != "learn_retain":
            fields.append("learning_mode")
        due = state.get("retention_due")
        if due is not None and not _is_iso_date(due):
            fields.append("retention_due")
        subskills = state.get("subskills", [])
        if not isinstance(subskills, list) or not all(isinstance(item, dict) for item in subskills):
            fields.append("subskills")
        else:
            ids = {item.get("id") for item in subskills}
            for index, item in enumerate(subskills):
                mastery = item.get("mastery_level", 0.0)
                if not isinstance(mastery, (int, float)) or isinstance(mastery, bool) or not 0.0 <= mastery <= 1.0:
                    fields.append(f"subskills[{index}].mastery_level")
                dependencies = item.get("dependencies", [])
                if not isinstance(dependencies, list) or any(dependency not in ids for dependency in dependencies):
                    fields.append(f"subskills[{index}].dependencies")
        completed_at = state.get("completed_at")
        if completed_at is not None:
            try:
                datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                fields.append("completed_at")
        if fields:
            raise StateValidationError("Invalid state fields", fields=sorted(set(fields)))

    def _append_recovery_event(self, state_id: str, error: Exception) -> None:
        directory = self.skill_dir(state_id)
        directory.mkdir(parents=True, exist_ok=True)
        with self.recovery_events_path(state_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": _now(), "event": "backup_recovered", "error": str(error)}, ensure_ascii=False) + "\n")
