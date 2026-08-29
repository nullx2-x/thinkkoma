from __future__ import annotations

from pathlib import Path

from thinkkoma.models import Critique, Goal, GoalKind, StepResult, StepStatus
from thinkkoma.safety import SafetyError, ensure_inside, resolve_workspace
from thinkkoma.tools.fs import inventory, read_text
from thinkkoma.tools.pytest_runner import run_tests


def critique_goal(workspace: Path, goal: Goal, steps: list[StepResult]) -> Critique:
    reasons: list[str] = []
    if goal.kind == GoalKind.WRITE_FILE:
        relative = goal.write_path
        if not relative or goal.write_content is None:
            return Critique(False, ["Write goal is missing path or content"])
        try:
            path = ensure_inside(workspace, resolve_workspace(workspace) / relative)
        except SafetyError as exc:
            return Critique(False, [str(exc)])
        if not path.exists():
            return Critique(False, [f"{relative} was not created"])
        actual = read_text(workspace, relative)
        expected = goal.write_content.strip()
        if expected not in actual:
            return Critique(False, [f"{relative} does not contain the requested text"], actual)
        return Critique(True, [f"{relative} matches the requested write"], actual)

    files = inventory(workspace)
    has_tests = any(
        Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py") for name in files
    )
    if goal.kind in {GoalKind.REPAIR_TESTS, GoalKind.IMPLEMENT, GoalKind.EXPLORE}:
        if has_tests:
            result = run_tests(workspace)
            if result.passed:
                return Critique(True, ["Tests pass; critic accepts the mission"], result.output[-2000:])
            if goal.kind == GoalKind.REPAIR_TESTS:
                return Critique(False, ["Tests still fail"], result.output[-2000:])
            reasons.append("Tests did not pass; mission remains open")
            return Critique(False, reasons, result.output[-2000:])
        if goal.kind == GoalKind.REPAIR_TESTS:
            return Critique(False, ["Workspace has no tests to verify a repair"])
        return Critique(True, ["No test oracle; critic accepted the recorded work"])

    if goal.kind == GoalKind.PROPOSE:
        if goal.ideas:
            return Critique(True, ["Ranked ideas are ready to submit"], goal.ideas[0].title)
        proposed = [
            item
            for item in steps
            if item.step.kind.value == "propose" and item.status == StepStatus.OK
        ]
        if proposed:
            return Critique(True, ["Ranked ideas are ready to submit"], proposed[-1].output)
        return Critique(False, ["No ideas were produced"])

    diagnoses = [
        item.output
        for item in steps
        if item.step.kind.value == "diagnose" and item.status == StepStatus.OK
    ]
    if diagnoses:
        return Critique(True, ["Diagnosis produced without asking a human"], diagnoses[-1])
    return Critique(False, ["No diagnosis was produced"])
