from __future__ import annotations

from thinkkoma.models import Goal, GoalKind, Step, StepKind


def plan_steps(goal: Goal, *, previous_failures: list[str] | None = None) -> list[Step]:
    failures = previous_failures or []
    retry_note = f" previous failures: {failures[-3:]}" if failures else ""
    focus = next((item for item in reversed(failures) if item.startswith("backprop:")), "")
    if goal.kind == GoalKind.WRITE_FILE:
        return [
            Step(StepKind.WRITE_FILE, "Write the requested file", goal.write_path, goal.write_content),
            Step(StepKind.SUBMIT, "Submit the write as a local dossier"),
        ]
    if goal.kind == GoalKind.PROPOSE:
        return [
            Step(StepKind.INVENTORY, "Index the workspace before ranking ideas"),
            Step(StepKind.PROPOSE, "Rank autonomous next actions"),
            Step(StepKind.SUBMIT, "Submit the idea dossier"),
        ]
    if goal.kind == GoalKind.REPAIR_TESTS:
        return [
            Step(StepKind.INVENTORY, "Index the workspace"),
            Step(
                StepKind.RUN_TESTS,
                "Observe the current failure" + retry_note + (f" {focus}" if focus else ""),
            ),
            Step(StepKind.REPAIR_PYTHON, "Mutate Python until tests pass"),
            Step(StepKind.RUN_TESTS, "Verify the repair"),
            Step(StepKind.SUBMIT, "Submit the repair dossier"),
        ]
    if goal.kind == GoalKind.DIAGNOSE:
        return [
            Step(StepKind.INVENTORY, "Index logs and source"),
            Step(StepKind.DIAGNOSE, "Infer a cause from files and the problem text"),
            Step(StepKind.SUBMIT, "Submit the diagnosis"),
        ]
    return [
        Step(StepKind.INVENTORY, "Index the workspace"),
        Step(StepKind.PROPOSE, "Rank a next autonomous action"),
        Step(StepKind.RUN_TESTS, "Use tests as an oracle when present"),
        Step(StepKind.REPAIR_PYTHON, "Attempt a bounded Python repair"),
        Step(StepKind.RUN_TESTS, "Re-check the oracle"),
        Step(StepKind.SUBMIT, "Submit the mission dossier"),
    ]
