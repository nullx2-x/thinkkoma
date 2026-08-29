from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from thinkkoma.safety import resolve_workspace


class Memory:
    def __init__(self, workspace: Path) -> None:
        self.root = resolve_workspace(workspace) / ".thinkkoma"
        self.path = self.root / "memory.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def record(self, event: dict[str, Any]) -> None:
        payload = {"ts": datetime.now(UTC).isoformat(), **event}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        events: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events
