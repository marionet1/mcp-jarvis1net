from __future__ import annotations

from fastapi import APIRouter, Depends

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
    description="Executes one tool call with {name, arguments}. Scope is enforced per tool.",
)
def tools_call(body: ToolCallBody, auth: ApiKeyAuth = Depends(require_api_key)) -> dict:
    result = run_tool_call(body.name, body.arguments, auth)
    return {"name": body.name, "result": result}

