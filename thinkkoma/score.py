from __future__ import annotations

from pathlib import Path

from thinkkoma.dual import Affirmer, Negator, ScoreContext, build_context
from thinkkoma.models import Critique, Goal, StepResult
from thinkkoma.scorecard import (
    HARD_VIEWPOINTS,
    SPEC_TARGETS,
    STAGE_WEIGHTS,
    VIEWPOINTS,
    Scorecard,
    StageGradient,
    ViewpointScore,
    clamp,
)


def _combine(
    plus: dict[str, tuple[float, str]],
    minus: dict[str, tuple[float, str]],
) -> list[ViewpointScore]:
    views: list[ViewpointScore] = []
    for name in VIEWPOINTS:
        added, aff_note = plus[name]
        deducted, neg_note = minus[name]
        net = clamp(added - deducted)
        target = SPEC_TARGETS[name]
        views.append(
            ViewpointScore(
                name=name,
                target=target,
                plus=added,
                minus=deducted,
                net=net,
                residual=clamp(target - net, -1.0, 1.0),
                affirmer_note=aff_note,
                negator_note=neg_note,
            )
        )
    return views


def _fill_consensus(views: list[ViewpointScore]) -> None:
    oracle = next(item for item in views if item.name == "oracle")
    agreement = 1.0 - abs(oracle.plus - (1.0 - oracle.minus))
    for item in views:
        if item.name != "consensus":
            continue
        item.plus = round(agreement, 4)
        item.minus = round(1.0 - agreement, 4)
        item.net = clamp(item.plus - item.minus)
        item.residual = clamp(item.target - item.net, -1.0, 1.0)
        item.affirmer_note = f"肯定側 oracle+={oracle.plus:.2f}"
        item.negator_note = f"否定側 oracle-={oracle.minus:.2f}"


def backpropagate(views: list[ViewpointScore], *, learning_rate: float = 1.0) -> list[StageGradient]:
    """Map viewpoint residuals onto pipeline stages (discrete backprop)."""
    gradients: list[StageGradient] = []
    for stage, weights in STAGE_WEIGHTS.items():
        total = 0.0
        for view in views:
            total += view.residual * weights.get(view.name, 0.0)
        gradients.append(StageGradient(stage=stage, error=round(learning_rate * total, 4)))
    gradients.sort(key=lambda item: item.error, reverse=True)
    return gradients


def _hard_disagreement(views: list[ViewpointScore]) -> bool:
    by_name = {item.name: item for item in views}
    for name in HARD_VIEWPOINTS:
        view = by_name[name]
        if abs(view.plus - (1.0 - view.minus)) > 0.2:
            return True
    return False


def _score_pass(
    workspace: Path,
    goal: Goal,
    steps: list[StepResult],
    critique: Critique,
    *,
    reenact: bool,
) -> tuple[list[ViewpointScore], ScoreContext, ScoreContext]:
    ctx_plus = build_context(workspace, goal, steps, critique, reenact_oracle=reenact)
    plus = Affirmer().score(ctx_plus)
    ctx_minus = build_context(workspace, goal, steps, critique, reenact_oracle=reenact)
    minus = Negator().score(ctx_minus)
    views = _combine(plus, minus)
    _fill_consensus(views)
    return views, ctx_plus, ctx_minus


def evaluate(
    workspace: Path,
    goal: Goal,
    steps: list[StepResult],
    critique: Critique,
    *,
    reenact: bool = True,
) -> tuple[Scorecard, ScoreContext]:
    views, ctx_plus, ctx_minus = _score_pass(workspace, goal, steps, critique, reenact=reenact)
    rounds = 1 if reenact else 0
    split = ctx_plus.tests_passed != ctx_minus.tests_passed
    disagreement = _hard_disagreement(views) or split
    if disagreement:
        views, ctx_plus, ctx_minus = _score_pass(workspace, goal, steps, critique, reenact=True)
        rounds += 1
        split = ctx_plus.tests_passed != ctx_minus.tests_passed
        disagreement = _hard_disagreement(views) or split
    gradients = backpropagate(views)
    spec_ok = all(item.residual <= 0.05 for item in views if item.name in HARD_VIEWPOINTS)
    if spec_ok and not disagreement:
        retry = "none"
    else:
        retry = gradients[0].stage if gradients else "none"
    card = Scorecard(
        viewpoints=views,
        spec_ok=spec_ok and not disagreement,
        retry_stage=retry,
        disagreement=disagreement,
        reenacted=reenact or rounds > 1,
        reenact_rounds=rounds,
        affirmer_passed=ctx_plus.tests_passed,
        negator_passed=ctx_minus.tests_passed,
        gradients=gradients,
        affirmer=Affirmer.name,
        negator=Negator.name,
    )
    return card, ctx_minus
