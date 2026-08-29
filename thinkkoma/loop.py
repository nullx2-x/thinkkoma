from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from thinkkoma.act import execute_step
from thinkkoma.backends.client import backend_name
from thinkkoma.critique import critique_goal
from thinkkoma.halt import decide_stop, denied_streak
from thinkkoma.interpret import interpret_problem
from thinkkoma.memory import Memory
from thinkkoma.models import (
    Budget,
    Goal,
    GoalKind,
    MissionReport,
    StepKind,
    StepResult,
    StepStatus,
    StopReason,
)
from thinkkoma.plan import plan_steps
from thinkkoma.propose import adopt_idea, generate_ideas
from thinkkoma.safety import resolve_workspace
from thinkkoma.score import evaluate
from thinkkoma.scorecard import Scorecard
from thinkkoma.submit import submit_dossier


def _write_report(workspace: Path, report: MissionReport) -> Path:
    root = resolve_workspace(workspace) / ".thinkkoma" / "reports"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = root / f"{stamp}.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = root / f"{stamp}.md"
    status = "SOLVED" if report.solved else "UNSOLVED"
    stop = report.stop_reason.value if report.stop_reason else "unknown"
    score_md = ""
    card = report.scorecard
    if card is not None:
        rows = "\n".join(
            f"| {view.name} | {view.plus:.2f} | {view.minus:.2f} | {view.net:.2f} | {view.residual:.2f} |"
            for view in card.viewpoints
        )
        score_md = (
            "\n## Scorecard\n\n"
            f"- spec_ok: `{card.spec_ok}`\n"
            f"- retry_stage: `{card.retry_stage}`\n"
            f"- reenact_rounds: `{card.reenact_rounds}`\n"
            f"- affirmer: `{card.affirmer}` passed=`{card.affirmer_passed}`\n"
            f"- negator: `{card.negator}` passed=`{card.negator_passed}`\n\n"
            "| viewpoint | plus | minus | net | residual |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"{rows}\n"
        )
    markdown.write_text(
        f"# ThinkKoma mission {status}\n\n"
        f"- workspace: `{report.workspace}`\n"
        f"- stop_reason: `{stop}`\n"
        f"- goal: {report.goal.kind.value} — {report.goal.summary}\n\n"
        f"## Problem\n\n{report.problem}\n\n"
        f"## Summary\n\n{report.summary}\n"
        f"{score_md}",
        encoding="utf-8",
    )
    return path


def _apply_backend(problem: str, workspace: Path, goal: Goal) -> Goal:
    name = backend_name()
    overlay = None
    if name in {"ollama", "local"}:
        from thinkkoma.backends.ollama import LocalLLMBackend

        overlay = LocalLLMBackend().interpret(problem, workspace)
    elif name == "openai":
        from thinkkoma.backends.openai_compat import OpenAICompatBackend

        overlay = OpenAICompatBackend().interpret(problem, workspace)
    elif name == "cursor":
        from thinkkoma.backends.cursor_sdk import CursorSdkBackend

        overlay = CursorSdkBackend().interpret(problem, workspace)
    return overlay or goal


def _drive(goal: Goal, problem: str, workspace: Path) -> Goal:
    ideas = generate_ideas(problem, workspace)
    goal.ideas = ideas
    if goal.kind == GoalKind.PROPOSE and not goal.execute_best_idea:
        return goal
    if goal.execute_best_idea and goal.kind in {GoalKind.PROPOSE, GoalKind.EXPLORE} and ideas:
        adopted = adopt_idea(ideas[0])
        adopted.ideas = ideas
        return adopted
    return goal


def run_mission(
    problem: str,
    workspace: Path,
    *,
    budget: Budget | None = None,
) -> MissionReport:
    root = resolve_workspace(workspace)
    limits = budget or Budget()
    memory = Memory(root)
    started = time.monotonic()
    goal, votes = interpret_problem(problem, root)
    goal = _apply_backend(problem, root, goal)
    goal = _drive(goal, problem, root)
    memory.record(
        {
            "kind": "interpret",
            "goal": goal.to_dict(),
            "votes": [{"unit": vote.unit, "role": vote.role, "rationale": vote.rationale} for vote in votes],
        }
    )

    steps: list[StepResult] = []
    critiques = []
    failures: list[str] = []
    solved = False
    stop_reason: StopReason | None = None
    previous_reasons: list[str] = []
    stall_count = 0
    last_card: Scorecard | None = None

    for attempt in range(1, limits.max_attempts + 1):
        planned = plan_steps(goal, previous_failures=failures)
        for step in planned:
            if len(steps) >= limits.max_steps:
                failures.append("step budget exhausted")
                break
            if step.kind in {StepKind.REPORT, StepKind.SUBMIT} and goal.kind != GoalKind.PROPOSE:
                continue
            result = execute_step(root, step, goal)
            steps.append(result)
            memory.record({"kind": "step", "attempt": attempt, **result.to_dict()})
            if result.status == StepStatus.DENIED:
                failures.append(result.output)
        critique = critique_goal(root, goal, steps)
        card, _ctx = evaluate(root, goal, steps, critique, reenact=True)
        if card.disagreement:
            critique = critique_goal(root, goal, steps)
            card, _ctx = evaluate(root, goal, steps, critique, reenact=True)
        last_card = card
        critiques.append(critique)
        memory.record(
            {
                "kind": "critique",
                "attempt": attempt,
                **critique.to_dict(),
                "scorecard": card.to_dict(),
            }
        )
        solved = bool(critique.solved and card.spec_ok)
        if card.retry_stage != "none":
            failures.append(f"backprop:{card.retry_stage}:{card.residual('oracle'):.2f}")
        if critique.reasons == previous_reasons:
            stall_count += 1
        else:
            stall_count = 0
            previous_reasons = list(critique.reasons)
        if not solved:
            failures.extend(critique.reasons)
        stop_reason = decide_stop(
            solved=solved,
            attempt=attempt,
            steps=steps,
            budget=limits,
            elapsed_sec=time.monotonic() - started,
            stall_count=stall_count,
            denied_streak=denied_streak(steps),
        )
        if stop_reason is not None:
            break

    if solved and goal.kind == GoalKind.PROPOSE and not goal.execute_best_idea:
        stop_reason = StopReason.SUBMITTED
    elif stop_reason is None:
        stop_reason = StopReason.SOLVED if solved else StopReason.BUDGET_ATTEMPTS

    summary = _summarize(goal, solved, critiques, failures, stop_reason)
    report = MissionReport(
        problem=problem,
        workspace=str(root),
        solved=solved,
        goal=goal,
        steps=steps,
        critiques=critiques,
        summary=summary,
        stop_reason=stop_reason,
        ideas=list(goal.ideas),
        scorecard=last_card,
    )
    report.finished_at = datetime.now(UTC).isoformat()
    report.report_path = str(_write_report(root, report))
    report.submission_path = str(submit_dossier(root, report))
    memory.record(
        {
            "kind": "mission",
            "solved": solved,
            "stop_reason": stop_reason.value,
            "summary": summary,
            "report": report.report_path,
            "submission": report.submission_path,
            "scorecard": None if last_card is None else last_card.to_dict(),
        }
    )
    return report


def _summarize(
    goal: Goal,
    solved: bool,
    critiques: list,
    failures: list[str],
    stop_reason: StopReason,
) -> str:
    if solved and stop_reason == StopReason.SUBMITTED:
        return f"Units submitted ranked ideas for a {goal.kind.value} mission without asking a human"
    if solved:
        last = critiques[-1].reasons[0] if critiques and critiques[-1].reasons else "success criteria met"
        return f"Autonomous units closed a {goal.kind.value} mission: {last}"
    reason = failures[-1] if failures else "the critic could not verify success"
    return f"Units halted ({stop_reason.value}) on a {goal.kind.value} mission: {reason}"
