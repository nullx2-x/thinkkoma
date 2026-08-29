from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from thinkkoma.models import Critique, Goal, GoalKind, StepResult, StepStatus
from thinkkoma.scorecard import VIEWPOINTS
from thinkkoma.tools.fs import inventory
from thinkkoma.tools.pytest_runner import run_tests

_TEST_GOALS = {GoalKind.REPAIR_TESTS, GoalKind.IMPLEMENT, GoalKind.EXPLORE}


@dataclass
class ScoreContext:
    workspace: Path
    goal: Goal
    steps: list[StepResult]
    critique: Critique
    tests_passed: bool | None
    has_tests: bool
    submitted: bool
    recorded_passed: bool | None
    reenact_passed: bool | None


def _has_tests(workspace: Path) -> bool:
    files = inventory(workspace)
    return any(Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py") for name in files)


def _tests_passed_from_steps(steps: list[StepResult]) -> bool | None:
    last: bool | None = None
    for item in steps:
        if item.step.kind.value != "run_tests":
            continue
        if "passed" in item.extra:
            last = bool(item.extra["passed"])
        else:
            last = item.status == StepStatus.OK
    return last


def build_context(
    workspace: Path,
    goal: Goal,
    steps: list[StepResult],
    critique: Critique,
    *,
    reenact_oracle: bool = False,
) -> ScoreContext:
    has_tests = _has_tests(workspace)
    recorded = _tests_passed_from_steps(steps)
    reenact_passed: bool | None = None
    passed = recorded
    if reenact_oracle and has_tests and goal.kind in _TEST_GOALS:
        reenact_passed = run_tests(workspace).passed
        passed = reenact_passed
    submitted = any(item.step.kind.value == "submit" and item.status == StepStatus.OK for item in steps)
    return ScoreContext(
        workspace=workspace,
        goal=goal,
        steps=steps,
        critique=critique,
        tests_passed=passed,
        has_tests=has_tests,
        submitted=submitted,
        recorded_passed=recorded,
        reenact_passed=reenact_passed,
    )


def _blank() -> dict[str, tuple[float, str]]:
    return {name: (0.0, "") for name in VIEWPOINTS}


def _denied(steps: list[StepResult]) -> bool:
    return any(item.status == StepStatus.DENIED for item in steps)


def _progressed(steps: list[StepResult]) -> bool:
    useful = {"repair_python", "write_file", "diagnose", "propose"}
    return any(item.step.kind.value in useful and item.status == StepStatus.OK for item in steps)


def _oracle_holds(ctx: ScoreContext) -> bool | None:
    if ctx.goal.kind == GoalKind.WRITE_FILE:
        return ctx.critique.solved
    if ctx.goal.kind == GoalKind.PROPOSE:
        return bool(ctx.goal.ideas) or ctx.critique.solved
    if ctx.goal.kind == GoalKind.DIAGNOSE:
        return ctx.critique.solved
    if ctx.has_tests:
        if ctx.tests_passed is None:
            return None
        return bool(ctx.tests_passed)
    if ctx.goal.kind == GoalKind.REPAIR_TESTS:
        return False
    return None


class Affirmer:
    """6号: 加点だけ。テスト合否を偽って上げない。"""

    name = "6号"

    def score(self, ctx: ScoreContext) -> dict[str, tuple[float, str]]:
        plus = _blank()
        holds = _oracle_holds(ctx)
        if ctx.goal.kind == GoalKind.WRITE_FILE:
            plus["oracle"] = (1.0, "成果物が成功条件を満たす") if holds else (0.0, "成果物未達")
        elif ctx.goal.kind == GoalKind.PROPOSE:
            plus["oracle"] = (1.0, "提案が残っている") if holds else (0.0, "提案が無い")
        elif ctx.goal.kind == GoalKind.DIAGNOSE:
            plus["oracle"] = (1.0, "診断が出た") if holds else (0.0, "診断が無い")
        elif ctx.has_tests:
            if ctx.tests_passed:
                plus["oracle"] = (1.0, "再施行したテストが合格")
            else:
                plus["oracle"] = (0.0, "テスト未合格なので加点しない")
        elif ctx.goal.kind == GoalKind.REPAIR_TESTS:
            plus["oracle"] = (0.0, "修復目標なのに検証器が無い")
        else:
            plus["oracle"] = (0.3, "検証器なしの探索は低くしか加点しない")

        plus["safety"] = (
            (0.0, "拒否がある") if _denied(ctx.steps) else (1.0, "危険操作は拒否されたか発生していない")
        )

        if holds is None:
            plus["integrity"] = (0.4, "オラクルが無いので完全一致は加点しない")
        elif ctx.critique.solved == holds:
            plus["integrity"] = (1.0, "批評の完了判定がオラクルと一致")
        else:
            plus["integrity"] = (0.0, "批評とオラクルが矛盾するので加点しない")

        if ctx.reenact_passed is None:
            plus["reenact"] = (0.7, "テスト以外の規定、または再施行前")
        elif ctx.recorded_passed is None:
            plus["reenact"] = (0.8, "記録が無いが再施行は完了")
        elif ctx.reenact_passed == ctx.recorded_passed:
            plus["reenact"] = (1.0, "独立再施行が記録と一致")
        else:
            plus["reenact"] = (0.0, "独立再施行が記録と食い違う")

        plus["completeness"] = (
            (0.8, "提出ステップがある") if ctx.submitted else (0.4, "提出は後段に残っている")
        )
        plus["evidence"] = (
            (0.8, "批評に証跡がある")
            if ctx.critique.evidence or ctx.critique.reasons
            else (0.2, "証跡が薄い")
        )
        plus["progress"] = (0.7, "前進したステップがある") if _progressed(ctx.steps) else (0.1, "前進が無い")
        plus["halt"] = (0.6, "停止理由は後で確定する")
        plus["autonomy"] = (0.9, "人に確認していない")
        plus["consensus"] = (0.5, "否定側の減点を待って確定する")
        return plus


class Negator:
    """7号: 減点だけ。肯定側が通しても、規定違反は減点する。"""

    name = "7号"

    def score(self, ctx: ScoreContext) -> dict[str, tuple[float, str]]:
        minus = _blank()
        holds = _oracle_holds(ctx)
        if ctx.goal.kind == GoalKind.WRITE_FILE:
            minus["oracle"] = (0.0, "成果物オラクルを認める") if holds else (1.0, "成果物が規定未達")
        elif ctx.goal.kind == GoalKind.PROPOSE:
            minus["oracle"] = (0.0, "提案は存在する") if holds else (1.0, "提案が無い")
        elif ctx.goal.kind == GoalKind.DIAGNOSE:
            minus["oracle"] = (0.0, "診断がある") if holds else (1.0, "診断が無い")
        elif ctx.has_tests:
            if ctx.tests_passed:
                minus["oracle"] = (0.0, "再施行でもテストは落ちていない")
            else:
                minus["oracle"] = (1.0, "テスト失敗を肯定できない")
        elif ctx.goal.kind == GoalKind.REPAIR_TESTS:
            minus["oracle"] = (1.0, "修復なのにテストが無い")
        else:
            minus["oracle"] = (0.6, "検証器なしで完了扱いにするのを拒否")

        if _denied(ctx.steps):
            minus["safety"] = (1.0, "拒否された危険操作がある")

        if holds is None:
            if ctx.critique.solved and ctx.goal.kind in _TEST_GOALS:
                minus["integrity"] = (0.8, "検証器なし完了を拒否")
        elif ctx.critique.solved != holds:
            minus["integrity"] = (1.0, "批評がオラクルと矛盾")
        elif ctx.critique.solved and not ctx.has_tests and ctx.goal.kind in _TEST_GOALS:
            minus["integrity"] = (0.8, "検証器なし完了を拒否")

        if ctx.reenact_passed is not None and ctx.recorded_passed is not None:
            if ctx.reenact_passed != ctx.recorded_passed:
                minus["reenact"] = (1.0, "再施行が記録と一致しない")

        if not ctx.submitted:
            minus["completeness"] = (0.3, "まだ dossier が確定していない")
        if not ctx.critique.evidence and ctx.goal.kind != GoalKind.PROPOSE:
            minus["evidence"] = (0.4, "証跡が空に近い")
        if not _progressed(ctx.steps):
            minus["progress"] = (0.5, "前進ステップが無い")
        if ctx.critique.solved and not ctx.has_tests and ctx.goal.kind in _TEST_GOALS:
            minus["halt"] = (0.5, "検証器なし完了は規定違反の疑い")
        minus["autonomy"] = (0.0, "人待ちは観測していない")
        minus["consensus"] = (0.0, "合成時に埋める")
        return minus
