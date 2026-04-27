#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rag.service import rag_search_tool_guidance  # noqa: E402


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def main() -> None:
    path = Path(__file__).resolve().parent / "golden_queries.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    total = len(cases)
    passed = 0
    for case in cases:
        result = rag_search_tool_guidance(
            query=case["query"],
            tool_family=case.get("tool_family"),
            top_k=5,
            min_score=0.1,
        )
        hits = result.get("results", [])
        min_hits = int(case.get("min_hits", 1))
        blob = " ".join([_norm(str(h.get("snippet", ""))) for h in hits])
        expected_any = [str(x).lower() for x in case.get("expected_any", [])]
        keyword_ok = any(token in blob for token in expected_any) if expected_any else True
        ok = len(hits) >= min_hits and keyword_ok
        if ok:
            passed += 1
        print(
            f"[{'PASS' if ok else 'FAIL'}] {case['id']} "
            f"hits={len(hits)} expected_min={min_hits} keyword_ok={keyword_ok}"
        )
    ratio = passed / total if total else 0.0
    print(f"\nrag_eval: {passed}/{total} passed ({ratio:.1%})")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
