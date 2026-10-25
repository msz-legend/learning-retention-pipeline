import json
from dataclasses import dataclass
from pathlib import Path


class WikiLog:
    def __init__(self, path: Path):
        self.path = path

    def append(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
