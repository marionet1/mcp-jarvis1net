from __future__ import annotations

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from filesystem import fs_delete_path, fs_list_directory, fs_mkdir, fs_read_file, fs_rename_path, fs_stat_path, fs_write_file
from graph import GraphHttpError, run_with_graph_token
from graph_ops import (
    microsoft_calendar_events_on_date,
    microsoft_calendar_list_events,
    microsoft_graph_api,
    microsoft_graph_me,
    microsoft_integration_status,
    microsoft_mail_list_inbox_tree,
    microsoft_mail_list_messages,
    microsoft_mail_list_unread_inbox_tree,
    microsoft_mail_mark_folder_read,
    microsoft_mail_mark_read,
    microsoft_mail_search_messages,
    microsoft_onedrive_list_root,
    resolve_graph_token,
    strip_token_copy,
)
from paths import PathError
from shell_tools import shell_run_diagnostic
from tool_manifest import mcp_tool_list

load_dotenv()
mcp = FastMCP("mcp-jarvis1net")


def _run_microsoft(handler, args: dict[str, object]) -> dict[str, object]:
    token = resolve_graph_token(args)
    clean = strip_token_copy(args)
    return run_with_graph_token(token, lambda: handler(clean))


@mcp.tool(name="fs_list_directory")
def tool_fs_list_directory(path: str) -> dict[str, object]:
    return fs_list_directory(path)


@mcp.tool(name="fs_stat_path")
def tool_fs_stat_path(path: str) -> dict[str, object]:
    return fs_stat_path(path)


@mcp.tool(name="fs_read_file")
def tool_fs_read_file(path: str, max_bytes: int | None = None) -> dict[str, object]:
    return fs_read_file(path, max_bytes)


@mcp.tool(name="fs_write_file")
def tool_fs_write_file(path: str, content: str, encoding: str = "utf-8", create_parents: bool = False) -> dict[str, object]:
    return fs_write_file(path, content, encoding, create_parents)


@mcp.tool(name="fs_mkdir")
def tool_fs_mkdir(path: str, parents: bool = False) -> dict[str, object]:
    return fs_mkdir(path, parents)


@mcp.tool(name="fs_delete_path")
def tool_fs_delete_path(path: str) -> dict[str, object]:
    return fs_delete_path(path)


@mcp.tool(name="fs_rename_path")
def tool_fs_rename_path(from_path: str, to_path: str) -> dict[str, object]:
    return fs_rename_path(from_path, to_path)


@mcp.tool(name="shell_run_diagnostic")
def tool_shell_run_diagnostic(action: str, host: str | None = None, count: int | None = None) -> dict[str, object]:
    return shell_run_diagnostic(action, host, count)


@mcp.tool(name="mcp_refresh_tool_manifest")
def tool_mcp_refresh_tool_manifest() -> dict[str, object]:
    tools = sorted(mcp_tool_list, key=lambda t: str(t["name"]))
    return {"tools": tools, "count": len(tools)}


@mcp.tool(name="microsoft_integration_status")
def tool_microsoft_integration_status(graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_integration_status, {"graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_graph_me")
def tool_microsoft_graph_me(graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_graph_me, {"graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_mail_list_messages")
def tool_microsoft_mail_list_messages(top: int = 10, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_mail_list_messages, {"top": top, "graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_mail_list_inbox_tree")
def tool_microsoft_mail_list_inbox_tree(top_per_folder: int = 10, max_child_folders: int = 15, top: int | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_mail_list_inbox_tree, {"top_per_folder": top_per_folder, "max_child_folders": max_child_folders, "top": top if top is not None else top_per_folder, "graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_mail_list_unread_inbox_tree")
def tool_microsoft_mail_list_unread_inbox_tree(top_per_folder: int = 25, max_child_folders: int = 15, top: int | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_mail_list_unread_inbox_tree, {"top_per_folder": top_per_folder, "max_child_folders": max_child_folders, "top": top if top is not None else top_per_folder, "graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_mail_search_messages")
def tool_microsoft_mail_search_messages(query: str, top: int = 20, include_body_preview: bool = True, q: str | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_mail_search_messages, {"query": query, "top": top, "include_body_preview": include_body_preview, "q": q or query, "graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_mail_mark_read")
def tool_microsoft_mail_mark_read(message_ids: list[str], mail_folder_id: str | None = None, folder_id: str | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_mail_mark_read, {"message_ids": message_ids, "mail_folder_id": mail_folder_id or "", "folder_id": folder_id or "", "graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_mail_mark_folder_read")
def tool_microsoft_mail_mark_folder_read(mail_folder_id: str | None = None, folder_id: str | None = None, top: int = 50, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_mail_mark_folder_read, {"mail_folder_id": mail_folder_id or "", "folder_id": folder_id or "", "top": top, "graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_calendar_list_events")
def tool_microsoft_calendar_list_events(top: int = 25, days: int = 56, past_days: int = 1, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_calendar_list_events, {"top": top, "days": days, "past_days": past_days, "graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_calendar_events_on_date")
def tool_microsoft_calendar_events_on_date(date: str, time_zone: str = "Europe/Warsaw", top: int = 50, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_calendar_events_on_date, {"date": date, "time_zone": time_zone, "top": top, "graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_onedrive_list_root")
def tool_microsoft_onedrive_list_root(graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_onedrive_list_root, {"graph_access_token": graph_access_token or ""})


@mcp.tool(name="microsoft_graph_api")
def tool_microsoft_graph_api(method: str, path: str, query: dict[str, object] | None = None, body: dict[str, object] | list[object] | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    return _run_microsoft(microsoft_graph_api, {"method": method, "path": path, "query": query or {}, "body": body, "graph_access_token": graph_access_token or ""})


def main() -> None:
    try:
        mcp.run(transport="stdio")
    except PathError as exc:
        raise RuntimeError({"ok": False, "error": str(exc), "code": exc.code}) from exc
    except GraphHttpError as exc:
        raise RuntimeError({"ok": False, "error": str(exc), "http_status": exc.status_code}) from exc


if __name__ == "__main__":
    main()

