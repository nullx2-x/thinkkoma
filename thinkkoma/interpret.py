from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from thinkkoma.models import Goal, GoalKind, UnitVote
from thinkkoma.tools.fs import inventory
from thinkkoma.units import UNITS

_TEST_HINT = re.compile(
    r"テスト|落ち|失敗|バグ|直して|修正|fix|fail|broken|error|エラー|pytest|unittest",
    re.IGNORECASE,
)
_WRITE_JA = re.compile(r"(?P<path>[\w./-]+\.\w+)\s*に\s*(?P<body>.+?)\s*と書")
_WRITE_EN = re.compile(
    r"write\s+(?P<body>.+?)\s+to\s+(?P<path>[\w./-]+\.\w+)",
    re.IGNORECASE,
)
_DIAGNOSE_HINT = re.compile(r"原因|調査|診断|なぜ|diagnose|root cause|log", re.IGNORECASE)
_IMPLEMENT_HINT = re.compile(r"実装|作って|追加|implement|add feature", re.IGNORECASE)
_PROPOSE_HINT = re.compile(r"提案|アイデア|アイディア|方針を|案を出", re.IGNORECASE)
_EXECUTE_HINT = re.compile(r"実行|直して|修正|実装|やって|進め|fix|implement", re.IGNORECASE)


def _has_tests(files: list[str]) -> bool:
    return any(
        name.startswith("test_") or name.endswith("_test.py") or "/tests/" in name.replace("\\", "/")
        for name in files
    )


def _write_goal(problem: str) -> Goal | None:
    match = _WRITE_JA.search(problem) or _WRITE_EN.search(problem)
    if not match:
        return None
    body = match.group("body").strip().strip("「」\"'")
    path = match.group("path").strip()
    return Goal(
        kind=GoalKind.WRITE_FILE,
        summary=f"Write {path} without waiting for confirmation",
        success_criteria=[f"{path} exists", f"{path} contains the requested text"],
        confidence=0.92,
        write_path=path,
        write_content=body + ("\n" if not body.endswith("\n") else ""),
        execute_best_idea=False,
    )


def interpret_problem(problem: str, workspace: Path) -> tuple[Goal, list[UnitVote]]:
    text = problem.strip()
    if not text:
        raise ValueError("Problem text is empty")
    files = inventory(workspace)
    votes: list[UnitVote] = []

    write_goal = _write_goal(text)
    propose = bool(_PROPOSE_HINT.search(text))
    execute = bool(_EXECUTE_HINT.search(text))
    if write_goal is not None:
        primary = write_goal
    elif propose and not execute:
        primary = Goal(
            kind=GoalKind.PROPOSE,
            summary="Rank ideas and submit them without waiting for a human to pick",
            success_criteria=["At least one idea is recorded", "A submission exists in .thinkkoma/outbox"],
            confidence=0.88,
            execute_best_idea=False,
        )
    elif _TEST_HINT.search(text) or _has_tests(files):
        primary = Goal(
            kind=GoalKind.REPAIR_TESTS,
            summary="Make the workspace tests pass without asking a human",
            success_criteria=["pytest or unittest exits 0"],
            confidence=0.86 if _TEST_HINT.search(text) else 0.64,
            notes=[f"indexed {len(files)} files"],
        )
    elif _DIAGNOSE_HINT.search(text):
        primary = Goal(
            kind=GoalKind.DIAGNOSE,
            summary="Produce a diagnosis from the workspace and problem text",
            success_criteria=["A diagnosis report with a likely cause is written"],
            confidence=0.7,
        )
    elif _IMPLEMENT_HINT.search(text):
        primary = Goal(
            kind=GoalKind.IMPLEMENT,
            summary="Implement the requested change and verify what can be verified locally",
            success_criteria=["Requested files exist", "Local tests pass if present"],
            confidence=0.6,
        )
    elif propose:
        primary = Goal(
            kind=GoalKind.PROPOSE,
            summary="Propose ranked ideas, then drive the best one without asking",
            success_criteria=["Best idea is adopted and verified locally"],
            confidence=0.7,
            execute_best_idea=True,
        )
    else:
        primary = Goal(
            kind=GoalKind.EXPLORE,
            summary="Inspect the workspace, infer the defect, and close it if a verifier exists",
            success_criteria=["A report is written", "Tests pass if the workspace has them"],
            confidence=0.45,
            notes=[f"indexed {len(files)} files"],
        )

    for unit in UNITS:
        goal = primary
        if unit.role == "critic":
            goal = replace(
                primary,
                confidence=min(1.0, primary.confidence + 0.05),
                notes=[*primary.notes, "Will accept only evidence, not hope"],
            )
        votes.append(
            UnitVote(
                unit=unit.name,
                role=unit.role,
                goal=goal,
                rationale=unit.mandate,
            )
        )
    return primary, votes
