from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from thinkkoma.loop import run_mission
from thinkkoma.models import Budget, MissionReport, StopReason
from thinkkoma.patrol import PatrolState
from thinkkoma.safety import resolve_workspace
from thinkkoma.sense import Signal, sense_workspace
from thinkkoma.tools.fs import write_text


@dataclass
class PatrolReport:
    workspace: str
    quiet: bool
    stop_reason: StopReason
    missions: list[MissionReport] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    status_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "quiet": self.quiet,
            "stop_reason": self.stop_reason.value,
            "missions": [item.to_dict() for item in self.missions],
            "signals": [item.to_dict() for item in self.signals],
            "status_path": self.status_path,
        }


def _write_status(workspace: Path, report: PatrolReport) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    relative = f".thinkkoma/patrol/{stamp}-status.md"
    lines = [
        "# ThinkKoma patrol",
        "",
        f"- quiet: {report.quiet}",
        f"- stop_reason: `{report.stop_reason.value}`",
        f"- missions: {len(report.missions)}",
        "",
        "## Signals",
        "",
    ]
    if report.signals:
        for signal in report.signals:
            lines.append(f"- {signal.kind.value} ({signal.priority:.2f}) `{signal.fingerprint}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Missions", ""])
    if report.missions:
        for mission in report.missions:
            mark = "solved" if mission.solved else "unsolved"
            lines.append(f"- {mark}: {mission.summary}")
    else:
        lines.append("- none")
    write_text(workspace, relative, "\n".join(lines) + "\n")
    return resolve_workspace(workspace) / relative


def run_patrol(
    workspace: Path,
    *,
    inbox: Path | None = None,
    once: bool = True,
    interval: float = 5.0,
    max_missions: int = 12,
    max_idle: int = 3,
    budget: Budget | None = None,
) -> PatrolReport:
    root = resolve_workspace(workspace)
    state = PatrolState(root)
    limits = budget or Budget()
    missions: list[MissionReport] = []
    last_signals: list[Signal] = []
    idle_rounds = 0
    stop_reason = StopReason.QUIET

    while True:
        signals = sense_workspace(root, inbox=inbox)
        last_signals = signals
        actionable = [item for item in signals if not state.is_exhausted(item.fingerprint)]
        if not actionable:
            idle_rounds += 1
            stop_reason = StopReason.QUIET if not signals else StopReason.PATROL_COMPLETE
            if once or idle_rounds >= max_idle:
                break
            time.sleep(interval)
            continue

        idle_rounds = 0
        target = actionable[0]
        report = run_mission(target.problem, root, budget=limits)
        missions.append(report)
        if report.solved:
            state.mark_solved(target.fingerprint)
        else:
            reason = report.stop_reason.value if report.stop_reason else "unsolved"
            state.mark_exhausted(target.fingerprint, reason)

        if len(missions) >= max_missions:
            stop_reason = StopReason.PATROL_COMPLETE
            break
        if not once:
            time.sleep(interval)

    quiet = stop_reason is StopReason.QUIET and all(item.solved for item in missions)
    patrol = PatrolReport(
        workspace=str(root),
        quiet=quiet,
        stop_reason=stop_reason,
        missions=missions,
        signals=last_signals,
    )
    patrol.status_path = str(_write_status(root, patrol))
    latest = resolve_workspace(root) / ".thinkkoma" / "patrol" / "latest.json"
    latest.write_text(json.dumps(patrol.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return patrol
