from __future__ import annotations

import shutil
from pathlib import Path

from thinkkoma.models import GoalKind
from thinkkoma.patrol import PatrolState
from thinkkoma.sense import SignalKind
from thinkkoma.think import ThoughtKind, think, write_thought

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "broken_add"


def test_think_authors_repair_from_failing_tests(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "ws")
    thought = think(tmp_path / "ws", cycle=1)
    assert thought.kind is ThoughtKind.SIGNAL
    assert thought.cycle == 1
    assert any(item.kind is SignalKind.FAILING_TESTS for item in thought.signals)
    assert "人の指示を待たず" in thought.problem


def test_think_rotates_self_authored_missions_when_quiet(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
    first = think(tmp_path, cycle=1)
    second = think(tmp_path, cycle=2)
    third = think(tmp_path, cycle=3)
    assert first.kind is ThoughtKind.PROPOSE
    assert second.kind is ThoughtKind.DIAGNOSE
    assert third.kind is ThoughtKind.EXPLORE
    assert "提案して" in first.problem
    assert "原因" in second.problem


def test_think_skips_exhausted_signals(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "ws")
    first = think(tmp_path / "ws", cycle=1)
    state = PatrolState(tmp_path / "ws")
    state.mark_exhausted(first.fingerprint, "stalled")
    again = think(tmp_path / "ws", cycle=2, state=state)
    assert again.kind is ThoughtKind.DIAGNOSE
    path = write_thought(tmp_path / "ws", again)
    assert path.exists()
    latest = tmp_path / "ws" / ".thinkkoma" / "think" / "latest.json"
    assert latest.exists()
    assert "diagnose" in latest.read_text(encoding="utf-8")


def test_diagnose_intent_wins_even_when_tests_exist(tmp_path: Path) -> None:
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    from thinkkoma.interpret import interpret_problem

    goal, _votes = interpret_problem("作業場を診断し原因仮説を提出せよ。", tmp_path)
    assert goal.kind is GoalKind.DIAGNOSE
