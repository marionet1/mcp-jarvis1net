from __future__ import annotations

from pathlib import Path

import msal
from fastapi import HTTPException

from .settings import (
    authority,
    client_id,
    client_secret,
    graph_scopes,
    microsoft_configured,
    redirect_uri,
    token_cache_path,
)


def _build_app() -> tuple[msal.ConfidentialClientApplication, msal.SerializableTokenCache]:
    if not microsoft_configured():
        raise HTTPException(status_code=503, detail="Microsoft integration is not configured (missing env vars).")
    cache = msal.SerializableTokenCache()
    path = Path(token_cache_path())
    if path.exists():
        try:
            cache.deserialize(path.read_text(encoding="utf-8"))
        except OSError:
            pass
    app = msal.ConfidentialClientApplication(
        client_id(),
        authority=authority(),
        client_credential=client_secret(),
        token_cache=cache,
    )
    return app, cache


def _persist_cache(cache: msal.SerializableTokenCache) -> None:
    if not cache.has_state_changed:
        return
    path = Path(token_cache_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache.serialize(), encoding="utf-8")


def authorization_url(state: str) -> str:
    ru = redirect_uri()
    if not ru:
        raise HTTPException(status_code=503, detail="MICROSOFT_REDIRECT_URI is not set.")
    app, _cache = _build_app()
    return app.get_authorization_request_url(
        scopes=graph_scopes(),
        state=state,
        redirect_uri=ru,
    )


def exchange_authorization_code(code: str) -> dict[str, object]:
    ru = redirect_uri()
    if not ru:
        raise HTTPException(status_code=503, detail="MICROSOFT_REDIRECT_URI is not set.")
    app, cache = _build_app()
    result = app.acquire_token_by_authorization_code(
        code,
        scopes=graph_scopes(),
        redirect_uri=ru,
    )
    _persist_cache(cache)
    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=str(result.get("error_description") or result.get("error")),
        )
    return result


def acquire_access_token() -> str:
    app, cache = _build_app()
    accounts = app.get_accounts()
    if not accounts:
        raise HTTPException(
            status_code=401,
            detail=(
                "Microsoft account not linked. Call GET /v1/tools/microsoft/oauth/start "
                "with a valid MCP Bearer key (scope microsoft), then complete sign-in in the browser."
            ),
        )
    result = app.acquire_token_silent(graph_scopes(), account=accounts[0])
    _persist_cache(cache)
    if not result or "access_token" not in result:
        raise HTTPException(
            status_code=401,
            detail=str((result or {}).get("error_description") or (result or {}).get("error") or "Silent token failed"),
        )
    return str(result["access_token"])


def linked_account_summary() -> dict[str, object]:
    if not microsoft_configured():
        return {"configured": False, "linked": False}
    app, _cache = _build_app()
    accounts = app.get_accounts()
    if not accounts:
        return {"configured": True, "linked": False}
    a = accounts[0]
    return {
        "configured": True,
        "linked": True,
        "username": a.get("username"),
        "environment": a.get("environment"),
    }
