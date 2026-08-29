from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

VIEWPOINTS = (
    "oracle",
    "safety",
    "integrity",
    "reenact",
    "completeness",
    "evidence",
    "progress",
    "halt",
    "autonomy",
    "consensus",
)

SPEC_TARGETS: dict[str, float] = {
    "oracle": 1.0,
    "safety": 1.0,
    "integrity": 1.0,
    "reenact": 0.8,
    "completeness": 0.8,
    "evidence": 0.7,
    "progress": 0.5,
    "halt": 0.6,
    "autonomy": 0.9,
    "consensus": 0.5,
}

STAGE_WEIGHTS: dict[str, dict[str, float]] = {
    "interpret": {"autonomy": 0.5, "oracle": 0.15, "consensus": 0.1, "integrity": 0.1},
    "plan": {"progress": 0.4, "oracle": 0.15, "halt": 0.2},
    "act": {"oracle": 0.8, "progress": 0.5, "safety": 0.35, "integrity": 0.2},
    "verify": {
        "oracle": 0.35,
        "evidence": 0.6,
        "consensus": 0.5,
        "halt": 0.4,
        "reenact": 0.7,
        "integrity": 0.6,
    },
    "submit": {"completeness": 0.5, "evidence": 0.2},
}

HARD_VIEWPOINTS = ("oracle", "safety", "integrity")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class ViewpointScore:
    name: str
    target: float
    plus: float
    minus: float
    net: float
    residual: float
    affirmer_note: str = ""
    negator_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StageGradient:
    stage: str
    error: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Scorecard:
    viewpoints: list[ViewpointScore]
    spec_ok: bool
    retry_stage: str
    disagreement: bool
    reenacted: bool
    reenact_rounds: int = 0
    affirmer_passed: bool | None = None
    negator_passed: bool | None = None
    gradients: list[StageGradient] = field(default_factory=list)
    affirmer: str = "6号"
    negator: str = "7号"

    def to_dict(self) -> dict[str, Any]:
        return {
            "viewpoints": [item.to_dict() for item in self.viewpoints],
            "spec_ok": self.spec_ok,
            "retry_stage": self.retry_stage,
            "disagreement": self.disagreement,
            "reenacted": self.reenacted,
            "reenact_rounds": self.reenact_rounds,
            "affirmer_passed": self.affirmer_passed,
            "negator_passed": self.negator_passed,
            "gradients": [item.to_dict() for item in self.gradients],
            "affirmer": self.affirmer,
            "negator": self.negator,
        }

    def residual(self, name: str) -> float:
        for item in self.viewpoints:
            if item.name == name:
                return item.residual
        return 0.0

    def viewpoint(self, name: str) -> ViewpointScore | None:
        for item in self.viewpoints:
            if item.name == name:
                return item
        return None
