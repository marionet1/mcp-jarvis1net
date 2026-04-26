from __future__ import annotations

import os
import re
import subprocess
import time

_SAFE_HOST = re.compile(r"^[A-Za-z0-9.\-:]{1,255}$")


def shell_timeout_sec() -> int:
    raw = (os.getenv("MCP_SHELL_TIMEOUT_SEC") or "8").strip()
    try:
        num = int(raw)
    except ValueError:
        num = 8
    return max(1, min(num, 30))


def command_for(action: str, host: str | None, count: int) -> list[str]:
    is_win = os.name == "nt"
    if action == "disk_usage":
        if is_win:
            return [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-PSDrive -PSProvider FileSystem | ForEach-Object { $_.Name + ' ' + [math]::Round($_.Used/1GB,2) + ' GB used / ' + [math]::Round($_.Free/1GB,2) + ' GB free' }",
            ]
        return ["df", "-h"]
    if action == "memory_usage":
        if is_win:
            return [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_OperatingSystem | ForEach-Object { 'Total: ' + [math]::Round($_.TotalVisibleMemorySize/1MB,2) + ' MB, Free: ' + [math]::Round($_.FreePhysicalMemory/1MB,2) + ' MB' }",
            ]
        return ["free", "-h"]
    if action == "cpu_load":
        if is_win:
            return [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Counter '\\Processor(_Total)\\% Processor Time' -ErrorAction SilentlyContinue | ForEach-Object { $_.CounterSamples[0].CookedValue } ; if(-not $?) { 'wmic cpu get loadpercentage' }",
            ]
        return ["cat", "/proc/loadavg"]
    if action == "uptime":
        if is_win:
            return [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | ForEach-Object { 'Uptime: ' + $_.Days + 'd ' + $_.Hours + 'h ' + $_.Minutes + 'm' }",
            ]
        return ["uptime"]
    if action == "ping":
        safe_host = (host or "").strip()
        if not safe_host:
            raise ValueError("host is required for action=ping.")
        if not _SAFE_HOST.match(safe_host):
            raise ValueError("host contains unsupported characters.")
        return ["ping", "-n" if is_win else "-c", str(count), safe_host]
    raise ValueError(f"Unsupported action: {action}")


def shell_run_diagnostic(action: str, host: str | None = None, count: int | None = None) -> dict[str, object]:
    ping_count = 2 if count is None else max(1, min(4, int(count)))
    command = command_for(action, host, ping_count)
    timeout = shell_timeout_sec()
    start = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        stdout = (result.stdout or "")[:12000]
        stderr = (result.stderr or "")[:12000]
        return {
            "ok": result.returncode == 0,
            "action": action,
            "command": command,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timeout_sec": timeout,
            "elapsed_ms": int((time.time() - start) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "action": action,
            "command": command,
            "exit_code": 124,
            "stdout": (exc.stdout or "")[:12000],
            "stderr": (exc.stderr or "Timed out")[:12000],
            "timeout_sec": timeout,
            "elapsed_ms": int((time.time() - start) * 1000),
        }

