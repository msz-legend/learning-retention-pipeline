"""State persistence, validation, and recovery for LRP."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

# Single platform fork in this codebase: cross-process locks on the independent
# .progress-state.lock file. Windows (msvcrt) locks a 1-byte region of the open
# handle; POSIX (Linux, macOS) takes advisory flock locks on the open file
# description. Closing the handle releases both, so a crashed process never
# deadlocks the next contender.
if os.name == "nt":
    import msvcrt
else:
    import fcntl

PHASES = {"decompose", "cognitive", "associative", "autonomous", "retention", "completed"}
MODES = {"", "learn", "learn_retain"}
SKILL_TYPES = {"procedural", "knowledge", "social", "hybrid"}
_SAFE_ID = re.compile(r"[^a-z0-9]+")
_STATE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *{f"com{i}" for i in range(1, 10)}, *{f"lpt{i}" for i in range(1, 10)}}
LOCK_FILE_NAME = ".progress-state.lock"
DEFAULT_LOCK_TIMEOUT = 5.0
_LOCK_POLL_SECONDS = 0.05
_REPLACE_BACKOFF_SECONDS = 0.01
_REPLACE_RETRY_WINDOW = 2.0
_READ_SHARE_RETRY_WINDOW = 1.0
_READ_SHARE_RETRY_BACKOFF = 0.05


class StateValidationError(ValueError):
    def __init__(self, message: str, code: str = "STATE_INVALID", fields: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.fields = fields or []


class StateLockTimeout(StateValidationError):
    """Raised when a save/init lock cannot be acquired within the timeout."""

    def __init__(self, lock_file: Path, timeout: float):
        super().__init__(
            f"could not acquire state lock within {timeout:g}s: {lock_file}",
            code="STATE_LOCK_TIMEOUT",
        )
        self.timeout = timeout


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


def _lock_fd(handle) -> None:
    """Try to acquire the cross-process lock without blocking.

    Raises ``OSError`` when the lock is currently held elsewhere. The handle is
    always positioned at byte 0 first so every contender targets the same
    1-byte region under msvcrt; flock applies to the open file description.
    This is the only platform-specific pair of functions in the project.
    """
    handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_fd(handle) -> None:
    try:
        handle.seek(0)
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass  # closing the handle releases any remaining lock


def _read_with_share_retry(path: Path) -> str:
    """read_text with bounded retries for transient Windows open conflicts.

    On a loaded machine, antivirus/indexing/sharing locks can make open()
    fail with PermissionError for brief moments. Such a failure is NOT
    evidence that the file is corrupt, so it must never trigger backup
    recovery with its audit event and primary rewrite (that would roll a
    perfectly good file back to the previous version). After the bounded
    window the original OSError is re-raised as-is.
    """
    deadline = time.monotonic() + _READ_SHARE_RETRY_WINDOW
    while True:
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_READ_SHARE_RETRY_BACKOFF)


def _atomic_replaced(temp: Path, target: Path) -> None:
    """os.replace with a short retry for Windows share conflicts.

    On POSIX os.replace is atomic and unaffected by concurrent readers. On
    Windows the rename fails with PermissionError while another handle has
    the target open without FILE_SHARE_DELETE (for example a concurrent
    load() in the middle of read_text). Retries run under the state lock, so
    the conflicting reader closes its handle momentarily and the rename then
    succeeds; persisting failures raise the original PermissionError.
    """
    deadline = time.monotonic() + _REPLACE_RETRY_WINDOW
    while True:
        try:
            os.replace(temp, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_REPLACE_BACKOFF_SECONDS)


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

    def lock_path(self, state_or_id: dict[str, Any] | str) -> Path:
        return self.skill_dir(state_or_id) / LOCK_FILE_NAME

    def wiki_log_path(self, state: dict[str, Any]) -> Path:
        """Resolve the host-facing ``wiki_log_path`` field on the current platform.

        Storage keeps the value as a portable POSIX-relative path (see
        SKILL.md), so a data directory moved between Windows, Linux, and macOS
        still resolves under ``data_dir/skills/<state_id>/``; legacy absolute
        values are honored as-is through ``Path(value)``.
        """
        value = state.get("wiki_log_path")
        skill_dir = self.skill_dir(state)
        if not isinstance(value, str) or not value:
            return skill_dir / "wiki-log.jsonl"
        candidate = Path(value.replace("\\", "/"))
        if PureWindowsPath(value).is_absolute() or value.startswith("/"):
            return Path(value)
        return skill_dir / candidate

    @contextmanager
    def _acquire(self, state_or_id: dict[str, Any] | str, timeout: float = DEFAULT_LOCK_TIMEOUT):
        """Hold the advisory lock for one write sequence.

        The lock file itself is never os.replace'd or deleted while held —
        replacing it would hand contenders a different file object than the
        lock holder. Not reentrant: nested acquisitions on the same process
        would block until timeout, so init_state and the recovery path call
        _atomic_write directly inside one held lock instead of via save().
        """
        lock_file = self.lock_path(state_or_id)
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + max(0.0, timeout)
        with open(lock_file, "a+") as handle:
            while True:
                try:
                    _lock_fd(handle)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise StateLockTimeout(lock_file, timeout) from None
                    time.sleep(_LOCK_POLL_SECONDS)
            try:
                yield
            finally:
                _unlock_fd(handle)

    def init_state(self, skill_name: str, skill_context: dict[str, Any], *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> dict[str, Any]:
        state_id = safe_skill_id(skill_name)
        # Collision check and first write share one lock: without it two
        # processes racing the same id could both pass the existence check and
        # overwrite each other's freshly created state (TOCTOU).
        with self._acquire(state_id, timeout):
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
                "wiki_log_path": "wiki-log.jsonl",
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
            self._atomic_write(state, backup=True)
        return state

    def _existing_skill_name(self, state_id: str) -> str | None:
        try:
            existing = json.loads(_read_with_share_retry(self.state_path(state_id)))
        except json.JSONDecodeError:
            return None
        except FileNotFoundError:
            return None
        if isinstance(existing, dict):
            name = existing.get("skill_name")
            return name if isinstance(name, str) else None
        return None

    def load(self, state_id: str) -> dict[str, Any]:
        path = self.state_path(state_id)
        try:
            state = json.loads(_read_with_share_retry(path))
            state = self.migrate(state)
            self.validate(state)
            return state
        except StateValidationError as schema_error:
            if schema_error.code == "STATE_INVALID":
                raise  # unreadable schema is a state problem, not a storage one
            raise StateValidationError(f"State is unreadable; primary={schema_error}", code="STATE_DIAGNOSTIC_ONLY", fields=schema_error.fields) from schema_error
        except json.JSONDecodeError as primary_error:
            # Only a failed parse is proof of corruption. OSError (including
            # transient PermissionError from share locks) stays raised above
            # so a readable-but-locked file is never "recovered" into the
            # older backup, which would silently roll back valid data.
            backup = self.backup_path(state_id)
            try:
                recovered = json.loads(_read_with_share_retry(backup))
                recovered = self.migrate(recovered)
                self.validate(recovered)
            except StateValidationError as backup_schema_error:
                raise StateValidationError(
                    f"State is unreadable; primary={primary_error}; backup={backup_schema_error}",
                    code="STATE_DIAGNOSTIC_ONLY",
                    fields=backup_schema_error.fields,
                ) from primary_error
            except (OSError, json.JSONDecodeError) as backup_error:
                fields = getattr(primary_error, "fields", [])
                raise StateValidationError(
                    f"State is unreadable; primary={primary_error}; backup={backup_error}",
                    code="STATE_DIAGNOSTIC_ONLY",
                    fields=fields,
                ) from primary_error
            try:
                self._repair_primary_with_event(state_id, primary_error, recovered)
            except (OSError, StateLockTimeout):
                pass  # recovery repair is best-effort
            return recovered

    def _repair_primary_with_event(self, state_id: str, error: Exception, recovered: dict[str, Any]) -> None:
        """Best-effort repair, under one lock: one recovery event, the rewrite.

        Without the rewrite, every subsequent load re-reads the broken primary
        and appends another recovery event. The rewrite deliberately skips the
        usual save/backup step so the corrupt primary never replaces the good
        backup. Never touches the backup itself.
        """
        with self._acquire(state_id):
            self._append_recovery_event_unlocked(state_id, error)
            self._atomic_write(recovered, backup=False)

    def save(self, state: dict[str, Any], *, timeout: float = DEFAULT_LOCK_TIMEOUT) -> None:
        self.validate(state)
        with self._acquire(state["state_id"], timeout):
            self._atomic_write(state, backup=True)

    def _atomic_write(self, state: dict[str, Any], *, backup: bool) -> None:
        # Must be called while the caller holds the state lock (save, init_state,
        # recovery) — it never locks on its own to stay reentrance-free.
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
            _atomic_replaced(Path(temp_name), target)
        finally:
            Path(temp_name).unlink(missing_ok=True)

    @staticmethod
    def migrate(state: dict[str, Any]) -> dict[str, Any]:
        migrated = copy.deepcopy(state)
        if "skill_types" not in migrated and "skill_type" in migrated:
            migrated["skill_types"] = [migrated["skill_type"]]
        migrated["wiki_log_path"] = StateStore._relativize_wiki_log_path(migrated.get("wiki_log_path"), migrated)
        return migrated

    @staticmethod
    def _relativize_wiki_log_path(value: object, state: dict[str, Any]) -> str:
        """Best-effort normalization of legacy ``wiki_log_path`` values.

        Legacy pre-relativization init_state stored an absolute path anchored
        to the creating machine. Returns a POSIX-relative string when the
        value sits under the ``data_dir/skills/<state_id>`` root recorded in
        the state; keeps the original value otherwise, so migration never
        raises on states moved between Windows, Linux, and macOS.
        """
        if not isinstance(value, str) or not value:
            return "" if not isinstance(value, str) else value
        if not (PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()):
            return PurePosixPath(value.replace("\\", "/")).as_posix()
        data_dir = state.get("data_dir")
        state_id = state.get("state_id")
        if isinstance(data_dir, str) and data_dir and isinstance(state_id, str) and state_id:
            candidate = PurePosixPath(value.replace("\\", "/"))
            base = PurePosixPath(data_dir.replace("\\", "/")) / "skills" / state_id
            try:
                return candidate.relative_to(base).as_posix()
            except ValueError:
                pass  # outside the recorded tree or moved machine: keep as-is
        return value

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

    def _append_recovery_event_unlocked(self, state_id: str, error: Exception) -> None:
        # Called under the state lock (see _repair_primary_with_event); the
        # single-line O_APPEND style write keeps the JSONL stream intact even
        # if a caller ever forgets the lock.
        self.skill_dir(state_id).mkdir(parents=True, exist_ok=True)
        with self.recovery_events_path(state_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": _now(), "event": "backup_recovered", "error": str(error)}, ensure_ascii=False) + "\n")
