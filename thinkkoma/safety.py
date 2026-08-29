from __future__ import annotations

import re
from pathlib import Path

SECRET_PATH_RE = re.compile(
    r"(^|/|\\)(\.env|\.netrc|\.pypirc|id_rsa|id_ed25519|credentials|\.ssh)(/|\\|$|\.)",
    re.IGNORECASE,
)

_DENIED_PATTERNS = (
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\s+[/~]", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r"\bshutdown\b|\breboot\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{"),
    re.compile(r"\bchmod\s+777\b", re.IGNORECASE),
    re.compile(r"curl\s+[^\n]*\|\s*(sh|bash)", re.IGNORECASE),
    re.compile(r"wget\s+[^\n]*\|\s*(sh|bash)", re.IGNORECASE),
    re.compile(r"\bgit\s+push\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\b", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\b", re.IGNORECASE),
    re.compile(r"\bgit\s+checkout\b", re.IGNORECASE),
    re.compile(r"\bgit\s+commit\b", re.IGNORECASE),
    re.compile(r"\bosascript\b", re.IGNORECASE),
    re.compile(r"\blaunchctl\b", re.IGNORECASE),
)

_ALLOWED_BINARIES = {
    "python",
    "python3",
    "pytest",
    "uv",
    "ls",
    "cat",
    "head",
    "tail",
    "rg",
    "grep",
    "find",
    "git",
    "wc",
    "diff",
    "sed",
    "awk",
    "true",
}

_ALLOWED_GIT_SUBCOMMANDS = {"status", "diff", "log", "show", "rev-parse", "ls-files"}


class SafetyError(ValueError):
    """Raised when an action would leave the workspace sandbox."""


def resolve_workspace(workspace: Path) -> Path:
    resolved = workspace.expanduser().resolve()
    if not resolved.exists():
        raise SafetyError(f"Workspace does not exist: {resolved}")
    if not resolved.is_dir():
        raise SafetyError(f"Workspace is not a directory: {resolved}")
    return resolved


def ensure_inside(workspace: Path, target: Path) -> Path:
    root = resolve_workspace(workspace)
    resolved = target.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SafetyError(f"Path escapes workspace: {resolved}") from exc
    if SECRET_PATH_RE.search(str(resolved)):
        raise SafetyError(f"Refusing to touch credential path: {resolved}")
    return resolved


def deny_secret_read(path: Path) -> None:
    if SECRET_PATH_RE.search(str(path)):
        raise SafetyError(f"Refusing to read credential path: {path}")


def split_command(command: str) -> list[str]:
    import shlex

    try:
        return shlex.split(command)
    except ValueError as exc:
        raise SafetyError(f"Could not parse command: {command}") from exc


def check_command(command: str) -> list[str]:
    stripped = command.strip()
    if not stripped:
        raise SafetyError("Empty command")
    if any(pattern.search(stripped) for pattern in _DENIED_PATTERNS):
        raise SafetyError(f"Denied command: {stripped}")
    if any(token in stripped for token in ("&&", ";", "|", "`", "$(", "\n")):
        raise SafetyError("Compound or interpolated shell commands are not allowed")
    argv = split_command(stripped)
    binary = Path(argv[0]).name
    stem = binary.split(".")[0]
    allowed = binary in _ALLOWED_BINARIES or stem in _ALLOWED_BINARIES or stem.startswith("python")
    if not allowed:
        raise SafetyError(f"Binary is not on the allowlist: {binary}")
    if stem == "git":
        if len(argv) < 2 or argv[1] not in _ALLOWED_GIT_SUBCOMMANDS:
            raise SafetyError("Only read-only git subcommands are allowed")
    return argv
