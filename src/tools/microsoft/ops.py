from __future__ import annotations

from typing import Any

from src.deps import ApiKeyAuth

from .graph import graph_api, graph_get
from .graph_context import get_graph_bearer


def microsoft_integration_status(_: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    _ = auth
    if get_graph_bearer():
        return {
            "ready": True,
            "message": "Microsoft Graph access token is present (X-Graph-Authorization). MCP has no Azure app credentials.",
        }
    return {
        "ready": False,
        "message": (
            "No token on this request. The agent must obtain a delegated Graph access token using its own Azure "
            "registration and send X-Graph-Authorization on every microsoft_* tool call."
        ),
    }


def microsoft_graph_me(_: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    _ = auth
    return graph_get("/me")


def microsoft_mail_list_messages(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    _ = auth
    top = int(args.get("top", 10))
    top = min(max(top, 1), 50)
    return graph_get("/me/mailFolders/inbox/messages", {"$top": str(top), "$select": "id,subject,receivedDateTime,isRead"})


def microsoft_calendar_list_events(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    _ = auth
    top = int(args.get("top", 10))
    top = min(max(top, 1), 50)
    return graph_get(
        "/me/calendar/events",
        {"$top": str(top), "$select": "id,subject,start,end,organizer,isCancelled"},
    )


def microsoft_onedrive_list_root(_: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    _ = auth
    return graph_get("/me/drive/root/children", {"$top": "50"})


def microsoft_graph_api(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    """Generic Graph v1 call under /me/... (mail, calendar, drive, profile)."""
    _ = auth
    method = str(args.get("method", "GET")).strip()
    path = str(args.get("path", "")).strip()
    raw_q = args.get("query")
    query = raw_q if isinstance(raw_q, dict) else None
    raw_b = args.get("body")
    body: dict[str, Any] | list[Any] | None
    if isinstance(raw_b, dict):
        body = raw_b
    elif isinstance(raw_b, list):
        body = raw_b
    else:
        body = None
    out = graph_api(method, path, query=query, body=body)
    if isinstance(out, dict):
        return out
    return {"data": out}
