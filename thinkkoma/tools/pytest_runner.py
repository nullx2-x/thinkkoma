from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from thinkkoma.tools.shell import run_command


@dataclass
class TestRun:
    passed: bool
    output: str
    command: str


def run_tests(workspace: Path, *, timeout: float = 30.0) -> TestRun:
    commands = (
        f"{sys.executable} -m pytest -q",
        f"{sys.executable} -m unittest discover -q",
    )
    last = TestRun(passed=False, output="No test runner produced output", command=commands[0])
    for command in commands:
        result = run_command(workspace, command, timeout=timeout)
        output = (result.stdout or "") + (result.stderr or "")
        last = TestRun(passed=result.returncode == 0, output=output, command=command)
        if "No module named pytest" in output:
            continue
        if "no tests ran" in output.lower() and "unittest" not in command:
            continue
        return last
    return last
