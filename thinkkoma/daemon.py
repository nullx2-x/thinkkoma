from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from thinkkoma.loop import run_mission
from thinkkoma.models import Budget, MissionReport
from thinkkoma.safety import resolve_workspace


def _resolve_declared_workspace(path: Path, workspace: str | None) -> Path | None:
    if not workspace:
        return None
    declared = Path(workspace).expanduser()
    if not declared.is_absolute():
        declared = (path.parent / declared).resolve()
    return declared


def _read_problem(path: Path) -> tuple[str, Path | None]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(raw)
        problem = str(data.get("problem") or data.get("task") or "").strip()
        return problem, _resolve_declared_workspace(path, data.get("workspace"))
    if raw.startswith("workspace:"):
        header, _, body = raw.partition("\n")
        workspace = header.split(":", 1)[1].strip()
        if body.startswith("---\n"):
            body = body[4:]
        return body.strip(), _resolve_declared_workspace(path, workspace)
    return raw.strip(), None


def process_item(path: Path, *, default_workspace: Path, budget: Budget | None = None) -> MissionReport:
    problem, workspace = _read_problem(path)
    if not problem:
        raise ValueError(f"Inbox item has no problem text: {path}")
    target = resolve_workspace(workspace or default_workspace)
    return run_mission(problem, target, budget=budget)


def run_daemon(
    inbox: Path,
    *,
    default_workspace: Path,
    once: bool = False,
    interval: float = 2.0,
    budget: Budget | None = None,
) -> list[MissionReport]:
    inbox = inbox.expanduser().resolve()
    for name in ("new", "running", "done", "failed"):
        (inbox / name).mkdir(parents=True, exist_ok=True)
    reports: list[MissionReport] = []
    while True:
        items = sorted((inbox / "new").iterdir())
        for item in items:
            if not item.is_file() or item.suffix not in {".md", ".txt", ".json"}:
                continue
            running = inbox / "running" / item.name
            shutil.move(str(item), str(running))
            try:
                report = process_item(running, default_workspace=default_workspace, budget=budget)
                dest_dir = inbox / ("done" if report.solved else "failed")
                shutil.move(str(running), str(dest_dir / running.name))
                if report.report_path:
                    shutil.copy(report.report_path, dest_dir / f"{running.stem}.report.json")
                reports.append(report)
            except Exception as exc:  # noqa: BLE001 - daemon must isolate a bad inbox item
                failed = inbox / "failed" / running.name
                if running.exists():
                    shutil.move(str(running), str(failed))
                (inbox / "failed" / f"{running.name}.error.txt").write_text(str(exc), encoding="utf-8")
        if once:
            return reports
        time.sleep(interval)
