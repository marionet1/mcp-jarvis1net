from __future__ import annotations

import os
from pathlib import Path


def allowed_roots() -> list[str]:
    from_env = (os.getenv("MCP_ALLOWED_ROOTS") or "").strip()
    if from_env:
        roots = [str(Path(item.strip()).resolve()) for item in from_env.split(",") if item.strip()]
        return roots
    return [str((Path.home() / "jump").resolve())]


def max_read_bytes() -> int:
    raw = (os.getenv("MCP_MAX_READ_BYTES") or "1048576").strip()
    try:
        num = int(raw)
    except ValueError:
        num = 1048576
    return max(1024, min(num, 16 * 1024 * 1024))


def max_write_bytes() -> int:
    raw = (os.getenv("MCP_MAX_WRITE_BYTES") or "2097152").strip()
    try:
        num = int(raw)
    except ValueError:
        num = 2097152
    return max(1024, min(num, 8 * 1024 * 1024))


def is_under_allowed_root(target: str, roots: list[str] | None = None) -> bool:
    root_list = roots if roots is not None else allowed_roots()
    try:
        resolved = Path(target).resolve()
    except OSError:
        return False
    for root in root_list:
        root_path = Path(root).resolve()
        if resolved == root_path:
            return True
        try:
            resolved.relative_to(root_path)
            return True
        except ValueError:
            continue
    return False


class PathError(Exception):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_path(path_str: str) -> str:
    expanded = str(Path(path_str).expanduser())
    target = Path(expanded)
    if not target.is_absolute():
        target = Path.cwd() / target
    resolved = str(target.resolve())
    if not is_under_allowed_root(resolved):
        raise PathError("Path is outside allowed roots (set MCP_ALLOWED_ROOTS).", "out_of_root")
    return resolved


def resolve_directory(path_str: str) -> str:
    target = resolve_path(path_str)
    p = Path(target)
    if not p.exists() or not p.is_dir():
        raise PathError("Directory does not exist.", "not_found")
    return target

