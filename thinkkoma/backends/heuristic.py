from __future__ import annotations

from pathlib import Path

from thinkkoma.backends.base import Backend
from thinkkoma.interpret import interpret_problem
from thinkkoma.models import Goal


class HeuristicBackend(Backend):
    name = "heuristic"

    def interpret(self, problem: str, workspace: Path) -> Goal | None:
        goal, _votes = interpret_problem(problem, workspace)
        return goal
