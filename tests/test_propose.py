from __future__ import annotations

from pathlib import Path

from thinkkoma.loop import run_mission
from thinkkoma.models import Budget, GoalKind, StopReason


def test_propose_only_submits_ranked_ideas(tmp_path: Path) -> None:
    (tmp_path / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    report = run_mission("改善のアイデアを提案して", tmp_path, budget=Budget(max_attempts=2, max_steps=8))
    assert report.solved is True
    assert report.stop_reason is StopReason.SUBMITTED
    assert report.goal.kind is GoalKind.PROPOSE
    assert report.ideas
    assert report.submission_path is not None
    text = Path(report.submission_path).read_text(encoding="utf-8")
    assert "ideas" in text
    markdown = Path(str(report.submission_path).replace(".json", ".md"))
    assert markdown.exists()
    assert "テストをオラクルにして" in markdown.read_text(encoding="utf-8")


def test_workspace_with_tests_is_driven_to_repair(tmp_path: Path) -> None:
    (tmp_path / "mathutil.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_mathutil.py").write_text(
        "from mathutil import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    report = run_mission("この作業場を見ておいて", tmp_path, budget=Budget(max_attempts=3, max_steps=12))
    assert report.solved is True
    assert "a + b" in (tmp_path / "mathutil.py").read_text(encoding="utf-8")
    assert report.stop_reason is StopReason.SOLVED


def test_unsolvable_repair_halts_on_budget_or_stall(tmp_path: Path) -> None:
    report = run_mission(
        "テストが落ちているので直して",
        tmp_path,
        budget=Budget(max_attempts=3, max_steps=20, stall_limit=2, max_seconds=30),
    )
    assert report.solved is False
    assert report.stop_reason in {StopReason.STALLED, StopReason.BUDGET_ATTEMPTS}
    assert report.submission_path is not None
