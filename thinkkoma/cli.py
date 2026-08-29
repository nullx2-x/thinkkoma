from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from thinkkoma import __version__
from thinkkoma.daemon import run_daemon
from thinkkoma.drive import PatrolReport, run_patrol
from thinkkoma.loop import run_mission
from thinkkoma.models import Budget
from thinkkoma.units import describe_units


def _print_report(report, as_json: bool) -> None:
    if as_json:
        json.dump(report.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    status = "SOLVED" if report.solved else "UNSOLVED"
    sys.stdout.write(f"{status}: {report.summary}\n")
    if report.stop_reason is not None:
        sys.stdout.write(f"stop: {report.stop_reason.value}\n")
    sys.stdout.write(f"goal: {report.goal.kind.value} ({report.goal.confidence:.2f})\n")
    for step in report.steps:
        first_line = (step.output.splitlines() or [""])[0]
        sys.stdout.write(f"- {step.step.kind.value}: {step.status.value} {first_line}\n")
    if report.report_path:
        sys.stdout.write(f"report: {report.report_path}\n")
    if report.submission_path:
        sys.stdout.write(f"submission: {report.submission_path}\n")
    card = getattr(report, "scorecard", None)
    if card is not None:
        sys.stdout.write(
            f"score: spec_ok={card.spec_ok} retry={card.retry_stage} "
            f"reenacted={card.reenacted} rounds={card.reenact_rounds} "
            f"disagreement={card.disagreement} "
            f"affirmer_passed={card.affirmer_passed} negator_passed={card.negator_passed}\n"
        )
        for view in card.viewpoints:
            sys.stdout.write(
                f"  {view.name}: +{view.plus:.2f} -{view.minus:.2f} "
                f"net={view.net:.2f} residual={view.residual:.2f}\n"
            )


def _print_patrol(report: PatrolReport, as_json: bool) -> None:
    if as_json:
        json.dump(report.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    status = "QUIET" if report.quiet else "PATROL"
    sys.stdout.write(f"{status}: stop={report.stop_reason.value} missions={len(report.missions)}\n")
    for mission in report.missions:
        mark = "solved" if mission.solved else "unsolved"
        sys.stdout.write(f"- {mark}: {mission.summary}\n")
    if report.status_path:
        sys.stdout.write(f"status: {report.status_path}\n")


def _apply_runtime_flags(args) -> None:
    backend = getattr(args, "backend", None)
    if backend:
        os.environ["THINKKOMA_BACKEND"] = backend


def _budget_from(args) -> Budget:
    return Budget(
        max_attempts=getattr(args, "max_attempts", 6),
        max_steps=getattr(args, "max_steps", 16),
        max_seconds=getattr(args, "max_seconds", 120.0),
    )


def _exit_patrol(report: PatrolReport) -> int:
    return 0 if report.quiet or all(item.solved for item in report.missions) else 2


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--backend", choices=["heuristic", "ollama", "local", "openai", "cursor"])
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="thinkkoma",
        description="Fully autonomous think-tank. Finds defects and closes them without a human prompt.",
    )
    parser.add_argument("--version", action="version", version=f"thinkkoma {__version__}")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Solve one stated problem, or patrol if none is given")
    run_p.add_argument("problem", nargs="?", help="Problem text. Omit to patrol. Use - to read stdin.")
    _add_common(run_p)

    drive_p = sub.add_parser("drive", help="Patrol a workspace with no human instruction")
    _add_common(drive_p)
    drive_p.add_argument("--inbox", type=Path)
    drive_p.add_argument(
        "--watch",
        action="store_true",
        help="Keep rescanning after quiet. Default is patrol until quiet, then exit.",
    )
    drive_p.add_argument("--interval", type=float, default=5.0)
    drive_p.add_argument("--max-missions", type=int, default=12)
    drive_p.add_argument("--max-idle", type=int, default=3)

    daemon_p = sub.add_parser("daemon", help="Watch an inbox; empty inbox still patrols the workspace")
    daemon_p.add_argument("--inbox", type=Path, default=Path.home() / ".thinkkoma" / "inbox")
    _add_common(daemon_p)
    daemon_p.add_argument("--once", action="store_true")
    daemon_p.add_argument("--interval", type=float, default=2.0)

    sub.add_parser("units", help="List think-tank units")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "units":
        json.dump(describe_units(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    _apply_runtime_flags(args)

    if args.command == "drive":
        patrol = run_patrol(
            args.workspace,
            inbox=args.inbox,
            once=not args.watch,
            interval=args.interval,
            max_missions=args.max_missions,
            max_idle=args.max_idle,
            budget=_budget_from(args),
        )
        _print_patrol(patrol, args.json)
        return _exit_patrol(patrol)

    if args.command == "run" and args.problem is None:
        patrol = run_patrol(args.workspace, once=True, budget=_budget_from(args))
        _print_patrol(patrol, args.json)
        return _exit_patrol(patrol)

    if args.command == "run":
        problem = sys.stdin.read() if args.problem == "-" else args.problem
        if not problem.strip():
            patrol = run_patrol(args.workspace, once=True, budget=_budget_from(args))
            _print_patrol(patrol, args.json)
            return _exit_patrol(patrol)
        report = run_mission(problem, args.workspace, budget=_budget_from(args))
        _print_report(report, args.json)
        return 0 if report.solved else 2

    reports = run_daemon(
        args.inbox,
        default_workspace=args.workspace,
        once=args.once,
        interval=args.interval,
        budget=_budget_from(args),
    )
    if args.once and not reports:
        patrol = run_patrol(args.workspace, inbox=args.inbox, once=True, budget=_budget_from(args))
        _print_patrol(patrol, args.json)
        return _exit_patrol(patrol)
    if args.json:
        json.dump([item.to_dict() for item in reports], sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"processed {len(reports)} inbox item(s)\n")
        for report in reports:
            _print_report(report, False)
    return 0 if all(item.solved for item in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
