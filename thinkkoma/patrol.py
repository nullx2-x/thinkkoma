from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from thinkkoma.safety import resolve_workspace


class PatrolState:
    """Persists which self-found defects already stalled, so patrol does not loop forever."""

    def __init__(self, workspace: Path) -> None:
        self.root = resolve_workspace(workspace) / ".thinkkoma"
        self.path = self.root / "patrol.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"exhausted": {}, "solved": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"exhausted": {}, "solved": {}}
        payload.setdefault("exhausted", {})
        payload.setdefault("solved", {})
        return payload

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def is_exhausted(self, fingerprint: str) -> bool:
        return fingerprint in self.data["exhausted"]

    def mark_exhausted(self, fingerprint: str, reason: str) -> None:
        self.data["exhausted"][fingerprint] = {
            "reason": reason,
            "ts": datetime.now(UTC).isoformat(),
        }
        self.data["solved"].pop(fingerprint, None)
        self.save()

    def mark_solved(self, fingerprint: str) -> None:
        self.data["solved"][fingerprint] = {"ts": datetime.now(UTC).isoformat()}
        self.data["exhausted"].pop(fingerprint, None)
        self.save()
