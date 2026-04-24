from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from src.deps import ApiKeyAuth, require_api_key
from src.tools.registry import ToolCallBody, manifest_for_auth, run_tool_call

router = APIRouter(prefix="/v1/tools", tags=["tools"])


@router.get(
    "",
    summary="List tools manifest for this API key",
    description="Returns OpenAI-compatible function schemas filtered by allowed key scopes.",
)
def tools_manifest(auth: ApiKeyAuth = Depends(require_api_key)) -> dict:
    tools = manifest_for_auth(auth)
    return {"tools": tools, "count": len(tools)}


@router.post(
    "/call",
    summary="Execute a tool by name",
    description=(
        "Executes one tool call with {name, arguments}. Scope is enforced per tool. "
        "For `microsoft_*` tools you must send `X-Graph-Authorization: Bearer <delegated Graph access token>`; "
        "the agent obtains tokens with its own Azure app registration — MCP does not store Microsoft client secrets."
    ),
)
def tools_call(
    body: ToolCallBody,
    auth: ApiKeyAuth = Depends(require_api_key),
    x_graph_authorization: str | None = Header(default=None, alias="X-Graph-Authorization"),
) -> dict:
    graph_token: str | None = None
    if x_graph_authorization and x_graph_authorization.lower().startswith("bearer "):
        graph_token = x_graph_authorization.split(" ", 1)[1].strip() or None
    result = run_tool_call(body.name, body.arguments, auth, graph_access_token=graph_token)
    return {"name": body.name, "result": result}

