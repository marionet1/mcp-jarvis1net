from __future__ import annotations

from typing import Any

from fastapi import HTTPException

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


def microsoft_mail_mark_read(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    """PATCH isRead=true for many message ids (one HTTP call per id; returns per-id status)."""
    _ = auth
    raw = args.get("message_ids")
    if not isinstance(raw, list) or not raw:
        raise HTTPException(status_code=400, detail="message_ids must be a non-empty JSON array of Graph message id strings")
    folder_raw = args.get("mail_folder_id") or args.get("folder_id")
    folder_id = folder_raw.strip() if isinstance(folder_raw, str) else None
    max_ids = 40
    if len(raw) > max_ids:
        raise HTTPException(
            status_code=400,
            detail=f"At most {max_ids} message_ids per call; split into multiple calls or narrow the GET.",
        )
    results: list[dict[str, Any]] = []
    ok_count = 0
    fail_count = 0
    for item in raw:
        if not isinstance(item, str):
            fail_count += 1
            results.append({"id": repr(item), "ok": False, "detail": "message_ids entries must be strings"})
            continue
        mid = item.strip()
        if not mid:
            continue
        if folder_id:
            path = f"/me/mailFolders/{folder_id}/messages/{mid}"
        else:
            path = f"/me/messages/{mid}"
        try:
            out = graph_api("PATCH", path, body={"isRead": True})
            ok_count += 1
            results.append({"id": mid, "ok": True, "result": out})
        except HTTPException as ex:
            fail_count += 1
            det = ex.detail
            if not isinstance(det, str):
                det = str(det)
            results.append({"id": mid, "ok": False, "status_code": ex.status_code, "detail": det[:2000]})
    return {
        "summary": {"patched_ok": ok_count, "patched_failed": fail_count, "ids_requested": len(raw)},
        "mail_folder_id_used": folder_id,
        "results": results,
    }


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
