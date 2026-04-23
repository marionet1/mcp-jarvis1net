import os
from pathlib import Path

from fastapi import HTTPException


def allowed_roots() -> list[Path]:
    raw = os.getenv("MCP_ALLOWED_ROOTS", "/home/jump")
    return [Path(p.strip()).resolve() for p in raw.split(",") if p.strip()]


def max_read_bytes() -> int:
    raw = os.getenv("MCP_MAX_READ_BYTES", "1048576").strip()
    try:
        return max(1024, min(int(raw), 16 * 1024 * 1024))
    except ValueError:
        return 1048576


def max_write_bytes() -> int:
    raw = os.getenv("MCP_MAX_WRITE_BYTES", "2097152").strip()
    try:
        return max(1024, min(int(raw), 8 * 1024 * 1024))
    except ValueError:
        return 2097152


def is_under_allowed_root(target: Path, roots: list[Path] | None = None) -> bool:
    roots = roots or allowed_roots()
    try:
        target_resolved = target.resolve()
    except OSError:
        return False
    return any(target_resolved == root or root in target_resolved.parents for root in roots)


def resolve_path(path: str) -> Path:
    """Resolves an absolute path inside allowed roots (path may not exist yet)."""
    target = Path(path).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    try:
        resolved = target.resolve(strict=False)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid path: {exc}") from exc
    if not is_under_allowed_root(resolved):
        raise HTTPException(status_code=403, detail="Path is outside allowed roots.")
    return resolved


def resolve_directory(path: str) -> Path:
    target = resolve_path(path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory does not exist.")
    return target
