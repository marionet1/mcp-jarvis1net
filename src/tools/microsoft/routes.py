from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, RedirectResponse

from src.deps import ApiKeyAuth, require_api_key

from .msal_client import authorization_url, exchange_authorization_code
from .oauth_state import issue_state, consume_state
from .settings import microsoft_configured

router = APIRouter(prefix="/v1/tools/microsoft", tags=["microsoft"])


@router.get(
    "/oauth/start",
    summary="Start Microsoft OAuth (delegated)",
    description="Requires MCP API key with `microsoft` scope. Redirects browser to Microsoft login.",
)
def microsoft_oauth_start(auth: ApiKeyAuth = Depends(require_api_key)) -> RedirectResponse:
    if not auth.allows("microsoft"):
        raise HTTPException(
            status_code=403,
            detail="API key is not allowed to use microsoft scope.",
        )
    if not microsoft_configured():
        raise HTTPException(
            status_code=503,
            detail="Microsoft OAuth is not configured (set MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET / MICROSOFT_REDIRECT_URI).",
        )
    state = issue_state()
    url = authorization_url(state)
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/oauth/callback",
    summary="Microsoft OAuth callback",
    description="Public endpoint used by Microsoft redirect. Validates state and stores tokens.",
)
def microsoft_oauth_callback(
    code: str = Query(..., description="Authorization code from Microsoft."),
    state: str = Query(..., description="CSRF state issued by /oauth/start."),
) -> PlainTextResponse:
    if not consume_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state. Start login again from /oauth/start.")
    if not microsoft_configured():
        raise HTTPException(status_code=503, detail="Microsoft OAuth is not configured.")
    exchange_authorization_code(code)
    return PlainTextResponse(
        "Microsoft account linked successfully. You can close this tab and use Graph tools from the agent.",
        status_code=200,
    )
