from __future__ import annotations

import json
import shutil
from pathlib import Path

from thinkkoma.cli import _with_default_live, main
from thinkkoma.live import run_live
from thinkkoma.models import Budget, StopReason
from thinkkoma.think import ThoughtKind

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "broken_add"


def test_live_think_run_think_repairs_then_keeps_going(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    shutil.copytree(FIXTURE, workspace)
    report = run_live(
        workspace,
        budget=Budget(max_attempts=3, max_steps=12),
        max_cycles=2,
        interval=0.0,
    )
    assert report.stop_reason is StopReason.CYCLE_LIMIT
    assert len(report.cycles) == 2
    first, second = report.cycles
    assert first.thought.kind is ThoughtKind.SIGNAL
    assert first.mission.solved is True
    assert "a + b" in (workspace / "mathutil.py").read_text(encoding="utf-8")
    assert second.thought.kind is ThoughtKind.DIAGNOSE
    assert second.mission.solved is True
    assert Path(report.status_path or "").exists()
    assert (workspace / ".thinkkoma" / "think" / "latest.json").exists()
    assert (workspace / ".thinkkoma" / "outbox").is_dir()
    assert (workspace / ".thinkkoma" / "patrol" / "latest.json").exists()
    assert (workspace / ".thinkkoma" / "live" / "latest.json").exists()


def test_live_does_not_halt_on_a_quiet_workspace(tmp_path: Path) -> None:
    (tmp_path / "note.py").write_text("VALUE = 1\n", encoding="utf-8")
    report = run_live(
        tmp_path,
        budget=Budget(max_attempts=2, max_steps=8),
        max_cycles=2,
        interval=0.0,
    )
    assert report.stop_reason is StopReason.CYCLE_LIMIT
    assert len(report.cycles) == 2
    assert report.cycles[0].thought.kind is ThoughtKind.PROPOSE
    assert report.cycles[1].thought.kind is ThoughtKind.DIAGNOSE
    assert all(item.mission.solved for item in report.cycles)


def test_bare_cli_is_the_live_loop() -> None:
    assert _with_default_live([]) == ["live"]
    assert _with_default_live(["--workspace", "."]) == ["live", "--workspace", "."]
    assert _with_default_live(["drive"]) == ["drive"]
    assert _with_default_live(["--help"]) == ["--help"]


def test_cli_live_one_cycle_json(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "--workspace",
            str(tmp_path),
            "--max-cycles",
            "1",
            "--interval",
            "0",
            "--json",
            "--max-attempts",
            "2",
            "--max-steps",
            "8",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["stop_reason"] == "cycle_limit"
    assert len(payload["cycles"]) == 1
    assert payload["cycles"][0]["thought"]["kind"] == "propose"
