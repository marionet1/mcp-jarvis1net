from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RagConfig:
    rag_root: str
    backend: str
    qdrant_url: str
    qdrant_collection: str
    qdrant_api_key_env: str
    openrouter_base_url: str
    embed_model: str
    guidance_auto: bool


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "rag_config.json"


def _resolve_config_path() -> Path:
    override = os.getenv("MCP_RAG_CONFIG_PATH", "").strip()
    if override:
        return Path(override)
    return _default_config_path()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off"}:
            return False
    return default


@lru_cache(maxsize=1)
def get_rag_config() -> RagConfig:
    path = _resolve_config_path()
    data = _read_json(path)
    rag_root = str(data.get("rag_root", "/app/data/rag")).strip() or "/app/data/rag"
    backend = str(data.get("backend", "qdrant")).strip().lower() or "qdrant"
    qdrant_url = str(data.get("qdrant_url", "http://qdrant:6333")).strip() or "http://qdrant:6333"
    qdrant_collection = str(data.get("qdrant_collection", "jarvis1net_tool_docs")).strip() or "jarvis1net_tool_docs"
    qdrant_api_key_env = str(data.get("qdrant_api_key_env", "QDRANT_API_KEY")).strip() or "QDRANT_API_KEY"
    openrouter_base_url = str(data.get("openrouter_base_url", "https://openrouter.ai/api/v1")).strip() or "https://openrouter.ai/api/v1"
    embed_model = str(data.get("embed_model", "text-embedding-3-small")).strip() or "text-embedding-3-small"
    guidance_auto = _as_bool(data.get("guidance_auto", True), True)
    return RagConfig(
        rag_root=rag_root,
        backend=backend,
        qdrant_url=qdrant_url,
        qdrant_collection=qdrant_collection,
        qdrant_api_key_env=qdrant_api_key_env,
        openrouter_base_url=openrouter_base_url,
        embed_model=embed_model,
        guidance_auto=guidance_auto,
    )
