from __future__ import annotations

import shutil
from pathlib import Path

from thinkkoma.drive import run_patrol
from thinkkoma.models import Budget, StopReason
from thinkkoma.sense import SignalKind, sense_workspace

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "broken_add"


def test_sense_finds_failing_tests_without_a_prompt(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "ws")
    signals = sense_workspace(tmp_path / "ws")
    kinds = {item.kind for item in signals}
    assert SignalKind.FAILING_TESTS in kinds
    assert any("人の指示を待たず" in item.problem for item in signals)


def test_drive_repairs_without_human_instruction(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    shutil.copytree(FIXTURE, workspace)
    report = run_patrol(workspace, once=True, budget=Budget(max_attempts=3, max_steps=12))
    assert report.quiet is True
    assert report.stop_reason is StopReason.QUIET
    assert report.missions
    assert all(item.solved for item in report.missions)
    assert "a + b" in (workspace / "mathutil.py").read_text(encoding="utf-8")
    assert Path(report.status_path or "").exists()


def test_drive_is_quiet_on_a_healthy_workspace(tmp_path: Path) -> None:
    (tmp_path / "mathutil.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "test_mathutil.py").write_text(
        "from mathutil import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    report = run_patrol(tmp_path, once=True, budget=Budget(max_attempts=2, max_steps=8))
    assert report.quiet is True
    assert report.missions == []
    assert report.stop_reason is StopReason.QUIET
    assert not report.signals


def test_drive_does_not_retry_exhausted_unsolvable_tests(tmp_path: Path) -> None:
    (tmp_path / "test_always.py").write_text("def test_always():\n    assert False\n", encoding="utf-8")
    first = run_patrol(tmp_path, once=True, max_missions=3, budget=Budget(max_attempts=2, max_steps=8))
    assert first.quiet is False
    assert first.missions
    assert not first.missions[0].solved
    second = run_patrol(tmp_path, once=True, max_missions=3, budget=Budget(max_attempts=2, max_steps=8))
    assert second.missions == []
    assert second.stop_reason is StopReason.PATROL_COMPLETE
