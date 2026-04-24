from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.deps import require_scope

ActionType = Literal["disk_usage", "memory_usage", "cpu_load", "uptime", "ping"]
_SAFE_HOST_RE = re.compile(r"^[A-Za-z0-9.\-:]{1,255}$")

router = APIRouter(
    prefix="/v1/tools/shell",
    tags=["shell"],
    dependencies=[Depends(require_scope("shell"))],
)


class ShellRunBody(BaseModel):
    action: ActionType = Field(..., description="Diagnostic action to execute.")
    host: str | None = Field(
        default=None,
        description="Target host for action=ping (domain or IP).",
    )
    count: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Ping packet count (used only for action=ping).",
    )


def _shell_timeout_sec() -> int:
    raw = os.getenv("MCP_SHELL_TIMEOUT_SEC", "8").strip()
    try:
        return max(1, min(int(raw), 30))
    except ValueError:
        return 8


def _command_for(body: ShellRunBody) -> list[str]:
    if body.action == "disk_usage":
        return ["df", "-h"]
    if body.action == "memory_usage":
        return ["free", "-h"]
    if body.action == "cpu_load":
        return ["cat", "/proc/loadavg"]
    if body.action == "uptime":
        return ["uptime"]
    if body.action == "ping":
        if not body.host:
            raise HTTPException(status_code=400, detail="host is required for action=ping.")
        host = body.host.strip()
        if not _SAFE_HOST_RE.match(host):
            raise HTTPException(status_code=400, detail="host contains unsupported characters.")
        return ["ping", "-c", str(body.count), host]
    raise HTTPException(status_code=400, detail=f"Unsupported action: {body.action}")


@router.post(
    "/run",
    summary="Run safe shell diagnostics",
    description=(
        "Executes a restricted set of diagnostic commands (disk/memory/load/uptime/ping). "
        "Arbitrary shell execution is intentionally blocked."
    ),
)
def run_shell(body: ShellRunBody) -> dict:
    command = _command_for(body)
    timeout_sec = _shell_timeout_sec()
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=408,
            detail=f"Command timed out after {timeout_sec}s: {' '.join(command)}",
        ) from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    max_output = 12000
    stdout = (proc.stdout or "")[:max_output]
    stderr = (proc.stderr or "")[:max_output]

    return {
        "ok": proc.returncode == 0,
        "action": body.action,
        "command": command,
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timeout_sec": timeout_sec,
        "elapsed_ms": elapsed_ms,
    }

