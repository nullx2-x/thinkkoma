from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class GoalKind(StrEnum):
    REPAIR_TESTS = "repair_tests"
    WRITE_FILE = "write_file"
    DIAGNOSE = "diagnose"
    IMPLEMENT = "implement"
    EXPLORE = "explore"
    PROPOSE = "propose"
    SUBMIT = "submit"


class StepKind(StrEnum):
    INVENTORY = "inventory"
    RUN_TESTS = "run_tests"
    REPAIR_PYTHON = "repair_python"
    WRITE_FILE = "write_file"
    DIAGNOSE = "diagnose"
    PROPOSE = "propose"
    SUBMIT = "submit"
    REPORT = "report"


class StepStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    DENIED = "denied"
    SKIPPED = "skipped"


class StopReason(StrEnum):
    SOLVED = "solved"
    SUBMITTED = "submitted"
    BUDGET_ATTEMPTS = "budget_attempts"
    BUDGET_STEPS = "budget_steps"
    BUDGET_TIME = "budget_time"
    STALLED = "stalled"
    DENIED = "denied"
    QUIET = "quiet"
    PATROL_COMPLETE = "patrol_complete"
    CYCLE_LIMIT = "cycle_limit"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class Budget:
    max_steps: int = 16
    max_attempts: int = 6
    command_timeout_sec: float = 30.0
    max_seconds: float = 120.0
    stall_limit: int = 2


@dataclass
class Idea:
    title: str
    action: GoalKind
    rationale: str
    confidence: float
    deliverable: str
    source: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action"] = self.action.value
        return payload


@dataclass
class Goal:
    kind: GoalKind
    summary: str
    success_criteria: list[str]
    confidence: float
    write_path: str | None = None
    write_content: str | None = None
    notes: list[str] = field(default_factory=list)
    ideas: list[Idea] = field(default_factory=list)
    execute_best_idea: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["ideas"] = [idea.to_dict() for idea in self.ideas]
        return payload


@dataclass
class UnitVote:
    unit: str
    role: str
    goal: Goal
    rationale: str


@dataclass
class Step:
    kind: StepKind
    detail: str = ""
    path: str | None = None
    content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


@dataclass
class StepResult:
    step: Step
    status: StepStatus
    output: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step.to_dict(),
            "status": self.status.value,
            "output": self.output,
            "extra": self.extra,
        }


@dataclass
class Critique:
    solved: bool
    reasons: list[str]
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MissionReport:
    problem: str
    workspace: str
    solved: bool
    goal: Goal
    steps: list[StepResult]
    critiques: list[Critique]
    summary: str
    report_path: str | None = None
    submission_path: str | None = None
    stop_reason: StopReason | None = None
    ideas: list[Idea] = field(default_factory=list)
    scorecard: Any | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem": self.problem,
            "workspace": self.workspace,
            "solved": self.solved,
            "goal": self.goal.to_dict(),
            "steps": [item.to_dict() for item in self.steps],
            "critiques": [item.to_dict() for item in self.critiques],
            "summary": self.summary,
            "report_path": self.report_path,
            "submission_path": self.submission_path,
            "stop_reason": None if self.stop_reason is None else self.stop_reason.value,
            "ideas": [idea.to_dict() for idea in self.ideas],
            "scorecard": None if self.scorecard is None else self.scorecard.to_dict(),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
