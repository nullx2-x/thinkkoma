from __future__ import annotations

import os
from pathlib import Path

from thinkkoma.backends.base import Backend
from thinkkoma.models import Goal, GoalKind


class CursorSdkBackend(Backend):
    """Optional Cursor SDK executor. Interpretation stays local; this only notes availability."""

    name = "cursor"

    def interpret(self, problem: str, workspace: Path) -> Goal | None:
        if not os.environ.get("CURSOR_API_KEY", "").strip():
            return None
        try:
            import cursor_sdk  # noqa: F401
        except ImportError:
            return None
        return Goal(
            kind=GoalKind.IMPLEMENT,
            summary="Delegate remaining implementation to a Cursor local agent after local verification",
            success_criteria=["Local tests pass if present", "Cursor run finishes without error"],
            confidence=0.5,
            notes=["cursor-sdk is available; ThinkKoma still verifies locally before accepting"],
        )

    def execute_with_cursor(self, problem: str, workspace: Path) -> str:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

        result = Agent.prompt(
            (
                "You are a unit in an autonomous think-tank. Do not ask a human. "
                f"Solve this problem in {workspace}: {problem}"
            ),
            AgentOptions(
                api_key=os.environ["CURSOR_API_KEY"],
                model=os.environ.get("THINKKOMA_CURSOR_MODEL", "composer-2.5"),
                local=LocalAgentOptions(cwd=str(workspace)),
            ),
        )
        return f"{result.status}: {getattr(result, 'result', '')}"
