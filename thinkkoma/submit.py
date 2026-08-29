from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from thinkkoma.models import Idea, MissionReport, StopReason
from thinkkoma.safety import resolve_workspace
from thinkkoma.tools.fs import write_text


def submit_dossier(workspace: Path, report: MissionReport) -> Path:
    root = resolve_workspace(workspace)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    relative_json = f".thinkkoma/outbox/{stamp}-submission.json"
    relative_md = f".thinkkoma/outbox/{stamp}-submission.md"
    payload = report.to_dict()
    write_text(workspace, relative_json, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    ideas = report.ideas or report.goal.ideas
    idea_lines = "\n".join(
        f"- {idea.title} [{idea.action.value}] ({idea.confidence:.2f}) → {idea.deliverable}"
        if isinstance(idea, Idea)
        else f"- {idea}"
        for idea in ideas
    ) or "- (no ranked ideas)"
    stop = report.stop_reason.value if isinstance(report.stop_reason, StopReason) else "unknown"
    markdown = (
        f"# ThinkKoma submission\n\n"
        f"- status: {'SOLVED' if report.solved else 'UNSOLVED'}\n"
        f"- stop_reason: `{stop}`\n"
        f"- workspace: `{report.workspace}`\n\n"
        f"## Problem\n\n{report.problem}\n\n"
        f"## Ideas\n\n{idea_lines}\n\n"
        f"## Summary\n\n{report.summary}\n"
    )
    write_text(workspace, relative_md, markdown)
    return root / relative_json
