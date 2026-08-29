from __future__ import annotations

from pathlib import Path

from thinkkoma.safety import ensure_inside, resolve_workspace

_SKIP_DIRS = {".git", ".hg", ".thinkkoma", "__pycache__", ".venv", "node_modules", ".pytest_cache"}
_TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".cfg", ".ini"}


def inventory(workspace: Path, *, limit: int = 80) -> list[str]:
    root = resolve_workspace(workspace)
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES and path.name not in {"Makefile", "Dockerfile"}:
            continue
        found.append(str(path.relative_to(root)))
        if len(found) >= limit:
            break
    return found


def read_text(workspace: Path, relative: str, *, max_bytes: int = 200_000) -> str:
    path = ensure_inside(workspace, resolve_workspace(workspace) / relative)
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError(f"File too large to read: {relative}")
    return data.decode("utf-8")


def write_text(workspace: Path, relative: str, content: str) -> Path:
    path = ensure_inside(workspace, resolve_workspace(workspace) / relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    cache = path.parent / "__pycache__"
    if cache.is_dir():
        for item in cache.glob(f"{path.stem}.*"):
            item.unlink(missing_ok=True)
    return path
