from __future__ import annotations

from thinkkoma.halt import decide_stop, denied_streak
from thinkkoma.models import Budget, Step, StepKind, StepResult, StepStatus, StopReason


def test_solved_wins() -> None:
    reason = decide_stop(
        solved=True,
        attempt=1,
        steps=[],
        budget=Budget(),
        elapsed_sec=1,
        stall_count=9,
        denied_streak=9,
    )
    assert reason is StopReason.SOLVED


def test_time_budget() -> None:
    reason = decide_stop(
        solved=False,
        attempt=1,
        steps=[],
        budget=Budget(max_seconds=10),
        elapsed_sec=10,
        stall_count=0,
        denied_streak=0,
    )
    assert reason is StopReason.BUDGET_TIME


def test_denied_streak_counts_tail() -> None:
    denied = StepResult(Step(StepKind.INVENTORY), StepStatus.DENIED, "no")
    ok = StepResult(Step(StepKind.INVENTORY), StepStatus.OK, "yes")
    assert denied_streak([ok, denied, denied]) == 2
    assert denied_streak([denied, ok]) == 0
