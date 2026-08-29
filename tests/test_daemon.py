from __future__ import annotations

import json
import shutil
from pathlib import Path

from thinkkoma.daemon import run_daemon

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "broken_add"


def test_daemon_drains_inbox_once(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    shutil.copytree(FIXTURE, workspace)
    inbox = tmp_path / "inbox"
    (inbox / "new").mkdir(parents=True)
    problem = {"problem": "pytest が失敗しているので直して", "workspace": str(workspace)}
    (inbox / "new" / "job.json").write_text(json.dumps(problem), encoding="utf-8")

    reports = run_daemon(inbox, default_workspace=workspace, once=True)
    assert len(reports) == 1
    assert reports[0].solved is True
    assert (inbox / "done" / "job.json").exists()
    assert not (inbox / "new" / "job.json").exists()
