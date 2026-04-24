from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from .msal_client import acquire_access_token

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


def graph_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = acquire_access_token()
    url = f"{GRAPH_ROOT}{path}" if path.startswith("/") else f"{GRAPH_ROOT}/{path}"
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=45.0) as client:
        resp = client.get(url, headers=headers, params=params or {})
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:4000])
    return resp.json()
