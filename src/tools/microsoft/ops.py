from __future__ import annotations

from typing import Any

from src.deps import ApiKeyAuth

from .graph import graph_get
from .msal_client import linked_account_summary


def microsoft_integration_status(_: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    _ = auth
    return linked_account_summary()


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
