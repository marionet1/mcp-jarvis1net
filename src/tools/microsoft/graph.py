from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from .graph_context import get_graph_bearer

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"

_MISSING_TOKEN_DETAIL = (
    "Missing Microsoft Graph access token. Send header X-Graph-Authorization: Bearer <token> on POST /v1/tools/call. "
    "Obtain the token on the agent (your Azure app registration + user login); MCP does not store client secrets or tokens."
)


def graph_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = get_graph_bearer()
    if not token:
        raise HTTPException(status_code=401, detail=_MISSING_TOKEN_DETAIL)
    url = f"{GRAPH_ROOT}{path}" if path.startswith("/") else f"{GRAPH_ROOT}/{path}"
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=45.0) as client:
        resp = client.get(url, headers=headers, params=params or {})
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:4000])
    return resp.json()
