import codecs
import errno
import os

from fastapi import APIRouter, Depends, HTTPException, Query

from src.deps import require_scope
from src.tools.common.paths import (
    max_read_bytes,
    max_write_bytes,
    resolve_directory,
    resolve_path,
)
from src.tools.filesystem.schemas import DeleteBody, MkdirBody, RenameBody, WriteBody

router = APIRouter(
    prefix="/v1/tools/filesystem",
    tags=["filesystem"],
    dependencies=[Depends(require_scope("filesystem"))],
)


@router.get(
    "/list",
    summary="List files and directories",
    description=(
        "Returns entry names and types for a directory. "
        "Use first when structure is unknown or when searching by filename."
    ),
)
def list_directory(
    path: str = Query(default=".", description="Directory to list."),
) -> dict:
    target = resolve_directory(path)
    entries: list[dict] = []
    for p in target.iterdir():
        entries.append({"name": p.name, "is_dir": p.is_dir()})
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    items = [e["name"] for e in entries]
    return {"path": str(target), "items": items, "entries": entries}


@router.get(
    "/stat",
    summary="Path metadata",
    description="Checks whether a path exists and returns file/dir info, size, and modification time.",
)
def stat_path(
    path: str = Query(..., description="Any path inside allowed roots."),
) -> dict:
    p = resolve_path(path)
    if not p.exists():
        return {"path": str(p), "exists": False}
    try:
        st = p.stat()
    except OSError as exc:
        return {"path": str(p), "exists": False, "error": str(exc)}
    return {
        "path": str(p),
        "exists": True,
        "is_file": p.is_file(),
        "is_dir": p.is_dir(),
        "size": st.st_size,
        "mtime": st.st_mtime,
    }


@router.get(
    "/read",
    summary="Read text file",
    description=(
        "Reads a file as text (UTF-8 with replacement for invalid bytes). "
        "Binary files may produce distorted output. "
        "Use max_bytes to cap read size."
    ),
)
def read_file(
    path: str = Query(..., description="Path to file."),
    max_bytes: int | None = Query(
        default=None,
        description="Byte limit (defaults to MCP_MAX_READ_BYTES).",
    ),
) -> dict:
    p = resolve_path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File does not exist or is not a regular file.")
    cap = max_read_bytes() if max_bytes is None else max(1, min(max_bytes, max_read_bytes()))
    with p.open("rb") as fh:
        data = fh.read(cap)
    truncated = len(data) >= cap and p.stat().st_size > cap
    text = data.decode("utf-8", errors="replace")
    return {
        "path": str(p),
        "content": text,
        "truncated": truncated,
        "read_bytes": len(data),
        "total_size": p.stat().st_size,
    }


@router.post(
    "/write",
    summary="Write/overwrite text file",
    description=(
        "Creates or overwrites file content. Use for config updates, script generation, and text edits. "
        "For very large payloads, split writes into smaller chunks."
    ),
)
def write_file(body: WriteBody) -> dict:
    try:
        codecs.lookup(body.encoding)
    except LookupError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown encoding: {body.encoding}") from exc

    target = resolve_path(body.path)
    if target.exists() and target.is_dir():
        raise HTTPException(status_code=400, detail="Path is a directory; pick a file path.")

    if body.create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        if not target.parent.exists():
            raise HTTPException(
                status_code=404,
                detail="Parent directory does not exist. Use create_parents=true.",
            )

    raw = body.content.encode(body.encoding, errors="strict")
    if len(raw) > max_write_bytes():
        raise HTTPException(
            status_code=400,
            detail=f"Content exceeds max write size ({max_write_bytes()} bytes).",
        )

    target.write_bytes(raw)
    return {"path": str(target), "written_bytes": len(raw), "ok": True}


@router.post(
    "/mkdir",
    summary="Create directory",
    description="Creates one directory or a directory tree (parents=true) within allowed roots.",
)
def mkdir(body: MkdirBody) -> dict:
    target = resolve_path(body.path)
    if target.exists():
        if target.is_dir():
            return {"path": str(target), "ok": True, "already_existed": True}
        raise HTTPException(status_code=400, detail="Path exists and is a file.")
    try:
        if body.parents:
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.mkdir(parents=False)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            return {"path": str(target), "ok": True, "already_existed": True}
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": str(target), "ok": True, "already_existed": False}


@router.post(
    "/delete",
    summary="Delete file or empty directory",
    description="Deletes a single file or an empty directory. Does not delete non-empty directory trees.",
)
def delete_path(body: DeleteBody) -> dict:
    target = resolve_path(body.path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist.")
    if target.is_file() or target.is_symlink():
        target.unlink(missing_ok=False)
        return {"path": str(target), "ok": True, "removed": "file"}
    if target.is_dir():
        try:
            target.rmdir()
        except OSError as exc:
            raise HTTPException(
                status_code=400,
                detail="Directory is not empty or cannot be removed. Remove files inside first or use delete on files.",
            ) from exc
        return {"path": str(target), "ok": True, "removed": "empty_dir"}
    raise HTTPException(status_code=400, detail="Unsupported path type.")


@router.post(
    "/rename",
    summary="Rename / move path",
    description="Renames or moves a file or directory within allowed paths (source must exist).",
)
def rename_path(body: RenameBody) -> dict:
    src = resolve_path(body.from_path)
    dst = resolve_path(body.to_path)
    if not src.exists():
        raise HTTPException(status_code=404, detail="from_path does not exist.")
    if dst.exists():
        raise HTTPException(status_code=400, detail="to_path already exists.")
    if not dst.parent.exists():
        raise HTTPException(status_code=404, detail="Destination parent directory does not exist.")
    os.replace(src, dst)
    return {"from": str(src), "to": str(dst), "ok": True}
