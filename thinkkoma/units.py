from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    name: str
    role: str
    mandate: str


UNITS = (
    Unit("0号", "scout", "人間の指示を待たず、作業場のテスト・ログ・構文から欠陥信号を見つける"),
    Unit("1号", "interpreter", "問題文と作業場を見て、人が聞かなくても成功条件まで落とす"),
    Unit("2号", "planner", "検証可能な最短手順に分解する。推測で止めない"),
    Unit("3号", "operator", "サンドボックス内だけで実行し、危険な操作は拒否する"),
    Unit("4号", "critic", "人に確認せず、成功条件と証跡だけで完了判定する"),
    Unit("5号", "archivist", "失敗と成功を記憶し、次の解釈に再利用する"),
    Unit("6号", "affirmer", "加点だけで見る。テスト合否を偽って上げない"),
    Unit("7号", "negator", "減点だけで見る。規定違反と未検証の完了を拒否する"),
)


def describe_units() -> list[dict[str, str]]:
    return [{"name": unit.name, "role": unit.role, "mandate": unit.mandate} for unit in UNITS]
