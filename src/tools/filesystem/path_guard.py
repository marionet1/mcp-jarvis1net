from __future__ import annotations

from pathlib import Path

from tools.config import load_tools_config

def allowed_roots() -> list[str]:
    return load_tools_config().allowed_roots


def max_read_bytes() -> int:
    return load_tools_config().max_read_bytes


def max_write_bytes() -> int:
    return load_tools_config().max_write_bytes


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
        raise PathError("Path is outside allowed roots (set src/tools/tools_config.json).", "out_of_root")
    return resolved


def resolve_directory(path_str: str) -> str:
    target = resolve_path(path_str)
    p = Path(target)
    if not p.exists() or not p.is_dir():
        raise PathError("Directory does not exist.", "not_found")
    return target
