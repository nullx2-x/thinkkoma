from __future__ import annotations

from pathlib import Path

from thinkkoma.critique import critique_goal
from thinkkoma.dual import Affirmer, Negator, build_context
from thinkkoma.loop import run_mission
from thinkkoma.models import Budget, Critique, Goal, GoalKind, Step, StepKind, StepResult, StepStatus
from thinkkoma.score import backpropagate, evaluate
from thinkkoma.scorecard import SPEC_TARGETS, VIEWPOINTS


def _repair_goal() -> Goal:
    return Goal(
        kind=GoalKind.REPAIR_TESTS,
        summary="Make tests pass",
        success_criteria=["pytest exits 0"],
        confidence=0.9,
    )


def test_spec_targets_use_plus_and_minus() -> None:
    assert SPEC_TARGETS["oracle"] == 1.0
    assert SPEC_TARGETS["safety"] == 1.0
    assert SPEC_TARGETS["integrity"] == 1.0
    assert set(VIEWPOINTS) >= {"oracle", "safety", "integrity", "reenact", "consensus"}


def test_affirmer_does_not_award_oracle_when_tests_fail(tmp_path: Path) -> None:
    (tmp_path / "test_x.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    steps = [StepResult(Step(StepKind.RUN_TESTS), StepStatus.FAILED, "fail", {"passed": False})]
    critique = critique_goal(tmp_path, _repair_goal(), steps)
    ctx = build_context(tmp_path, _repair_goal(), steps, critique, reenact_oracle=False)
    plus = Affirmer().score(ctx)
    minus = Negator().score(ctx)
    assert plus["oracle"][0] == 0.0
    assert minus["oracle"][0] == 1.0
    assert plus["integrity"][0] == 1.0
    assert minus["integrity"][0] == 0.0


def test_negator_rejects_unverified_completion(tmp_path: Path) -> None:
    goal = _repair_goal()
    critique = Critique(solved=True, reasons=["hope"], evidence="")
    ctx = build_context(tmp_path, goal, [], critique, reenact_oracle=False)
    minus = Negator().score(ctx)
    plus = Affirmer().score(ctx)
    assert plus["oracle"][0] == 0.0
    assert minus["oracle"][0] == 1.0
    assert minus["integrity"][0] >= 0.8


def test_backprop_sends_oracle_error_to_act(tmp_path: Path) -> None:
    (tmp_path / "test_x.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    steps = [StepResult(Step(StepKind.RUN_TESTS), StepStatus.FAILED, "fail", {"passed": False})]
    critique = critique_goal(tmp_path, _repair_goal(), steps)
    card, _ctx = evaluate(tmp_path, _repair_goal(), steps, critique, reenact=False)
    assert card.spec_ok is False
    assert card.residual("oracle") > 0.9
    assert card.retry_stage == "act"
    grads = {item.stage: item.error for item in backpropagate(card.viewpoints)}
    assert grads["act"] >= grads["submit"]


def test_dual_reenact_confirms_repaired_spec(tmp_path: Path) -> None:
    (tmp_path / "mathutil.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_mathutil.py").write_text(
        "from mathutil import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    report = run_mission(
        "テストが落ちているので直して",
        tmp_path,
        budget=Budget(max_attempts=3, max_steps=12),
    )
    assert report.solved is True
    assert report.scorecard is not None
    assert report.scorecard.spec_ok is True
    assert report.scorecard.reenacted is True
    assert report.scorecard.reenact_rounds >= 1
    assert report.scorecard.disagreement is False
    assert report.scorecard.affirmer_passed is True
    assert report.scorecard.negator_passed is True
    assert report.scorecard.residual("oracle") <= 0.05
    assert report.scorecard.residual("integrity") <= 0.05
    assert report.scorecard.retry_stage == "none"
    names = {view.name for view in report.scorecard.viewpoints}
    assert names == set(VIEWPOINTS)


def test_unrepaired_failure_stays_spec_fail(tmp_path: Path) -> None:
    (tmp_path / "test_x.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    report = run_mission(
        "テストが落ちているので直して",
        tmp_path,
        budget=Budget(max_attempts=1, max_steps=8),
    )
    assert report.solved is False
    assert report.scorecard is not None
    assert report.scorecard.spec_ok is False
    assert report.scorecard.retry_stage == "act"
    assert report.scorecard.affirmer_passed is False
    assert report.scorecard.negator_passed is False


def test_disagreement_triggers_second_reenact(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "test_x.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    steps = [StepResult(Step(StepKind.RUN_TESTS), StepStatus.OK, "ok", {"passed": True})]
    critique = critique_goal(tmp_path, _repair_goal(), steps)
    real = Affirmer.score
    calls = {"n": 0}

    def lying_then_honest(self, ctx):
        calls["n"] += 1
        plus = real(self, ctx)
        if calls["n"] == 1:
            plus["oracle"] = (0.0, "わざと否定側と食い違わせる")
        return plus

    monkeypatch.setattr(Affirmer, "score", lying_then_honest)
    card, _ctx = evaluate(tmp_path, _repair_goal(), steps, critique, reenact=True)
    assert calls["n"] >= 2
    assert card.reenact_rounds >= 2
    assert card.disagreement is False
    assert card.spec_ok is True
    assert card.retry_stage == "none"
