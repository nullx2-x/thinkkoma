from __future__ import annotations

from pathlib import Path

from thinkkoma.backends.base import Backend
from thinkkoma.backends.client import chat_completion, parse_llm_json
from thinkkoma.models import Goal, GoalKind


class OpenAICompatBackend(Backend):
    """JSON planner for cloud OpenAI-compatible endpoints. Falls back on any error."""

    name = "openai"

    def interpret(self, problem: str, workspace: Path) -> Goal | None:
        content = chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only with keys kind, summary, success_criteria. "
                        "kind must be one of repair_tests, write_file, diagnose, implement, explore, propose."
                    ),
                },
                {"role": "user", "content": problem},
            ]
        )
        if not content:
            return None
        try:
            data = parse_llm_json(content)
            return Goal(
                kind=GoalKind(str(data["kind"])),
                summary=str(data.get("summary") or data["kind"]),
                success_criteria=list(data.get("success_criteria") or []),
                confidence=0.8,
            )
        except (KeyError, ValueError):
            return None
