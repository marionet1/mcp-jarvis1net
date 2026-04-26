from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag_config import get_rag_config
from rag_vector_store import RagChunk, RagVectorStore

DOC_SCHEMA_VERSION = "1.0"
ALLOWED_DOC_TYPES = {"overview", "howto", "reference", "errors", "limits", "examples", "runbook", "security"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rag_root() -> Path:
    configured = get_rag_config().rag_root.strip()
    if configured:
        return Path(configured)
    docker_default = Path("/app/data/rag")
    if docker_default.parent.exists():
        return docker_default
    return Path.cwd() / ".rag-data"


def _docs_path() -> Path:
    return _rag_root() / "documents.json"


def _catalog_path() -> Path:
    return _rag_root() / "tool_catalog.json"


def _telemetry_path() -> Path:
    return _rag_root() / "telemetry.jsonl"


def _ensure_storage() -> None:
    _rag_root().mkdir(parents=True, exist_ok=True)
    if not _docs_path().exists():
        _docs_path().write_text("[]", encoding="utf-8")
    if not _catalog_path().exists():
        _catalog_path().write_text("[]", encoding="utf-8")
    if not _telemetry_path().exists():
        _telemetry_path().write_text("", encoding="utf-8")


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_telemetry(event: dict[str, Any]) -> None:
    row = dict(event)
    row["timestamp"] = _utc_now_iso()
    with _telemetry_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _family_from_tool(tool_name: str) -> str:
    if tool_name.startswith("microsoft_"):
        return "microsoft"
    if tool_name.startswith("fs_"):
        return "filesystem"
    if tool_name.startswith("shell_"):
        return "shell"
    return "other"


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]
    rows = []
    i = 0
    while i < len(cleaned):
        rows.append(cleaned[i : i + chunk_size])
        i += max(1, chunk_size - overlap)
    return rows


def _validate_doc_type(doc_type: str) -> str:
    normalized = (doc_type or "reference").strip().lower()
    if normalized in ALLOWED_DOC_TYPES:
        return normalized
    return "reference"


def _build_doc_row(
    doc_id: str,
    title: str,
    content: str,
    tool_family: str,
    tool_name: str,
    provider: str,
    doc_type: str,
    source_url: str,
    version: str,
    tags: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": DOC_SCHEMA_VERSION,
        "doc_id": doc_id,
        "title": title,
        "content": content,
        "tool_family": tool_family,
        "tool_name": tool_name,
        "provider": provider,
        "doc_type": _validate_doc_type(doc_type),
        "source_url": source_url,
        "version": version,
        "tags": tags,
        "updated_at": _utc_now_iso(),
    }


def rag_refresh_tool_catalog(mcp_tool_list: list[dict[str, object]]) -> dict[str, object]:
    _ensure_storage()
    rows: list[dict[str, object]] = []
    for tool in sorted(mcp_tool_list, key=lambda x: str(x.get("name", ""))):
        name = str(tool.get("name", "")).strip()
        if not name:
            continue
        rows.append(
            {
                "schema_version": DOC_SCHEMA_VERSION,
                "tool_name": name,
                "tool_family": _family_from_tool(name),
                "description": str(tool.get("description", "")),
                "updated_at": _utc_now_iso(),
            }
        )
    _write_json(_catalog_path(), rows)
    return {"ok": True, "count": len(rows), "path": str(_catalog_path()), "schema_version": DOC_SCHEMA_VERSION}


def rag_list_tool_catalog(tool_family: str | None = None) -> dict[str, object]:
    _ensure_storage()
    rows = _read_json(_catalog_path(), [])
    if tool_family:
        rows = [r for r in rows if str(r.get("tool_family", "")) == tool_family]
    return {"ok": True, "count": len(rows), "tools": rows}


def rag_upsert_document(
    doc_id: str,
    title: str,
    content: str,
    tool_family: str,
    tool_name: str | None = None,
    provider: str = "microsoft",
    doc_type: str = "reference",
    source_url: str | None = None,
    version: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    _ensure_storage()
    doc_id = doc_id.strip()
    if not doc_id:
        return {"ok": False, "error": "doc_id is required"}
    if not title.strip():
        return {"ok": False, "error": "title is required"}
    if not content.strip():
        return {"ok": False, "error": "content is required"}
    if not tool_family.strip():
        return {"ok": False, "error": "tool_family is required"}

    docs = _read_json(_docs_path(), [])
    row = _build_doc_row(
        doc_id=doc_id,
        title=title.strip(),
        content=content.strip(),
        tool_family=tool_family.strip().lower(),
        tool_name=(tool_name or "").strip(),
        provider=(provider or "unknown").strip().lower(),
        doc_type=doc_type,
        source_url=(source_url or "").strip(),
        version=(version or "").strip(),
        tags=[str(t).strip().lower() for t in (tags or []) if str(t).strip()],
    )

    replaced = False
    for idx, existing in enumerate(docs):
        if str(existing.get("doc_id", "")) == doc_id:
            docs[idx] = row
            replaced = True
            break
    if not replaced:
        docs.append(row)
    _write_json(_docs_path(), docs)

    chunks = _chunk_text(row["content"])
    vector_chunks = [
        RagChunk(
            doc_id=doc_id,
            chunk_id=f"{doc_id}:{idx}",
            title=row["title"],
            content=chunk,
            metadata={
                "tool_family": row["tool_family"],
                "tool_name": row["tool_name"],
                "provider": row["provider"],
                "doc_type": row["doc_type"],
                "source_url": row["source_url"],
                "version": row["version"],
                "tags": ",".join(row["tags"]),
            },
        )
        for idx, chunk in enumerate(chunks)
    ]
    vector_store = RagVectorStore()
    vector_status = vector_store.upsert_chunks(vector_chunks)
    return {
        "ok": True,
        "updated": replaced,
        "doc_id": doc_id,
        "count": len(docs),
        "chunk_count": len(chunks),
        "vector_status": vector_status,
    }


def rag_delete_document(doc_id: str) -> dict[str, object]:
    _ensure_storage()
    docs = _read_json(_docs_path(), [])
    before = len(docs)
    docs = [d for d in docs if str(d.get("doc_id", "")) != doc_id]
    _write_json(_docs_path(), docs)
    # Vector deletion can be added later through id-based delete in Qdrant.
    return {"ok": True, "deleted": before - len(docs), "count": len(docs)}


def rag_list_documents(
    tool_family: str | None = None,
    tool_name: str | None = None,
    provider: str | None = None,
    doc_type: str | None = None,
    limit: int = 100,
) -> dict[str, object]:
    _ensure_storage()
    docs = _read_json(_docs_path(), [])
    if tool_family:
        docs = [d for d in docs if str(d.get("tool_family", "")) == tool_family]
    if tool_name:
        docs = [d for d in docs if str(d.get("tool_name", "")) == tool_name]
    if provider:
        docs = [d for d in docs if str(d.get("provider", "")) == provider]
    if doc_type:
        normalized = _validate_doc_type(doc_type)
        docs = [d for d in docs if str(d.get("doc_type", "")) == normalized]
    limit = max(1, min(limit, 500))
    docs = docs[:limit]
    return {"ok": True, "count": len(docs), "documents": docs}


def _score_document(query_tokens: list[str], doc: dict[str, object]) -> float:
    searchable = " ".join(
        [
            str(doc.get("title", "")),
            str(doc.get("content", "")),
            str(doc.get("tool_family", "")),
            str(doc.get("tool_name", "")),
            str(doc.get("doc_type", "")),
            " ".join([str(t) for t in doc.get("tags", [])]),
        ]
    )
    doc_tokens = _tokenize(searchable)
    if not doc_tokens:
        return 0.0
    doc_set = set(doc_tokens)
    overlap = sum(1 for token in query_tokens if token in doc_set)
    density = overlap / max(1, len(query_tokens))
    exact_boost = 0.25 if " ".join(query_tokens) in searchable.lower() else 0.0
    return density + exact_boost


def _lexical_search(
    query: str,
    docs: list[dict[str, Any]],
    top_k: int,
    min_score: float,
) -> list[dict[str, Any]]:
    tokens = _tokenize(query)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for doc in docs:
        score = _score_document(tokens, doc)
        if score >= min_score:
            ranked.append((score, doc))
    ranked.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for score, doc in ranked[:top_k]:
        content = str(doc.get("content", ""))
        hits.append(
            {
                "score": round(score, 4),
                "doc_id": doc.get("doc_id", ""),
                "tool_family": doc.get("tool_family", ""),
                "tool_name": doc.get("tool_name", ""),
                "title": doc.get("title", ""),
                "doc_type": doc.get("doc_type", ""),
                "source_url": doc.get("source_url", ""),
                "snippet": content[:600],
                "retrieval_mode": "lexical",
            }
        )
    return hits


def rag_search_tool_guidance(
    query: str,
    tool_family: str | None = None,
    tool_name: str | None = None,
    provider: str | None = None,
    top_k: int = 5,
    min_score: float = 0.2,
    doc_type: str | None = None,
) -> dict[str, object]:
    _ensure_storage()
    t0 = time.perf_counter()
    query = query.strip()
    if not query:
        return {"ok": False, "error": "query is required"}

    docs = _read_json(_docs_path(), [])
    if tool_family:
        docs = [d for d in docs if str(d.get("tool_family", "")) == tool_family]
    if tool_name:
        docs = [d for d in docs if str(d.get("tool_name", "")) == tool_name]
    if provider:
        docs = [d for d in docs if str(d.get("provider", "")) == provider]
    if doc_type:
        docs = [d for d in docs if str(d.get("doc_type", "")) == _validate_doc_type(doc_type)]

    top_k = max(1, min(top_k, 20))
    vector_store = RagVectorStore()
    vector_results: list[dict[str, Any]] = []
    vector_status = {"ok": True, "backend": vector_store.backend, "results": []}
    if docs:
        vector_status = vector_store.search(
            query=query,
            top_k=top_k,
            metadata_filters={
                "tool_family": (tool_family or ""),
                "tool_name": (tool_name or ""),
                "provider": (provider or ""),
                "doc_type": (_validate_doc_type(doc_type or "") if doc_type else ""),
            },
        )
        vector_results = list(vector_status.get("results", []))
    lexical_results = _lexical_search(query, docs, top_k=top_k, min_score=min_score)
    merged = []
    seen: set[str] = set()
    for item in vector_results + lexical_results:
        doc_id = str(item.get("doc_id", ""))
        mode = str(item.get("retrieval_mode", "vector" if item in vector_results else "lexical"))
        key = f"{doc_id}:{mode}"
        if key in seen:
            continue
        seen.add(key)
        if "retrieval_mode" not in item:
            item["retrieval_mode"] = "vector"
        merged.append(item)
        if len(merged) >= top_k:
            break

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    _append_telemetry(
        {
            "event": "rag_search",
            "query": query,
            "tool_family": tool_family or "",
            "tool_name": tool_name or "",
            "provider": provider or "",
            "doc_type": doc_type or "",
            "vector_backend": vector_store.backend,
            "vector_ok": bool(vector_status.get("ok", True)),
            "result_count": len(merged),
            "fallback_used": 1 if not vector_results else 0,
            "elapsed_ms": elapsed_ms,
        }
    )
    return {
        "ok": True,
        "count": len(merged),
        "results": merged,
        "metrics": {
            "elapsed_ms": elapsed_ms,
            "vector_backend": vector_store.backend,
            "vector_ok": bool(vector_status.get("ok", True)),
            "fallback_used": 1 if not vector_results else 0,
        },
    }


def rag_get_tool_execution_guidance(
    tool_name: str,
    intent: str,
    provider: str | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    tool_name = (tool_name or "").strip()
    if not tool_name:
        return {"ok": False, "error": "tool_name is required"}
    family = _family_from_tool(tool_name)
    preferred_doc_types = ["howto", "errors", "reference"]
    collected = []
    for dtype in preferred_doc_types:
        response = rag_search_tool_guidance(
            query=intent,
            tool_family=family,
            tool_name=tool_name,
            provider=provider,
            top_k=top_k,
            min_score=0.15,
            doc_type=dtype,
        )
        for hit in response.get("results", []):
            collected.append(hit)
        if len(collected) >= top_k:
            break
    if not collected:
        response = rag_search_tool_guidance(
            query=intent,
            tool_family=family,
            tool_name=tool_name,
            provider=provider,
            top_k=top_k,
            min_score=0.15,
        )
        collected = list(response.get("results", []))
    collected = collected[:top_k]
    guidance = []
    sources = []
    for row in collected:
        snippet = str(row.get("snippet", "")).strip()
        if snippet:
            guidance.append(snippet)
        src = str(row.get("source_url", "")).strip()
        if src and src not in sources:
            sources.append(src)
    return {
        "ok": True,
        "tool_name": tool_name,
        "tool_family": family,
        "guidance_text": "\n\n".join(guidance[:3]),
        "sources": sources,
        "hits": collected,
    }
