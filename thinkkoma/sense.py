from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from thinkkoma.repair_python import summarize_failure
from thinkkoma.safety import resolve_workspace
from thinkkoma.tools.fs import inventory, read_text
from thinkkoma.tools.pytest_runner import run_tests

_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
_TRACE_RE = re.compile(r"Traceback \(most recent call last\)|^\s*ERROR\b", re.MULTILINE)
_FAILED_RE = re.compile(r"FAILED\s+(\S+)")
_NOT_IMPL_RE = re.compile(r"raise\s+NotImplementedError")


class SignalKind(StrEnum):
    FAILING_TESTS = "failing_tests"
    SYNTAX_ERROR = "syntax_error"
    TRACEBACK = "traceback"
    INBOX = "inbox"
    NOT_IMPLEMENTED = "not_implemented"
    TODO = "todo"


@dataclass(frozen=True)
class Signal:
    kind: SignalKind
    problem: str
    fingerprint: str
    priority: float
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


def _fingerprint(kind: SignalKind, key: str) -> str:
    digest = hashlib.sha256(f"{kind.value}:{key}".encode()).hexdigest()[:12]
    return f"{kind.value}:{digest}"


def _has_tests(files: list[str]) -> bool:
    return any(Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py") for name in files)


def _inbox_items(workspace: Path, inbox: Path | None) -> list[Path]:
    roots = []
    if inbox is not None:
        roots.append(inbox.expanduser().resolve() / "new")
    roots.append(resolve_workspace(workspace) / ".thinkkoma" / "inbox" / "new")
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if path.is_file() and path.suffix in {".md", ".txt", ".json"}:
                found.append(path)
    return found


def sense_workspace(workspace: Path, *, inbox: Path | None = None) -> list[Signal]:
    root = resolve_workspace(workspace)
    files = inventory(root)
    signals: list[Signal] = []

    if _has_tests(files):
        result = run_tests(root)
        if not result.passed:
            failed = _FAILED_RE.search(result.output)
            key = failed.group(1) if failed else summarize_failure(result.output)
            signals.append(
                Signal(
                    kind=SignalKind.FAILING_TESTS,
                    problem="テストが落ちている。人の指示を待たず原因を解釈して修正せよ。",
                    fingerprint=_fingerprint(SignalKind.FAILING_TESTS, key),
                    priority=1.0,
                    evidence=summarize_failure(result.output),
                )
            )

    for name in files:
        if not name.endswith(".py"):
            continue
        source = read_text(root, name)
        try:
            ast.parse(source)
        except SyntaxError as exc:
            signals.append(
                Signal(
                    kind=SignalKind.SYNTAX_ERROR,
                    problem=f"{name} に構文エラーがある。人に聞かず診断し、閉じられる欠陥から直せ。",
                    fingerprint=_fingerprint(SignalKind.SYNTAX_ERROR, f"{name}:{exc.lineno}"),
                    priority=0.94,
                    evidence=str(exc),
                )
            )
            continue
        if _NOT_IMPL_RE.search(source):
            signals.append(
                Signal(
                    kind=SignalKind.NOT_IMPLEMENTED,
                    problem=f"{name} に NotImplementedError がある。検証器があれば人に聞かず実装して閉じよ。",
                    fingerprint=_fingerprint(SignalKind.NOT_IMPLEMENTED, name),
                    priority=0.58,
                    evidence=name,
                )
            )
        todo = _TODO_RE.search(source)
        if todo:
            signals.append(
                Signal(
                    kind=SignalKind.TODO,
                    problem=f"{name} に {todo.group(1)} が残っている。人に聞かず診断報告を提出せよ。",
                    fingerprint=_fingerprint(SignalKind.TODO, f"{name}:{todo.group(1)}"),
                    priority=0.34,
                    evidence=f"{name}:{todo.group(1)}",
                )
            )

    for name in files:
        if not name.endswith((".log", ".txt")):
            continue
        text = read_text(root, name)
        if _TRACE_RE.search(text):
            signals.append(
                Signal(
                    kind=SignalKind.TRACEBACK,
                    problem=f"{name} に失敗ログがある。人に聞かず診断し、テストがあれば修復せよ。",
                    fingerprint=_fingerprint(SignalKind.TRACEBACK, name),
                    priority=0.84,
                    evidence=name,
                )
            )

    for item in _inbox_items(root, inbox):
        raw = item.read_text(encoding="utf-8")
        if item.suffix == ".json":
            try:
                payload = json.loads(raw)
                raw = str(payload.get("problem") or payload.get("task") or raw)
            except json.JSONDecodeError:
                pass
        problem = raw.strip()
        if not problem:
            continue
        signals.append(
            Signal(
                kind=SignalKind.INBOX,
                problem=problem,
                fingerprint=_fingerprint(SignalKind.INBOX, item.name),
                priority=0.8,
                evidence=str(item),
            )
        )

    signals.sort(key=lambda item: item.priority, reverse=True)
    unique: list[Signal] = []
    seen: set[str] = set()
    for signal in signals:
        if signal.fingerprint in seen:
            continue
        seen.add(signal.fingerprint)
        unique.append(signal)
    return unique
