from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from thinkkoma.models import Goal


class Backend(ABC):
    name: str

    @abstractmethod
    def interpret(self, problem: str, workspace: Path) -> Goal | None:
        """Return a Goal, or None to fall back to the heuristic interpreter."""
