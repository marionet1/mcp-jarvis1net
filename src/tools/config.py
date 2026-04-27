from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolsConfig:
    allowed_roots: list[str]
    max_read_bytes: int
    max_write_bytes: int
    shell_timeout_sec: int


def _config_path() -> Path:
    return Path(__file__).resolve().parent / "tools_config.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def load_tools_config() -> ToolsConfig:
    data = _read_json(_config_path())
    roots_raw = data.get("allowed_roots", [str(Path.home())])
    roots: list[str] = []
    if isinstance(roots_raw, list):
        roots = [str(Path(str(item)).resolve()) for item in roots_raw if str(item).strip()]
    if not roots:
        roots = [str(Path.home().resolve())]

    max_read_raw = data.get("max_read_bytes", 1048576)
    max_write_raw = data.get("max_write_bytes", 2097152)
    timeout_raw = data.get("shell_timeout_sec", 8)
    try:
        max_read = max(1024, min(int(max_read_raw), 16 * 1024 * 1024))
    except Exception:
        max_read = 1048576
    try:
        max_write = max(1024, min(int(max_write_raw), 8 * 1024 * 1024))
    except Exception:
        max_write = 2097152
    try:
        timeout = max(1, min(int(timeout_raw), 30))
    except Exception:
        timeout = 8

    return ToolsConfig(
        allowed_roots=roots,
        max_read_bytes=max_read,
        max_write_bytes=max_write,
        shell_timeout_sec=timeout,
    )
