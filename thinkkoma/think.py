"""0号 thinks first. A thought is a self-authored next mission, never a human prompt."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from thinkkoma.memory import Memory
from thinkkoma.models import MissionReport
from thinkkoma.patrol import PatrolState
from thinkkoma.safety import resolve_workspace
from thinkkoma.sense import Signal, sense_workspace
from thinkkoma.tools.fs import write_text

_QUIET_ROTATION: tuple[tuple[str, str, str], ...] = (
    (
        "propose",
        "self:propose",
        "作業場は静穏だ。人に聞かず次に閉じられる改善のアイデアを提案して提出せよ。",
    ),
    (
        "diagnose",
        "self:diagnose",
        "作業場を診断し、人に聞かず残っている欠陥の原因仮説を提出せよ。",
    ),
    (
        "explore",
        "self:explore",
        "作業場を探索して索引し、次の自律行動の方針を提案して提出せよ。",
    ),
)


class ThoughtKind(StrEnum):
    SIGNAL = "signal"
    PROPOSE = "propose"
    DIAGNOSE = "diagnose"
    EXPLORE = "explore"


@dataclass
class Thought:
    cycle: int
    kind: ThoughtKind
    problem: str
    fingerprint: str
    signals: list[Signal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "kind": self.kind.value,
            "problem": self.problem,
            "fingerprint": self.fingerprint,
            "signals": [item.to_dict() for item in self.signals],
            "notes": list(self.notes),
            "path": self.path,
        }


def _quiet_slot(cycle: int) -> tuple[ThoughtKind, str, str]:
    kind, fingerprint, problem = _QUIET_ROTATION[(max(cycle, 1) - 1) % len(_QUIET_ROTATION)]
    return ThoughtKind(kind), fingerprint, problem


def think(
    workspace: Path,
    *,
    cycle: int,
    inbox: Path | None = None,
    state: PatrolState | None = None,
    last_report: MissionReport | None = None,
) -> Thought:
    root = resolve_workspace(workspace)
    patrol = state or PatrolState(root)
    signals = sense_workspace(root, inbox=inbox)
    actionable = [item for item in signals if not patrol.is_exhausted(item.fingerprint)]
    if actionable:
        target = actionable[0]
        notes = [target.evidence] if target.evidence else []
        if last_report is not None:
            previous = last_report.stop_reason.value if last_report.stop_reason else "none"
            notes.append(f"previous_stop:{previous}")
        return Thought(
            cycle=cycle,
            kind=ThoughtKind.SIGNAL,
            problem=target.problem,
            fingerprint=target.fingerprint,
            signals=signals,
            notes=notes or [target.kind.value],
        )

    kind, fingerprint, problem = _quiet_slot(cycle)
    notes = ["quiet:no_actionable_signals"]
    if last_report is not None:
        notes.append(f"previous:{'solved' if last_report.solved else 'unsolved'}")
        card = last_report.scorecard
        if card is not None and card.retry_stage != "none":
            notes.append(f"residual_stage:{card.retry_stage}")
    return Thought(
        cycle=cycle,
        kind=kind,
        problem=problem,
        fingerprint=fingerprint,
        signals=signals,
        notes=notes,
    )


def write_thought(workspace: Path, thought: Thought) -> Path:
    root = resolve_workspace(workspace)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    relative_json = f".thinkkoma/think/{stamp}-c{thought.cycle}.json"
    relative_md = f".thinkkoma/think/{stamp}-c{thought.cycle}.md"
    payload = json.dumps(thought.to_dict(), ensure_ascii=False, indent=2) + "\n"
    write_text(workspace, relative_json, payload)
    write_text(workspace, ".thinkkoma/think/latest.json", payload)
    signal_lines = (
        "\n".join(
            f"- {item.kind.value} ({item.priority:.2f}) `{item.fingerprint}`" for item in thought.signals
        )
        or "- none"
    )
    note_lines = "\n".join(f"- {note}" for note in thought.notes) or "- none"
    markdown = (
        f"# Think cycle {thought.cycle}\n\n"
        f"- kind: `{thought.kind.value}`\n"
        f"- fingerprint: `{thought.fingerprint}`\n\n"
        f"## Problem\n\n{thought.problem}\n\n"
        f"## Signals\n\n{signal_lines}\n\n"
        f"## Notes\n\n{note_lines}\n"
    )
    write_text(workspace, relative_md, markdown)
    thought.path = str(root / relative_json)
    Memory(root).record(
        {
            "kind": "think",
            "cycle": thought.cycle,
            "thought_kind": thought.kind.value,
            "fingerprint": thought.fingerprint,
            "problem": thought.problem,
            "path": thought.path,
        }
    )
    return root / relative_json
