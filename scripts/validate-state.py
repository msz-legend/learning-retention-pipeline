#!/usr/bin/env python3
"""Validate an LRP progress-state JSON file without mutating it."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))
from learning_retention.state import StateStore, StateValidationError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    args = parser.parse_args()
    try:
        state = json.loads(args.state.read_text(encoding="utf-8"))
        StateStore.validate(StateStore.migrate(state))
    except (OSError, json.JSONDecodeError, StateValidationError) as exc:
        payload = {"ok": False, "error": getattr(exc, "code", "STATE_INVALID"), "message": str(exc), "fields": getattr(exc, "fields", [])}
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "error": None, "fields": []}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
