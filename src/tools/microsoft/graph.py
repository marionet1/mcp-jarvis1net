from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, unquote

import httpx
from fastapi import HTTPException

from .graph_context import get_graph_bearer

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"

_MISSING_TOKEN_DETAIL = (
    "Missing Microsoft Graph access token. Send header X-Graph-Authorization: Bearer <token> on POST /v1/tools/call. "
    "Obtain the token on the agent (your Azure app registration + user login); MCP does not store client secrets or tokens."
)

_MAX_PATH_LEN = 2048
_MAX_JSON_BODY_BYTES = 512 * 1024


def _safe_me_path(path: str) -> str:
    p = path.strip()
    if len(p) > _MAX_PATH_LEN:
        raise HTTPException(status_code=400, detail="path too long")
    if not p.startswith("/"):
        p = "/" + p
    if p != "/me" and not p.startswith("/me/"):
        raise HTTPException(
            status_code=400,
            detail="path must be /me or start with /me/ (delegated Graph for the signed-in user only).",
        )
    if ".." in p or "\n" in p or "\r" in p:
        raise HTTPException(status_code=400, detail="invalid path")
    return p


def _encode_graph_me_path(path: str) -> str:
    """
    Graph mail message/folder ids often contain '=', '+', '/' — encode those path segments
    so httpx/servers match the same resource Microsoft documents (see message-update).
    """
    if "?" in path:
        p, qs = path.split("?", 1)
        suffix = "?" + qs
    else:
        p = path
        suffix = ""
    parts = p.split("/")
    out: list[str] = []
    for i, seg in enumerate(parts):
        prev = parts[i - 1] if i > 0 else ""
        if prev == "messages" and seg and not seg.startswith("$"):
            out.append(quote(unquote(seg), safe=""))
        elif prev == "mailFolders" and seg and not seg.startswith("$"):
            well_known = ("inbox", "drafts", "sentitems", "deleteditems", "junkemail", "archive", "outbox")
            if seg.lower() in well_known:
                out.append(seg)
            else:
                out.append(quote(unquote(seg), safe=""))
        else:
            out.append(seg)
    return "/".join(out) + suffix


def graph_api(
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | list[Any] | None = None,
) -> Any:
    """HTTP call to Graph v1.0; path restricted to /me/... for delegated safety on shared MCP."""
    token = get_graph_bearer()
    if not token:
        raise HTTPException(status_code=401, detail=_MISSING_TOKEN_DETAIL)
    safe_path = _encode_graph_me_path(_safe_me_path(path))
    m = method.strip().upper()
    if m not in ("GET", "POST", "PATCH", "PUT", "DELETE"):
        raise HTTPException(status_code=400, detail="method must be GET, POST, PATCH, PUT, or DELETE")
    url = f"{GRAPH_ROOT}{safe_path}"
    headers: dict[str, str] = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = query or {}
    with httpx.Client(timeout=120.0) as client:
        if m in ("POST", "PATCH", "PUT") and body is not None:
            raw = json.dumps(body, ensure_ascii=False)
            if len(raw.encode("utf-8")) > _MAX_JSON_BODY_BYTES:
                raise HTTPException(status_code=400, detail="JSON body exceeds size limit")
            h2 = {**headers, "Content-Type": "application/json"}
            resp = client.request(m, url, headers=h2, params=params, content=raw.encode("utf-8"))
        else:
            resp = client.request(m, url, headers=headers, params=params)
    if resp.status_code == 204:
        return {"ok": True, "status_code": 204}
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:8000])
    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" in ct and resp.content:
        return resp.json()
    return {"status_code": resp.status_code, "text": (resp.text or "")[:8000]}


def graph_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    data = graph_api("GET", path, query=params or {})
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Graph GET returned non-object JSON")
    return data
