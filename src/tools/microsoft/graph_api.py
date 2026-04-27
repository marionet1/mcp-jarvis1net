from __future__ import annotations

import contextvars
import json
from urllib.parse import parse_qsl, urlencode, urlparse

import requests

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
_graph_token_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("graph_token", default=None)
_MISSING = (
    "Missing Microsoft Graph access token. Set MCP_GRAPH_ACCESS_TOKEN or pass graph_access_token "
    "on the tool call. The host/agent obtains OAuth tokens; this server does not store client secrets."
)
_MAX_PATH_LEN = 2048
_MAX_JSON_BODY = 512 * 1024


class GraphHttpError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def run_with_graph_token(token: str | None, fn):
    token_ref = _graph_token_ctx.set(token)
    try:
        return fn()
    finally:
        _graph_token_ctx.reset(token_ref)


def get_graph_bearer() -> str | None:
    return _graph_token_ctx.get()


def _safe_me_path(path: str) -> str:
    p = path.strip()
    if len(p) > _MAX_PATH_LEN:
        raise ValueError("path too long")
    if not p.startswith("/"):
        p = "/" + p
    if p != "/me" and not p.startswith("/me/"):
        raise ValueError("path must be /me or start with /me/ (delegated user only).")
    if ".." in p or "\n" in p or "\r" in p:
        raise ValueError("invalid path")
    return p


def _canonical_key(key: str) -> str:
    k = str(key).strip()
    if not k:
        return k
    if k.startswith("$"):
        return "$" + k[1:].lower()
    low = k.lower()
    if low == "startdatetime":
        return "startDateTime"
    if low == "enddatetime":
        return "endDateTime"
    return k


def _normalize_query(query: dict[str, object]) -> dict[str, str]:
    return {_canonical_key(k): str(v) for k, v in query.items()}


def _build_graph_url(path: str, query: dict[str, str] | None) -> str:
    url = f"{GRAPH_ROOT}{path}"
    if query:
        return f"{url}?{urlencode(query)}"
    return url


def graph_api(
    method: str,
    path: str,
    *,
    query: dict[str, object] | None = None,
    body: object | None = None,
    extra_headers: dict[str, str] | None = None,
):
    token = get_graph_bearer()
    if not token:
        raise GraphHttpError(_MISSING, 401)
    parsed = urlparse(path.strip())
    base_path = parsed.path
    embedded_q = dict(parse_qsl(parsed.query))
    merged_q: dict[str, str] = dict(embedded_q)
    if query:
        merged_q.update(_normalize_query(query))
    safe_path = _safe_me_path(base_path)
    m = method.strip().upper()
    if m not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
        raise ValueError("method must be GET, POST, PATCH, PUT, or DELETE")
    url = _build_graph_url(safe_path, merged_q or None)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if extra_headers:
        for key, val in extra_headers.items():
            key = str(key).strip()
            val = str(val).strip()
            if key and val:
                headers[key] = val
    payload = None
    if m in {"POST", "PATCH", "PUT"} and body is not None:
        payload_raw = json.dumps(body)
        if len(payload_raw.encode("utf-8")) > _MAX_JSON_BODY:
            raise ValueError("JSON body exceeds size limit")
        headers["Content-Type"] = "application/json"
        payload = payload_raw
    response = requests.request(m, url, headers=headers, data=payload, timeout=30)
    if response.status_code == 204:
        return {"ok": True, "status_code": 204}
    if response.status_code >= 400:
        raise GraphHttpError(response.text[:8000], response.status_code)
    if not response.content:
        return {"status_code": response.status_code, "text": ""}
    content_type = (response.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        if not response.text.strip():
            return {"status_code": response.status_code, "text": ""}
        return response.json()
    return {"status_code": response.status_code, "text": response.text[:8000]}


def graph_get_absolute(absolute_url: str):
    token = get_graph_bearer()
    if not token:
        raise GraphHttpError(_MISSING, 401)
    url = absolute_url.strip()
    if not url.startswith("https://graph.microsoft.com/v1.0"):
        raise ValueError("URL must start with https://graph.microsoft.com/v1.0 (Graph @odata.nextLink).")
    response = requests.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=30)
    if response.status_code >= 400:
        raise GraphHttpError(response.text[:8000], response.status_code)
    if not response.content:
        return {"status_code": response.status_code, "text": ""}
    if "application/json" in (response.headers.get("content-type") or "").lower():
        return response.json()
    return {"status_code": response.status_code, "text": response.text[:8000]}


def graph_get(path: str, params: dict[str, object] | None = None, extra_headers: dict[str, str] | None = None) -> dict[str, object]:
    data = graph_api("GET", path, query=params or {}, extra_headers=extra_headers)
    if not isinstance(data, dict):
        raise ValueError("Graph GET returned non-object JSON")
    return data
