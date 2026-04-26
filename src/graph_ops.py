from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from graph import GraphHttpError, graph_api, graph_get, graph_get_absolute, get_graph_bearer

CAL_START_NOTE = "Each item may include `_jarvis1net_calendar_date` = calendar date of `start` only."


def resolve_graph_token(args: dict[str, object]) -> str | None:
    token = args.get("graph_access_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    env = (os.getenv("MCP_GRAPH_ACCESS_TOKEN") or "").strip()
    return env or None


def strip_token_copy(args: dict[str, object]) -> dict[str, object]:
    out = dict(args)
    out.pop("graph_access_token", None)
    return out


def microsoft_integration_status(_: dict[str, object]) -> dict[str, object]:
    if get_graph_bearer():
        return {"ready": True, "message": "Microsoft Graph access token is present."}
    return {"ready": False, "message": "No token. Set MCP_GRAPH_ACCESS_TOKEN or pass graph_access_token."}


def microsoft_graph_me(_: dict[str, object]) -> dict[str, object]:
    return graph_get("/me")


def microsoft_mail_list_messages(args: dict[str, object]) -> dict[str, object]:
    top = min(max(int(args.get("top", 10)), 1), 50)
    return graph_get("/me/mailFolders/inbox/messages", {"$top": str(top), "$select": "id,subject,receivedDateTime,isRead"})


def microsoft_mail_list_inbox_tree(args: dict[str, object]) -> dict[str, object]:
    return _mail_tree(args, unread_only=False, note="First-level folders under Inbox only.")


def microsoft_mail_list_unread_inbox_tree(args: dict[str, object]) -> dict[str, object]:
    return _mail_tree(args, unread_only=True, note="Unread only. First page per folder.")


def _mail_tree(args: dict[str, object], unread_only: bool, note: str) -> dict[str, object]:
    top = min(max(int(args.get("top_per_folder", args.get("top", 10))), 1), 50)
    max_children = min(max(int(args.get("max_child_folders", 15)), 1), 30)
    inbox_meta = graph_get("/me/mailFolders/inbox", {"$select": "id,displayName,unreadItemCount"})
    inbox_id = str(inbox_meta.get("id", "")).strip()
    if not inbox_id:
        raise ValueError("Graph did not return Inbox folder id")
    q = {"$top": str(top), "$select": "id,subject,receivedDateTime,isRead,from"}
    if unread_only:
        q["$filter"] = "isRead eq false"
    folders: list[dict[str, object]] = [
        {
            "folder_id": inbox_id,
            "displayName": inbox_meta.get("displayName") or "Inbox",
            "unreadItemCount": inbox_meta.get("unreadItemCount"),
            "messages": graph_get(f"/me/mailFolders/{inbox_id}/messages", q),
        }
    ]
    children = graph_get("/me/mailFolders/inbox/childFolders", {"$select": "id,displayName,unreadItemCount", "$top": str(max_children)})
    for child in children.get("value", []):
        if not isinstance(child, dict):
            continue
        folder_id = str(child.get("id", "")).strip()
        if not folder_id:
            continue
        folders.append({"folder_id": folder_id, "displayName": child.get("displayName"), "unreadItemCount": child.get("unreadItemCount"), "messages": graph_get(f"/me/mailFolders/{folder_id}/messages", q)})
    return {"note": note, "child_folders_page_truncated": bool(children.get("@odata.nextLink")), "folders": folders}


def microsoft_mail_search_messages(args: dict[str, object]) -> dict[str, object]:
    raw = args.get("query", args.get("q"))
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("query (or q) is required.")
    q = re.sub(r"\s+", " ", raw.strip())
    if len(q) > 400:
        raise ValueError("query too long (max 400 characters)")
    top = min(max(int(args.get("top", 20)), 1), 50)
    include_preview = bool(args.get("include_body_preview", True))
    select = "id,subject,from,receivedDateTime,isRead" + (",bodyPreview" if include_preview else "")
    if not (q.startswith('"') and q.endswith('"')) and " and " not in q.lower() and " or " not in q.lower() and ":" not in q:
        q = f'"{q.replace(chr(34), " ").strip()}"'
    data = graph_api("GET", "/me/messages", query={"$search": q, "$top": str(top), "$select": select}, extra_headers={"ConsistencyLevel": "eventual"})
    if not isinstance(data, dict):
        raise ValueError("Graph search returned non-object JSON")
    data["note"] = "$search uses the mailbox index."
    return data


def microsoft_mail_mark_read(args: dict[str, object]) -> dict[str, object]:
    ids = args.get("message_ids")
    if not isinstance(ids, list) or not ids:
        raise ValueError("message_ids must be a non-empty JSON array")
    if len(ids) > 40:
        raise ValueError("At most 40 message_ids per call")
    folder_id = str(args.get("mail_folder_id", args.get("folder_id", ""))).strip() or None
    results, ok, fail = [], 0, 0
    for item in ids:
        msg_id = str(item).strip()
        if not msg_id:
            continue
        try:
            out = graph_api("PATCH", f"/me/messages/{msg_id}", body={"isRead": True})
            ok += 1
            results.append({"id": msg_id, "ok": True, "path_used": "/me/messages/{id}", "result": out})
        except Exception as exc:
            if isinstance(exc, GraphHttpError) and exc.status_code == 404 and folder_id:
                try:
                    out2 = graph_api("PATCH", f"/me/mailFolders/{folder_id}/messages/{msg_id}", body={"isRead": True})
                    ok += 1
                    results.append({"id": msg_id, "ok": True, "path_used": "/me/mailFolders/{folderId}/messages/{id}", "result": out2})
                    continue
                except Exception as exc2:
                    fail += 1
                    results.append({"id": msg_id, "ok": False, "status_code": getattr(exc2, "status_code", 500), "detail": str(exc2)[:2000]})
                    continue
            fail += 1
            results.append({"id": msg_id, "ok": False, "status_code": getattr(exc, "status_code", 500), "detail": str(exc)[:2000]})
    return {"summary": {"patched_ok": ok, "patched_failed": fail, "ids_requested": len(ids)}, "mail_folder_id_for_fallback": folder_id, "results": results}


def microsoft_mail_mark_folder_read(args: dict[str, object]) -> dict[str, object]:
    folder_id = str(args.get("mail_folder_id", args.get("folder_id", ""))).strip()
    if not folder_id:
        raise ValueError("mail_folder_id is required")
    top = min(max(int(args.get("top", 50)), 1), 50)
    all_ids: list[str] = []
    pages, next_url = 0, None
    while pages < 40:
        data = graph_get_absolute(next_url) if next_url else graph_api("GET", f"/me/mailFolders/{folder_id}/messages", query={"$filter": "isRead eq false", "$select": "id", "$top": str(top)})
        if not isinstance(data, dict):
            break
        pages += 1
        for item in data.get("value", []):
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip():
                all_ids.append(item["id"].strip())
        nl = data.get("@odata.nextLink")
        next_url = str(nl).strip() if isinstance(nl, str) and nl.strip() else None
        if not next_url:
            break
    if len(all_ids) > 500:
        return {"ok": False, "error": f"Too many unread messages ({len(all_ids)}); max 500 in one call."}
    ok = fail = 0
    results = []
    for msg_id in all_ids:
        try:
            out = graph_api("PATCH", f"/me/messages/{msg_id}", body={"isRead": True})
            ok += 1
            results.append({"id": msg_id, "ok": True, "result": out})
        except Exception as exc:
            fail += 1
            results.append({"id": msg_id, "ok": False, "status_code": getattr(exc, "status_code", 500), "detail": str(exc)[:1500]})
    return {"summary": {"mail_folder_id": folder_id, "pages_fetched": pages, "unread_ids_collected": len(all_ids), "patched_ok": ok, "patched_failed": fail}, "failures_sample": [r for r in results if r.get("ok") is not True][:15]}


def microsoft_calendar_list_events(args: dict[str, object]) -> dict[str, object]:
    top = min(max(int(args.get("top", 25)), 1), 50)
    days = min(max(int(args.get("days", 56)), 1), 120)
    past_days = min(max(int(args.get("past_days", 1)), 0), 14)
    now = datetime.now(UTC)
    raw = graph_get("/me/calendarView", {"startDateTime": _utc(now - timedelta(days=past_days)), "endDateTime": _utc(now + timedelta(days=days)), "$top": str(top), "$orderby": "start/dateTime", "$select": "id,subject,start,end,organizer,isCancelled,isAllDay,location,showAs"})
    return _enrich(raw, "UTC")


def microsoft_calendar_events_on_date(args: dict[str, object]) -> dict[str, object]:
    date_raw = str(args.get("date", "")).strip()
    tz_name = str(args.get("time_zone", "Europe/Warsaw")).strip() or "Europe/Warsaw"
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_raw):
        raise ValueError("date must be YYYY-MM-DD")
    top = min(max(int(args.get("top", 50)), 1), 50)
    tz = ZoneInfo(tz_name)
    start_local = datetime.fromisoformat(f"{date_raw}T00:00:00").replace(tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    raw = graph_get("/me/calendarView", {"startDateTime": _utc(start_local.astimezone(UTC)), "endDateTime": _utc(end_local.astimezone(UTC)), "$top": str(top), "$orderby": "start/dateTime", "$select": "id,subject,start,end,organizer,isCancelled,isAllDay,location,showAs"})
    data = _enrich(raw, tz_name)
    vals = data.get("value")
    if isinstance(vals, list):
        data["value"] = [item for item in vals if not isinstance(item, dict) or item.get("_jarvis1net_calendar_date") in (None, date_raw)]
        data["_jarvis1net_filtered_to_start_calendar_date"] = date_raw
    return data


def microsoft_onedrive_list_root(_: dict[str, object]) -> dict[str, object]:
    return graph_get("/me/drive/root/children", {"$top": "50"})


def microsoft_graph_api(args: dict[str, object]) -> dict[str, object]:
    out = graph_api(str(args.get("method", "GET")).strip().upper(), str(args.get("path", "")).strip(), query=args.get("query") if isinstance(args.get("query"), dict) else None, body=args.get("body") if isinstance(args.get("body"), (dict, list)) else None)
    return out if isinstance(out, dict) else {"data": out}


def _utc(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _start_date(start: object, default_tz: str) -> str | None:
    if not isinstance(start, dict):
        return None
    d = start.get("date")
    if isinstance(d, str) and len(d) >= 10:
        return d[:10]
    dt_raw = start.get("dateTime")
    if not isinstance(dt_raw, str) or not dt_raw.strip():
        return None
    tz_name = str(start.get("timeZone") or default_tz)
    raw = dt_raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(tz_name))
    return parsed.astimezone(ZoneInfo(tz_name)).date().isoformat()


def _enrich(data: dict[str, object], default_tz: str) -> dict[str, object]:
    out = dict(data)
    out["_jarvis1net_note"] = CAL_START_NOTE
    vals = out.get("value")
    if not isinstance(vals, list):
        return out
    mapped = []
    for item in vals:
        if not isinstance(item, dict):
            mapped.append(item)
            continue
        row = dict(item)
        cd = _start_date(row.get("start"), default_tz)
        if cd:
            row["_jarvis1net_calendar_date"] = cd
        mapped.append(row)
    out["value"] = mapped
    return out

