#!/usr/bin/env python3
"""Small JSON CLI for deterministic LRP operations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from learning_retention.state import StateStore, StateValidationError  # noqa: E402


def envelope(ok: bool, data=None, error=None):
    return {"ok": ok, "data": data, "error": error, "meta": {"schema_version": "0.1.0"}}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("skill_name")
    init.add_argument("--context", default="{}")
    load = sub.add_parser("load")
    load.add_argument("state_id")
    validate = sub.add_parser("validate")
    validate.add_argument("state", type=Path)
    args = parser.parse_args()
    store = StateStore()
    try:
        if args.command == "init":
            data = store.init_state(args.skill_name, json.loads(args.context))
        elif args.command == "load":
            data = store.load(args.state_id)
        else:
            data = json.loads(args.state.read_text(encoding="utf-8"))
            store.validate(store.migrate(data))
            data = {"path": str(args.state)}
        print(json.dumps(envelope(True, data=data), ensure_ascii=False, default=str))
        return 0
    except (OSError, json.JSONDecodeError, StateValidationError) as exc:
        code = getattr(exc, "code", None) or ("IO_ERROR" if isinstance(exc, OSError) else "INVALID_INPUT")
        error = {"code": code, "message": str(exc), "fields": getattr(exc, "fields", [])}
        print(json.dumps(envelope(False, error=error), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
