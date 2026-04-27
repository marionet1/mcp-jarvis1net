from __future__ import annotations

from pathlib import Path

from tools.filesystem.path_guard import PathError, max_read_bytes, max_write_bytes, resolve_directory, resolve_path


def fs_list_directory(path: str) -> dict[str, object]:
    target = resolve_directory(path)
    entries = [{"name": item.name, "is_dir": item.is_dir()} for item in Path(target).iterdir()]
    entries.sort(key=lambda item: (not bool(item["is_dir"]), str(item["name"]).lower()))
    return {"path": target, "items": [entry["name"] for entry in entries], "entries": entries}


def fs_stat_path(path: str) -> dict[str, object]:
    resolved = resolve_path(path)
    p = Path(resolved)
    if not p.exists():
        return {"path": resolved, "exists": False}
    try:
        st = p.stat()
    except OSError as exc:
        return {"path": resolved, "exists": False, "error": str(exc)}
    return {
        "path": resolved,
        "exists": True,
        "is_file": p.is_file(),
        "is_dir": p.is_dir(),
        "size": st.st_size,
        "mtime": float(st.st_mtime),
    }


def fs_read_file(path: str, max_bytes: int | None = None) -> dict[str, object]:
    resolved = resolve_path(path)
    p = Path(resolved)
    if not p.exists() or not p.is_file():
        raise PathError("File does not exist or is not a regular file.", "not_found")
    cap = max_read_bytes() if max_bytes is None else max(1, min(int(max_bytes), max_read_bytes()))
    with p.open("rb") as handle:
        data = handle.read(cap)
    total = p.stat().st_size
    return {
        "path": resolved,
        "content": data.decode("utf-8", errors="replace"),
        "truncated": len(data) >= cap and total > cap,
        "read_bytes": len(data),
        "total_size": total,
    }


def fs_write_file(path: str, content: str, encoding: str = "utf-8", create_parents: bool = False) -> dict[str, object]:
    resolved = resolve_path(path)
    target = Path(resolved)
    if target.exists() and target.is_dir():
        raise PathError("Path is a directory; pick a file path.", "bad_request")
    try:
        raw = content.encode(encoding)
    except LookupError as exc:
        raise PathError(f"Unknown encoding: {encoding}", "invalid") from exc
    if len(raw) > max_write_bytes():
        raise PathError(f"Content exceeds max write size ({max_write_bytes()} bytes).", "bad_request")
    if create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)
    elif not target.parent.exists():
        raise PathError("Parent directory does not exist. Use create_parents=true.", "not_found")
    target.write_bytes(raw)
    return {"path": resolved, "written_bytes": len(raw), "ok": True}


def fs_mkdir(path: str, parents: bool = False) -> dict[str, object]:
    resolved = resolve_path(path)
    target = Path(resolved)
    if target.exists():
        if target.is_dir():
            return {"path": resolved, "ok": True, "already_existed": True}
        raise PathError("Path exists and is a file.", "bad_request")
    target.mkdir(parents=parents, exist_ok=False)
    return {"path": resolved, "ok": True, "already_existed": False}


def fs_delete_path(path: str) -> dict[str, object]:
    resolved = resolve_path(path)
    target = Path(resolved)
    if not target.exists():
        raise PathError("Path does not exist.", "not_found")
    if target.is_file() or target.is_symlink():
        target.unlink()
        return {"path": resolved, "ok": True, "removed": "file"}
    if target.is_dir():
        try:
            target.rmdir()
        except OSError as exc:
            raise PathError("Directory is not empty or cannot be removed. Remove files inside first.", "bad_request") from exc
        return {"path": resolved, "ok": True, "removed": "empty_dir"}
    raise PathError("Unsupported path type.", "bad_request")


def fs_rename_path(from_path: str, to_path: str) -> dict[str, object]:
    src = Path(resolve_path(from_path))
    dst = Path(resolve_path(to_path))
    if not src.exists():
        raise PathError("from_path does not exist.", "not_found")
    if dst.exists():
        raise PathError("to_path already exists.", "bad_request")
    if not dst.parent.exists():
        raise PathError("Destination parent directory does not exist.", "not_found")
    src.rename(dst)
    return {"from": str(src), "to": str(dst), "ok": True}
