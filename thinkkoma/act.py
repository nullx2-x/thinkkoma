from __future__ import annotations

from pathlib import Path

from thinkkoma.models import Goal, Step, StepKind, StepResult, StepStatus
from thinkkoma.repair_python import repair_python, summarize_failure
from thinkkoma.safety import SafetyError
from thinkkoma.tools.fs import inventory, read_text, write_text
from thinkkoma.tools.pytest_runner import run_tests


def _clip(text: str, limit: int = 4000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 16] + "\n...[truncated]"


def execute_step(workspace: Path, step: Step, goal: Goal) -> StepResult:
    try:
        if step.kind == StepKind.INVENTORY:
            files = inventory(workspace)
            return StepResult(step, StepStatus.OK, "\n".join(files), {"count": len(files)})
        if step.kind == StepKind.RUN_TESTS:
            result = run_tests(workspace)
            status = StepStatus.OK if result.passed else StepStatus.FAILED
            return StepResult(
                step,
                status,
                _clip(result.output),
                {
                    "passed": result.passed,
                    "command": result.command,
                    "hint": summarize_failure(result.output),
                },
            )
        if step.kind == StepKind.REPAIR_PYTHON:
            outcome = repair_python(workspace)
            passed = bool(outcome.test and outcome.test.passed)
            status = StepStatus.OK if outcome.changed or passed else StepStatus.FAILED
            extra = {"changed": outcome.changed}
            if outcome.test is not None:
                extra["passed"] = outcome.test.passed
            return StepResult(step, status, outcome.detail, extra)
        if step.kind == StepKind.WRITE_FILE:
            relative = step.path or goal.write_path
            content = step.content if step.content is not None else goal.write_content
            if not relative or content is None:
                return StepResult(step, StepStatus.FAILED, "Missing path or content")
            path = write_text(workspace, relative, content)
            return StepResult(step, StepStatus.OK, f"wrote {relative}", {"path": str(path)})
        if step.kind == StepKind.PROPOSE:
            from thinkkoma.propose import generate_ideas

            if not goal.ideas:
                goal.ideas = generate_ideas(goal.summary, workspace)
            titles = " / ".join(idea.title for idea in goal.ideas) or "no ideas"
            return StepResult(
                step,
                StepStatus.OK if goal.ideas else StepStatus.FAILED,
                titles,
                {"ideas": [idea.to_dict() for idea in goal.ideas]},
            )
        if step.kind == StepKind.SUBMIT:
            return StepResult(step, StepStatus.OK, "dossier will be written at halt")
        if step.kind == StepKind.DIAGNOSE:
            files = inventory(workspace)
            snippets: list[str] = []
            for name in files[:8]:
                if name.endswith((".log", ".txt", ".py", ".md")):
                    snippets.append(f"## {name}\n{read_text(workspace, name)[:800]}")
            cause = "No explicit exception was found; inspect the indexed files."
            blob = "\n".join(snippets).lower()
            for needle, label in (
                ("traceback", "A Python traceback is present"),
                ("assertionerror", "An assertion failed"),
                ("permission denied", "A permission error occurred"),
                ("connection refused", "A local service was not reachable"),
            ):
                if needle in blob or needle in goal.summary.lower():
                    cause = label
                    break
            return StepResult(step, StepStatus.OK, cause, {"files": files[:8]})
        if step.kind == StepKind.REPORT:
            return StepResult(step, StepStatus.OK, "report pending")
        return StepResult(step, StepStatus.SKIPPED, f"Unsupported step {step.kind}")
    except SafetyError as exc:
        return StepResult(step, StepStatus.DENIED, str(exc))
    except Exception as exc:  # noqa: BLE001 - operator boundary stays inside the loop
        return StepResult(step, StepStatus.FAILED, str(exc))
