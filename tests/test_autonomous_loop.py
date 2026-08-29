from __future__ import annotations

import shutil
from pathlib import Path

from thinkkoma.loop import run_mission
from thinkkoma.models import Budget

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "broken_add"


def test_autonomous_pytest_repair_without_human(tmp_path: Path) -> None:
    workspace = tmp_path / "broken_add"
    shutil.copytree(FIXTURE, workspace)
    source_before = (workspace / "mathutil.py").read_text(encoding="utf-8")
    assert "a - b" in source_before

    report = run_mission(
        "テストが落ちている。人に確認せず原因を解釈して修正せよ。",
        workspace,
        budget=Budget(max_attempts=3, max_steps=12),
    )

    assert report.solved is True
    assert "a + b" in (workspace / "mathutil.py").read_text(encoding="utf-8")
    assert report.goal.kind.value == "repair_tests"
    assert report.report_path is not None
    assert Path(report.report_path).exists()
    assert report.stop_reason is not None
    assert report.stop_reason.value == "solved"
    assert report.submission_path is not None
    assert Path(report.submission_path).exists()
    assert report.ideas
    assert report.scorecard is not None
    assert report.scorecard.spec_ok is True


def test_autonomous_file_write_without_human(tmp_path: Path) -> None:
    report = run_mission("note.txt に完了と書いて", tmp_path)
    assert report.solved is True
    assert (tmp_path / "note.txt").read_text(encoding="utf-8").strip() == "完了"
    assert report.scorecard is not None
    assert report.scorecard.spec_ok is True
    assert report.scorecard.residual("oracle") <= 0.05
