from __future__ import annotations

from pathlib import Path

from thinkkoma.interpret import interpret_problem
from thinkkoma.models import GoalKind


def test_japanese_failing_tests_are_repair_intent(tmp_path: Path) -> None:
    (tmp_path / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    goal, votes = interpret_problem("テストが落ちているので人に聞かず直して", tmp_path)
    assert goal.kind == GoalKind.REPAIR_TESTS
    assert "pytest or unittest exits 0" in goal.success_criteria
    assert [vote.unit for vote in votes] == ["0号", "1号", "2号", "3号", "4号", "5号", "6号", "7号"]


def test_write_file_intent_from_japanese(tmp_path: Path) -> None:
    goal, _votes = interpret_problem("hello.txt に完了と書いて", tmp_path)
    assert goal.kind == GoalKind.WRITE_FILE
    assert goal.write_path == "hello.txt"
    assert goal.write_content is not None
    assert "完了" in goal.write_content


def test_propose_only_does_not_auto_execute(tmp_path: Path) -> None:
    goal, _votes = interpret_problem("改善のアイデアを提案して", tmp_path)
    assert goal.kind == GoalKind.PROPOSE
    assert goal.execute_best_idea is False
