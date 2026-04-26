#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rag_tools import rag_refresh_tool_catalog, rag_upsert_document  # noqa: E402
from tool_manifest import mcp_tool_list  # noqa: E402


def _fetch_url(url: str, timeout_sec: int = 25) -> str:
    response = requests.get(url, timeout=timeout_sec, headers={"User-Agent": "jarvis1net-rag-ingest/1.0"})
    response.raise_for_status()
    html = response.text
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _doc_id(item: dict[str, Any]) -> str:
    if item.get("doc_id"):
        return str(item["doc_id"]).strip()
    seed = "|".join(
        [
            str(item.get("tool_family", "")),
            str(item.get("tool_name", "")),
            str(item.get("title", "")),
            str(item.get("source_url", "")),
        ]
    )
    return "doc-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _load_source_file(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
        raise ValueError(f"Invalid source file format: {path}")
    return [x for x in data["documents"] if isinstance(x, dict)]


def ingest_file(path: Path, dry_run: bool = False) -> dict[str, Any]:
    rows = _load_source_file(path)
    upserted = 0
    failed = 0
    errors = []
    for item in rows:
        try:
            source_url = str(item.get("source_url", "")).strip()
            content = str(item.get("content", "")).strip()
            if not content and source_url:
                content = _fetch_url(source_url)
            if not content:
                raise ValueError("Document has no content and no fetchable source_url.")

            payload = {
                "doc_id": _doc_id(item),
                "title": str(item.get("title", "Untitled")),
                "content": content,
                "tool_family": str(item.get("tool_family", "other")),
                "tool_name": str(item.get("tool_name", "")) or None,
                "provider": str(item.get("provider", "internal")),
                "doc_type": str(item.get("doc_type", "reference")),
                "source_url": source_url or None,
                "version": str(item.get("version", "")) or None,
                "tags": [str(t) for t in item.get("tags", [])] if isinstance(item.get("tags"), list) else [],
            }
            if dry_run:
                print(f"[DRY-RUN] upsert {payload['doc_id']} :: {payload['title']}")
            else:
                result = rag_upsert_document(**payload)
                if not result.get("ok"):
                    raise RuntimeError(str(result))
            upserted += 1
        except Exception as exc:
            failed += 1
            errors.append(f"{item.get('title', 'unknown')}: {exc}")
    return {"ok": failed == 0, "upserted": upserted, "failed": failed, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documentation into local MCP RAG store.")
    parser.add_argument("--source", action="append", required=True, help="YAML source file path.")
    parser.add_argument("--dry-run", action="store_true", help="Parse/fetch without writing into RAG store.")
    args = parser.parse_args()

    refresh = rag_refresh_tool_catalog(mcp_tool_list)
    print(f"tool_catalog: ok={refresh.get('ok')} count={refresh.get('count')}")
    overall_failed = 0
    for source in args.source:
        path = Path(source).expanduser().resolve()
        summary = ingest_file(path, dry_run=args.dry_run)
        print(f"{path.name}: upserted={summary['upserted']} failed={summary['failed']}")
        for err in summary["errors"][:10]:
            print(f"  - {err}")
        overall_failed += int(summary["failed"])
    if overall_failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
