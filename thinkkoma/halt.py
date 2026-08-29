"""When ThinkKoma must halt. The agent never waits for a human answer."""

from __future__ import annotations

from thinkkoma.models import Budget, StepResult, StepStatus, StopReason


def decide_stop(
    *,
    solved: bool,
    attempt: int,
    steps: list[StepResult],
    budget: Budget,
    elapsed_sec: float,
    stall_count: int,
    denied_streak: int,
) -> StopReason | None:
    if solved:
        return StopReason.SOLVED
    if elapsed_sec >= budget.max_seconds:
        return StopReason.BUDGET_TIME
    if len(steps) >= budget.max_steps:
        return StopReason.BUDGET_STEPS
    if denied_streak >= 3:
        return StopReason.DENIED
    if stall_count >= budget.stall_limit:
        return StopReason.STALLED
    if attempt >= budget.max_attempts:
        return StopReason.BUDGET_ATTEMPTS
    return None


def denied_streak(steps: list[StepResult]) -> int:
    streak = 0
    for item in reversed(steps):
        if item.status == StepStatus.DENIED:
            streak += 1
            continue
        break
    return streak
