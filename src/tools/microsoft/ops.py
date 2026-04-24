from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from src.deps import ApiKeyAuth

from .graph import graph_api, graph_get, graph_get_absolute
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
        path_used = "/me/messages/{id}"
        try:
            out = graph_api("PATCH", f"/me/messages/{mid}", body={"isRead": True})
            ok_count += 1
            results.append({"id": mid, "ok": True, "path_used": path_used, "result": out})
        except HTTPException as ex:
            if folder_id and ex.status_code == 404:
                try:
                    out2 = graph_api("PATCH", f"/me/mailFolders/{folder_id}/messages/{mid}", body={"isRead": True})
                    ok_count += 1
                    results.append(
                        {
                            "id": mid,
                            "ok": True,
                            "path_used": "/me/mailFolders/{folderId}/messages/{id}",
                            "result": out2,
                            "note": "fallback after 404 on /me/messages/{id}",
                        }
                    )
                    continue
                except HTTPException as ex2:
                    fail_count += 1
                    det2 = ex2.detail if isinstance(ex2.detail, str) else str(ex2.detail)
                    results.append(
                        {
                            "id": mid,
                            "ok": False,
                            "status_code": ex2.status_code,
                            "detail": det2[:2000],
                            "note": "/me/messages 404 then folder-scoped PATCH failed",
                        }
                    )
                    continue
            fail_count += 1
            det = ex.detail
            if not isinstance(det, str):
                det = str(det)
            results.append({"id": mid, "ok": False, "status_code": ex.status_code, "detail": det[:2000]})
    return {
        "summary": {"patched_ok": ok_count, "patched_failed": fail_count, "ids_requested": len(raw)},
        "mail_folder_id_for_fallback": folder_id,
        "results": results,
    }


def microsoft_mail_mark_folder_read(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    """
    Lists all unread messages in one mail folder (follows @odata.nextLink), then PATCHes each via /me/messages/{id}.
    Prefer this over manual GET + $skip when the user wants every unread in that folder marked read.
    """
    _ = auth
    folder_raw = args.get("mail_folder_id") or args.get("folder_id")
    if not isinstance(folder_raw, str) or not folder_raw.strip():
        raise HTTPException(status_code=400, detail="mail_folder_id is required")
    fid = folder_raw.strip()
    top = int(args.get("top", 50))
    top = min(max(top, 1), 50)
    max_pages = 40
    max_patch = 500

    all_ids: list[str] = []
    pages = 0
    next_url: str | None = None
    path = f"/me/mailFolders/{fid}/messages"
    query: dict[str, Any] = {"$filter": "isRead eq false", "$select": "id", "$top": str(top)}

    while pages < max_pages:
        if next_url:
            data = graph_get_absolute(next_url)
        else:
            data = graph_api("GET", path, query=query)
        pages += 1
        if not isinstance(data, dict):
            return {
                "ok": False,
                "error": "Unexpected non-JSON object from Graph while listing unread messages",
                "summary": {"mail_folder_id": fid, "pages_fetched": pages},
            }
        vals = data.get("value")
        if isinstance(vals, list):
            for item in vals:
                if isinstance(item, dict):
                    iid = item.get("id")
                    if isinstance(iid, str) and iid.strip():
                        all_ids.append(iid.strip())
        nl = data.get("@odata.nextLink")
        next_url = nl.strip() if isinstance(nl, str) and nl.strip() else None
        if not next_url:
            break

    if len(all_ids) > max_patch:
        return {
            "ok": False,
            "error": f"Too many unread messages ({len(all_ids)}); max supported in one call is {max_patch}. Narrow folder or mark in batches.",
            "summary": {"mail_folder_id": fid, "unread_collected": len(all_ids)},
        }

    results: list[dict[str, Any]] = []
    ok_count = 0
    fail_count = 0
    for mid in all_ids:
        try:
            out = graph_api("PATCH", f"/me/messages/{mid}", body={"isRead": True})
            ok_count += 1
            results.append({"id": mid, "ok": True, "result": out})
        except HTTPException as ex:
            fail_count += 1
            det = ex.detail if isinstance(ex.detail, str) else str(ex.detail)
            results.append({"id": mid, "ok": False, "status_code": ex.status_code, "detail": det[:1500]})

    return {
        "summary": {
            "mail_folder_id": fid,
            "pages_fetched": pages,
            "unread_ids_collected": len(all_ids),
            "patched_ok": ok_count,
            "patched_failed": fail_count,
        },
        "failures_sample": [r for r in results if not r.get("ok")][:15],
    }


def _graph_calendarview_utc(dt: datetime) -> str:
    """ISO 8601 UTC for `startDateTime` / `endDateTime` in calendarView."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


_CAL_START_DATE_NOTE = (
    "Each item may include `_jarvis1net_calendar_date` = **calendar date of `start` only** (from `start.date` or "
    "`start.dateTime` in `start.timeZone`). For **all-day** events Graph often sets `end` on the **next** calendar day "
    "at 00:00 — **do not** assign the event to that day using `end`; use `_jarvis1net_calendar_date` or `start` only."
)


def _parse_graph_start_datetime_to_zoned(dt_raw: str, tz_win: str) -> datetime | None:
    """Parse Graph `start.dateTime`; no offset = wall-clock in `tz_win` (Graph convention)."""
    try:
        z = ZoneInfo(tz_win)
    except Exception:
        z = timezone.utc
    s = dt_raw.strip()
    if not s:
        return None
    if s.endswith("Z"):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt.astimezone(z)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        if "T" in s and "." in s:
            try:
                dt = datetime.fromisoformat(s.split(".", 1)[0])
            except ValueError:
                return None
        else:
            return None
    if dt.tzinfo is not None:
        return dt.astimezone(z)
    return dt.replace(tzinfo=z)


def _event_start_calendar_date(start: Any, *, default_tz: str) -> str | None:
    """Calendar day for the event — from `start` only (not `end`)."""
    if not isinstance(start, dict):
        return None
    date_only = start.get("date")
    if isinstance(date_only, str) and len(date_only) >= 10:
        return date_only[:10]
    dt_raw = start.get("dateTime")
    if not isinstance(dt_raw, str) or not dt_raw.strip():
        return None
    tz_win = str(start.get("timeZone") or "").strip() or default_tz
    dt = _parse_graph_start_datetime_to_zoned(dt_raw, tz_win)
    if dt is None:
        return None
    return dt.date().isoformat()


def _enrich_calendar_view_response(data: dict[str, Any], *, default_tz: str) -> dict[str, Any]:
    out: dict[str, Any] = {**data, "_jarvis1net_note": _CAL_START_DATE_NOTE}
    vals = out.get("value")
    if not isinstance(vals, list):
        return out
    new_vals: list[Any] = []
    for item in vals:
        if not isinstance(item, dict):
            new_vals.append(item)
            continue
        row = dict(item)
        st = row.get("start")
        prefer = default_tz
        if isinstance(st, dict):
            tz_s = str(st.get("timeZone") or "").strip()
            if tz_s:
                prefer = tz_s
        cd = _event_start_calendar_date(st, default_tz=prefer) if isinstance(st, dict) else None
        if cd:
            row["_jarvis1net_calendar_date"] = cd
        new_vals.append(row)
    out["value"] = new_vals
    return out


def microsoft_calendar_list_events(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    """
    Uses GET /me/calendarView (date window), not a raw /me/calendar/events list.

    ``/me/calendar/events?$top=…`` alone is misleading: default sort and no explicit window
    often drop **all-day** events (isAllDay) from the first page.
    calendarView returns all occurrences in the interval, including all-day and series instances.
    """
    _ = auth
    top = int(args.get("top", 25))
    top = min(max(top, 1), 50)
    days = int(args.get("days", 56))
    days = min(max(days, 1), 120)
    past_days = int(args.get("past_days", 1))
    past_days = min(max(past_days, 0), 14)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=past_days)
    end = now + timedelta(days=days)
    raw = graph_get(
        "/me/calendarView",
        {
            "startDateTime": _graph_calendarview_utc(start),
            "endDateTime": _graph_calendarview_utc(end),
            "$top": str(top),
            "$orderby": "start/dateTime",
            "$select": "id,subject,start,end,organizer,isCancelled,isAllDay,location,showAs",
        },
    )
    return _enrich_calendar_view_response(raw, default_tz="UTC")


def microsoft_calendar_events_on_date(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    """Single call: all occurrences (including all-day) on one calendar day in the given IANA zone."""
    _ = auth
    date_raw = str(args.get("date", "")).strip()
    tz_name = str(args.get("time_zone", "Europe/Warsaw")).strip() or "Europe/Warsaw"
    try:
        day = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD (Gregorian)")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        raise HTTPException(status_code=400, detail=f"invalid IANA time_zone: {tz_name!r}")
    top = int(args.get("top", 50))
    top = min(max(top, 1), 50)
    start_local = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    raw = graph_get(
        "/me/calendarView",
        {
            "startDateTime": _graph_calendarview_utc(start_utc),
            "endDateTime": _graph_calendarview_utc(end_utc),
            "$top": str(top),
            "$orderby": "start/dateTime",
            "$select": "id,subject,start,end,organizer,isCancelled,isAllDay,location,showAs",
        },
    )
    data = _enrich_calendar_view_response(raw, default_tz=tz_name)
    target = date_raw[:10]
    vals = data.get("value")
    if isinstance(vals, list):
        filtered: list[Any] = []
        for e in vals:
            if not isinstance(e, dict):
                filtered.append(e)
                continue
            cd = e.get("_jarvis1net_calendar_date")
            if cd is None or cd == target:
                filtered.append(e)
        data["value"] = filtered
        data["_jarvis1net_filtered_to_start_calendar_date"] = target
    return data


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
