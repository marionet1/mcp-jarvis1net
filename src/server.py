from __future__ import annotations

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from rag.config import get_rag_config
from rag.service import (
    rag_delete_document,
    rag_get_tool_execution_guidance,
    rag_list_documents,
    rag_list_tool_catalog,
    rag_refresh_tool_catalog,
    rag_search_tool_guidance,
    rag_upsert_document,
)
from tools.filesystem import fs_delete_path, fs_list_directory, fs_mkdir, fs_read_file, fs_rename_path, fs_stat_path, fs_write_file
from tools.filesystem.path_guard import PathError
from tools.manifest import mcp_tool_list
from tools.microsoft import GraphHttpError, run_with_graph_token
from tools.microsoft import (
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
from tools.shell import shell_run_diagnostic

load_dotenv()
mcp = FastMCP("mcp-jarvis1net")


def _run_microsoft(handler, args: dict[str, object]) -> dict[str, object]:
    token = resolve_graph_token(args)
    clean = strip_token_copy(args)
    return run_with_graph_token(token, lambda: handler(clean))


def _with_guidance(tool_name: str, intent: str, result: dict[str, object], provider: str = "microsoft") -> dict[str, object]:
    enabled = get_rag_config().guidance_auto
    if not enabled:
        return result
    guidance = rag_get_tool_execution_guidance(
        tool_name=tool_name,
        intent=intent,
        provider=provider,
        top_k=3,
    )
    enriched = dict(result)
    enriched["rag_guidance"] = guidance
    return enriched


@mcp.tool(name="fs_list_directory")
def tool_fs_list_directory(path: str) -> dict[str, object]:
    result = fs_list_directory(path)
    return _with_guidance("fs_list_directory", f"list directory content for path={path}", result, provider="internal")


@mcp.tool(name="fs_stat_path")
def tool_fs_stat_path(path: str) -> dict[str, object]:
    result = fs_stat_path(path)
    return _with_guidance("fs_stat_path", f"stat path metadata for path={path}", result, provider="internal")


@mcp.tool(name="fs_read_file")
def tool_fs_read_file(path: str, max_bytes: int | None = None) -> dict[str, object]:
    result = fs_read_file(path, max_bytes)
    return _with_guidance("fs_read_file", f"read file path={path} max_bytes={max_bytes}", result, provider="internal")


@mcp.tool(name="fs_write_file")
def tool_fs_write_file(path: str, content: str, encoding: str = "utf-8", create_parents: bool = False) -> dict[str, object]:
    result = fs_write_file(path, content, encoding, create_parents)
    return _with_guidance("fs_write_file", f"write file path={path} encoding={encoding} create_parents={create_parents}", result, provider="internal")


@mcp.tool(name="fs_mkdir")
def tool_fs_mkdir(path: str, parents: bool = False) -> dict[str, object]:
    result = fs_mkdir(path, parents)
    return _with_guidance("fs_mkdir", f"create directory path={path} parents={parents}", result, provider="internal")


@mcp.tool(name="fs_delete_path")
def tool_fs_delete_path(path: str) -> dict[str, object]:
    result = fs_delete_path(path)
    return _with_guidance("fs_delete_path", f"delete file or directory path={path}", result, provider="internal")


@mcp.tool(name="fs_rename_path")
def tool_fs_rename_path(from_path: str, to_path: str) -> dict[str, object]:
    result = fs_rename_path(from_path, to_path)
    return _with_guidance("fs_rename_path", f"rename path from={from_path} to={to_path}", result, provider="internal")


@mcp.tool(name="shell_run_diagnostic")
def tool_shell_run_diagnostic(action: str, host: str | None = None, count: int | None = None) -> dict[str, object]:
    result = shell_run_diagnostic(action, host, count)
    return _with_guidance("shell_run_diagnostic", f"run diagnostic action={action} host={host} count={count}", result, provider="internal")


@mcp.tool(name="mcp_refresh_tool_manifest")
def tool_mcp_refresh_tool_manifest() -> dict[str, object]:
    tools = sorted(mcp_tool_list, key=lambda t: str(t["name"]))
    return {"tools": tools, "count": len(tools)}


@mcp.tool(name="rag_refresh_tool_catalog")
def tool_rag_refresh_tool_catalog() -> dict[str, object]:
    return rag_refresh_tool_catalog(mcp_tool_list)


@mcp.tool(name="rag_list_tool_catalog")
def tool_rag_list_tool_catalog(tool_family: str | None = None) -> dict[str, object]:
    return rag_list_tool_catalog(tool_family)


@mcp.tool(name="rag_upsert_document")
def tool_rag_upsert_document(
    doc_id: str,
    title: str,
    content: str,
    tool_family: str,
    tool_name: str | None = None,
    provider: str = "microsoft",
    doc_type: str = "reference",
    source_url: str | None = None,
    version: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    return rag_upsert_document(
        doc_id=doc_id,
        title=title,
        content=content,
        tool_family=tool_family,
        tool_name=tool_name,
        provider=provider,
        doc_type=doc_type,
        source_url=source_url,
        version=version,
        tags=tags,
    )


@mcp.tool(name="rag_delete_document")
def tool_rag_delete_document(doc_id: str) -> dict[str, object]:
    return rag_delete_document(doc_id)


@mcp.tool(name="rag_list_documents")
def tool_rag_list_documents(
    tool_family: str | None = None,
    tool_name: str | None = None,
    provider: str | None = None,
    doc_type: str | None = None,
    limit: int = 100,
) -> dict[str, object]:
    return rag_list_documents(tool_family, tool_name, provider, doc_type, limit)


@mcp.tool(name="rag_search_tool_guidance")
def tool_rag_search_tool_guidance(
    query: str,
    tool_family: str | None = None,
    tool_name: str | None = None,
    provider: str | None = None,
    top_k: int = 5,
    min_score: float = 0.2,
    doc_type: str | None = None,
) -> dict[str, object]:
    return rag_search_tool_guidance(query, tool_family, tool_name, provider, top_k, min_score, doc_type)


@mcp.tool(name="rag_get_tool_execution_guidance")
def tool_rag_get_tool_execution_guidance(
    tool_name: str,
    intent: str,
    provider: str | None = None,
    top_k: int = 3,
) -> dict[str, object]:
    return rag_get_tool_execution_guidance(tool_name, intent, provider, top_k)


@mcp.tool(name="microsoft_integration_status")
def tool_microsoft_integration_status(graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_integration_status, {"graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_integration_status", "check microsoft graph integration status", result)


@mcp.tool(name="microsoft_graph_me")
def tool_microsoft_graph_me(graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_graph_me, {"graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_graph_me", "read signed-in microsoft profile from /me", result)


@mcp.tool(name="microsoft_mail_list_messages")
def tool_microsoft_mail_list_messages(top: int = 10, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_mail_list_messages, {"top": top, "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_mail_list_messages", f"list inbox messages with top={top}", result)


@mcp.tool(name="microsoft_mail_list_inbox_tree")
def tool_microsoft_mail_list_inbox_tree(top_per_folder: int = 10, max_child_folders: int = 15, top: int | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_mail_list_inbox_tree, {"top_per_folder": top_per_folder, "max_child_folders": max_child_folders, "top": top if top is not None else top_per_folder, "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_mail_list_inbox_tree", f"list inbox tree with top_per_folder={top_per_folder} max_child_folders={max_child_folders}", result)


@mcp.tool(name="microsoft_mail_list_unread_inbox_tree")
def tool_microsoft_mail_list_unread_inbox_tree(top_per_folder: int = 25, max_child_folders: int = 15, top: int | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_mail_list_unread_inbox_tree, {"top_per_folder": top_per_folder, "max_child_folders": max_child_folders, "top": top if top is not None else top_per_folder, "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_mail_list_unread_inbox_tree", f"list unread inbox tree with top_per_folder={top_per_folder} max_child_folders={max_child_folders}", result)


@mcp.tool(name="microsoft_mail_search_messages")
def tool_microsoft_mail_search_messages(query: str, top: int = 20, include_body_preview: bool = True, q: str | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_mail_search_messages, {"query": query, "top": top, "include_body_preview": include_body_preview, "q": q or query, "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_mail_search_messages", f"search mail query={query} top={top}", result)


@mcp.tool(name="microsoft_mail_mark_read")
def tool_microsoft_mail_mark_read(message_ids: list[str], mail_folder_id: str | None = None, folder_id: str | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_mail_mark_read, {"message_ids": message_ids, "mail_folder_id": mail_folder_id or "", "folder_id": folder_id or "", "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_mail_mark_read", f"mark specific messages as read count={len(message_ids)}", result)


@mcp.tool(name="microsoft_mail_mark_folder_read")
def tool_microsoft_mail_mark_folder_read(mail_folder_id: str | None = None, folder_id: str | None = None, top: int = 50, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_mail_mark_folder_read, {"mail_folder_id": mail_folder_id or "", "folder_id": folder_id or "", "top": top, "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_mail_mark_folder_read", f"mark folder read folder_id={mail_folder_id or folder_id} top={top}", result)


@mcp.tool(name="microsoft_calendar_list_events")
def tool_microsoft_calendar_list_events(top: int = 25, days: int = 56, past_days: int = 1, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_calendar_list_events, {"top": top, "days": days, "past_days": past_days, "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_calendar_list_events", f"list calendar events top={top} days={days} past_days={past_days}", result)


@mcp.tool(name="microsoft_calendar_events_on_date")
def tool_microsoft_calendar_events_on_date(date: str, time_zone: str = "Europe/Warsaw", top: int = 50, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_calendar_events_on_date, {"date": date, "time_zone": time_zone, "top": top, "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_calendar_events_on_date", f"get calendar events for date={date} time_zone={time_zone} top={top}", result)


@mcp.tool(name="microsoft_onedrive_list_root")
def tool_microsoft_onedrive_list_root(graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_onedrive_list_root, {"graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_onedrive_list_root", "list onedrive root children", result)


@mcp.tool(name="microsoft_graph_api")
def tool_microsoft_graph_api(method: str, path: str, query: dict[str, object] | None = None, body: dict[str, object] | list[object] | None = None, graph_access_token: str | None = None) -> dict[str, object]:
    result = _run_microsoft(microsoft_graph_api, {"method": method, "path": path, "query": query or {}, "body": body, "graph_access_token": graph_access_token or ""})
    return _with_guidance("microsoft_graph_api", f"call graph api method={method} path={path}", result)


def main() -> None:
    try:
        mcp.run(transport="stdio")
    except PathError as exc:
        raise RuntimeError({"ok": False, "error": str(exc), "code": exc.code}) from exc
    except GraphHttpError as exc:
        raise RuntimeError({"ok": False, "error": str(exc), "http_status": exc.status_code}) from exc


if __name__ == "__main__":
    main()

