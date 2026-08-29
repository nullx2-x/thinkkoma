from __future__ import annotations

from pathlib import Path

from thinkkoma.backends.client import chat_completion, llm_enabled, parse_llm_json
from thinkkoma.models import Goal, GoalKind, Idea
from thinkkoma.tools.fs import inventory


def _has_tests(files: list[str]) -> bool:
    return any(Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py") for name in files)


def heuristic_ideas(problem: str, workspace: Path) -> list[Idea]:
    files = inventory(workspace)
    ideas: list[Idea] = []
    if _has_tests(files):
        ideas.append(
            Idea(
                title="テストをオラクルにして実装を直す",
                action=GoalKind.REPAIR_TESTS,
                rationale="検証可能な失敗があるので、人に聞かずテスト合格まで自律修復できる",
                confidence=0.9,
                deliverable="修正済みソース、pytest 合格証跡、ミッション報告",
            )
        )
    has_log = any(name.endswith((".log", ".txt")) for name in files)
    if has_log or "原因" in problem or "log" in problem.lower():
        ideas.append(
            Idea(
                title="ログとソースから原因仮説を出す",
                action=GoalKind.DIAGNOSE,
                rationale="失敗の一次情報があるので、診断レポートを先に提出できる",
                confidence=0.72,
                deliverable="原因仮説と根拠ファイル一覧",
            )
        )
    ideas.append(
        Idea(
            title="作業場を探索し、閉じられる欠陥から着手する",
            action=GoalKind.EXPLORE,
            rationale="明示された検証器が弱くても、索引と局所修復で前進できる",
            confidence=0.45,
            deliverable="探索報告と次の自律行動",
        )
    )
    return ideas[:3]


def _ideas_from_llm(problem: str, workspace: Path, seed: list[Idea]) -> list[Idea] | None:
    if not llm_enabled():
        return None
    seed_text = "\n".join(f"- {idea.title} ({idea.action.value})" for idea in seed)
    content = chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "You are a think-tank unit. Do not ask a human. Return JSON "
                    '{"ideas":[{"title":str,"action":"repair_tests|diagnose|implement|explore|write_file",'
                    '"rationale":str,"confidence":number,"deliverable":str}]} '
                    "with 2 to 4 ranked ideas. Prefer actions that can finish inside a local sandbox."
                ),
            },
            {
                "role": "user",
                "content": f"problem:\n{problem}\nworkspace:\n{workspace}\nheuristic:\n{seed_text}",
            },
        ]
    )
    if not content:
        return None
    try:
        data = parse_llm_json(content)
        raw = data.get("ideas") or []
    except (ValueError, AttributeError):
        return None
    parsed: list[Idea] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            action = GoalKind(str(item.get("action") or "explore"))
        except ValueError:
            action = GoalKind.EXPLORE
        if action in {GoalKind.PROPOSE, GoalKind.SUBMIT}:
            action = GoalKind.EXPLORE
        parsed.append(
            Idea(
                title=str(item.get("title") or action.value),
                action=action,
                rationale=str(item.get("rationale") or ""),
                confidence=float(item.get("confidence") or 0.5),
                deliverable=str(item.get("deliverable") or "ミッション報告"),
                source="local_llm",
            )
        )
    return parsed[:4] or None


def generate_ideas(problem: str, workspace: Path) -> list[Idea]:
    seed = heuristic_ideas(problem, workspace)
    overlay = _ideas_from_llm(problem, workspace, seed)
    ranked = overlay or seed
    return sorted(ranked, key=lambda idea: idea.confidence, reverse=True)


def criteria_for(kind: GoalKind) -> list[str]:
    if kind == GoalKind.REPAIR_TESTS:
        return ["pytest or unittest exits 0"]
    if kind == GoalKind.WRITE_FILE:
        return ["Requested file exists with the requested text"]
    if kind == GoalKind.DIAGNOSE:
        return ["A diagnosis report with a likely cause is written"]
    if kind == GoalKind.PROPOSE:
        return ["At least one idea is recorded", "A submission exists in .thinkkoma/outbox"]
    return ["A report is written", "Tests pass if the workspace has them"]


def adopt_idea(idea: Idea) -> Goal:
    return Goal(
        kind=idea.action,
        summary=idea.title,
        success_criteria=criteria_for(idea.action),
        confidence=idea.confidence,
        notes=[idea.rationale],
        ideas=[idea],
        execute_best_idea=False,
    )
