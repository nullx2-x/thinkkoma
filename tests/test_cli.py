from __future__ import annotations

import json
from pathlib import Path

from thinkkoma.cli import main
from thinkkoma.units import describe_units


def test_cli_units(capsys) -> None:
    assert main(["units"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == describe_units()
    assert len(payload) == 8


def test_cli_run_json(tmp_path: Path, capsys) -> None:
    code = main(["run", "hello.txt にokと書いて", "--workspace", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload["solved"] is True
    assert payload["scorecard"]["spec_ok"] is True
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8").strip() == "ok"


def test_cli_drive_without_a_problem(tmp_path: Path, capsys) -> None:
    (tmp_path / "note.py").write_text("VALUE = 1\n", encoding="utf-8")
    code = main(["drive", "--workspace", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["quiet"] is True
    assert payload["stop_reason"] == "quiet"
