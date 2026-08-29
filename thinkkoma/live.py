"""Forever loop: think → run → next think. Halt only on cycle limit, interrupt, or process kill."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from thinkkoma.loop import run_mission
from thinkkoma.models import Budget, MissionReport, StopReason
from thinkkoma.patrol import PatrolState
from thinkkoma.safety import resolve_workspace
from thinkkoma.think import Thought, think, write_thought
from thinkkoma.tools.fs import write_text


@dataclass
class CycleRecord:
    cycle: int
    thought: Thought
    mission: MissionReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "thought": self.thought.to_dict(),
            "mission": self.mission.to_dict(),
        }


@dataclass
class LiveReport:
    workspace: str
    stop_reason: StopReason
    cycles: list[CycleRecord] = field(default_factory=list)
    status_path: str | None = None

    @property
    def quiet(self) -> bool:
        if not self.cycles:
            return True
        last = self.cycles[-1].thought
        return last.kind.value != "signal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "stop_reason": self.stop_reason.value,
            "quiet": self.quiet,
            "cycles": [item.to_dict() for item in self.cycles],
            "status_path": self.status_path,
        }


Emitter = Callable[[str], None]


def _emit(emitter: Emitter | None, text: str) -> None:
    if emitter is not None:
        emitter(text)


def _write_live_status(workspace: Path, report: LiveReport) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    relative = f".thinkkoma/patrol/{stamp}-live.md"
    lines = [
        "# ThinkKoma live",
        "",
        f"- stop_reason: `{report.stop_reason.value}`",
        f"- cycles: {len(report.cycles)}",
        f"- quiet: {report.quiet}",
        "",
        "## Cycles",
        "",
    ]
    if report.cycles:
        for item in report.cycles:
            mark = "solved" if item.mission.solved else "unsolved"
            stop = item.mission.stop_reason.value if item.mission.stop_reason else "unknown"
            lines.append(
                f"- #{item.cycle} think `{item.thought.kind.value}` → run `{mark}` stop=`{stop}`"
            )
    else:
        lines.append("- none")
    write_text(workspace, relative, "\n".join(lines) + "\n")
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"
    write_text(workspace, ".thinkkoma/live/latest.json", payload)
    write_text(workspace, ".thinkkoma/patrol/latest.json", payload)
    return resolve_workspace(workspace) / relative


def run_live(
    workspace: Path,
    *,
    inbox: Path | None = None,
    budget: Budget | None = None,
    max_cycles: int = 0,
    interval: float = 1.0,
    emitter: Emitter | None = None,
) -> LiveReport:
    """Run think → mission → next think.

    ``max_cycles`` 0 means forever. A single cycle is still think then run.
    """
    root = resolve_workspace(workspace)
    state = PatrolState(root)
    limits = budget or Budget()
    cycles: list[CycleRecord] = []
    last_report: MissionReport | None = None
    stop_reason = StopReason.INTERRUPTED
    cycle = 0

    try:
        while True:
            cycle += 1
            thought = think(
                root,
                cycle=cycle,
                inbox=inbox,
                state=state,
                last_report=last_report,
            )
            write_thought(root, thought)
            _emit(
                emitter,
                f"think #{cycle} [{thought.kind.value}] {thought.problem}\n",
            )

            mission = run_mission(thought.problem, root, budget=limits)
            last_report = mission
            if thought.kind.value == "signal":
                if mission.solved:
                    state.mark_solved(thought.fingerprint)
                else:
                    reason = mission.stop_reason.value if mission.stop_reason else "unsolved"
                    state.mark_exhausted(thought.fingerprint, reason)

            record = CycleRecord(cycle=cycle, thought=thought, mission=mission)
            cycles.append(record)
            mark = "SOLVED" if mission.solved else "UNSOLVED"
            stop = mission.stop_reason.value if mission.stop_reason else "unknown"
            _emit(emitter, f"run   #{cycle} {mark} stop={stop}\n")

            if max_cycles > 0 and cycle >= max_cycles:
                stop_reason = StopReason.CYCLE_LIMIT
                break
            if interval > 0:
                time.sleep(interval)
    except KeyboardInterrupt:
        stop_reason = StopReason.INTERRUPTED

    report = LiveReport(workspace=str(root), stop_reason=stop_reason, cycles=cycles)
    report.status_path = str(_write_live_status(root, report))
    return report


def stdout_emitter(stream: TextIO) -> Emitter:
    def emit(text: str) -> None:
        stream.write(text)
        stream.flush()

    return emit
