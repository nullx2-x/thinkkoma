from __future__ import annotations

import os
import subprocess
from pathlib import Path

from thinkkoma.safety import SafetyError, check_command, resolve_workspace


def run_command(workspace: Path, command: str, *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    argv = check_command(command)
    root = resolve_workspace(workspace)
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    try:
        return subprocess.run(
            argv,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise SafetyError(f"Command timed out: {command}") from exc
