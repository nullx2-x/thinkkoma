from __future__ import annotations

from pathlib import Path

from thinkkoma.backends.base import Backend
from thinkkoma.backends.client import chat_completion, parse_llm_json
from thinkkoma.models import Goal, GoalKind


class LocalLLMBackend(Backend):
    """Ollama / OpenAI-compatible local models. Missing server falls back to heuristic."""

    name = "ollama"

    def interpret(self, problem: str, workspace: Path) -> Goal | None:
        content = chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only with keys kind, summary, success_criteria, "
                        "execute_best_idea. kind must be one of repair_tests, write_file, "
                        "diagnose, implement, explore, propose. "
                        "execute_best_idea is true unless the user only asked for ideas."
                    ),
                },
                {"role": "user", "content": f"workspace={workspace}\n{problem}"},
            ]
        )
        if not content:
            return None
        try:
            data = parse_llm_json(content)
            kind = GoalKind(str(data["kind"]))
        except (KeyError, ValueError):
            return None
        criteria = data.get("success_criteria") or []
        if isinstance(criteria, str):
            criteria = [criteria]
        return Goal(
            kind=kind,
            summary=str(data.get("summary") or kind.value),
            success_criteria=[str(item) for item in criteria],
            confidence=0.78,
            execute_best_idea=bool(data.get("execute_best_idea", True)),
            notes=["interpreted by local LLM"],
        )
