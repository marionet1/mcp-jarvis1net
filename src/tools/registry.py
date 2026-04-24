from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException
from pydantic import BaseModel, Field

from src.deps import ApiKeyAuth
from src.tools.filesystem.routes import (
    delete_path,
    list_directory,
    mkdir,
    read_file,
    rename_path,
    stat_path,
    write_file,
)
from src.tools.filesystem.schemas import DeleteBody, MkdirBody, RenameBody, WriteBody
from src.tools.microsoft import ops as ms_ops
from src.tools.microsoft.graph_context import set_graph_bearer
from src.tools.shell.routes import ShellRunBody, run_shell


@dataclass(frozen=True)
class ToolSpec:
    name: str
    scope: str
    schema: dict[str, Any]
    runner: Callable[[dict[str, Any], ApiKeyAuth], dict[str, Any]]


class ToolCallBody(BaseModel):
    name: str = Field(..., description="Tool function name from /v1/tools/manifest.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool call arguments object.")


def _schema(
    *,
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _fs_list(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    _ = auth
    return list_directory(path=str(args.get("path", ".")))


def _fs_stat(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    if "path" not in args:
        raise HTTPException(status_code=400, detail="Missing required argument: path")
    _ = auth
    return stat_path(path=str(args["path"]))


def _fs_read(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    if "path" not in args:
        raise HTTPException(status_code=400, detail="Missing required argument: path")
    mb = args.get("max_bytes")
    _ = auth
    return read_file(path=str(args["path"]), max_bytes=int(mb) if mb is not None else None)


def _fs_write(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    if "path" not in args:
        raise HTTPException(status_code=400, detail="Missing required argument: path")
    body = WriteBody(
        path=str(args["path"]),
        content=str(args.get("content", "")),
        encoding=str(args.get("encoding") or "utf-8"),
        create_parents=bool(args.get("create_parents", False)),
    )
    _ = auth
    return write_file(body)


def _fs_mkdir(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    if "path" not in args:
        raise HTTPException(status_code=400, detail="Missing required argument: path")
    _ = auth
    return mkdir(MkdirBody(path=str(args["path"]), parents=bool(args.get("parents", False))))


def _fs_delete(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    if "path" not in args:
        raise HTTPException(status_code=400, detail="Missing required argument: path")
    _ = auth
    return delete_path(DeleteBody(path=str(args["path"])))


def _fs_rename(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    if "from_path" not in args or "to_path" not in args:
        raise HTTPException(status_code=400, detail="Missing required arguments: from_path, to_path")
    _ = auth
    return rename_path(RenameBody(from_path=str(args["from_path"]), to_path=str(args["to_path"])))


def _shell_run(args: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    if "action" not in args:
        raise HTTPException(status_code=400, detail="Missing required argument: action")
    body = ShellRunBody(
        action=str(args["action"]),
        host=str(args["host"]) if args.get("host") is not None else None,
        count=int(args.get("count", 2)),
    )
    _ = auth
    return run_shell(body)


def _mcp_refresh_tool_manifest(_: dict[str, Any], auth: ApiKeyAuth) -> dict[str, Any]:
    """Returns the current tool manifest for this API key (same source as GET /v1/tools)."""
    tools = manifest_for_auth(auth)
    return {"tools": tools, "count": len(tools)}


TOOL_SPECS: dict[str, ToolSpec] = {
    "fs_list_directory": ToolSpec(
        name="fs_list_directory",
        scope="filesystem",
        schema=_schema(
            name="fs_list_directory",
            description=(
                "Lists directory contents on the MCP server (file/subdirectory names with is_dir flag). "
                "Use this first when the user asks what is inside a folder, searches for a file location, "
                "or before proposing a path so names are not guessed. It does not read file content."
            ),
            properties={
                "path": {
                    "type": "string",
                    "description": "Directory path, e.g. /home/jump or a subdirectory.",
                }
            },
            required=["path"],
        ),
        runner=_fs_list,
    ),
    "fs_stat_path": ToolSpec(
        name="fs_stat_path",
        scope="filesystem",
        schema=_schema(
            name="fs_stat_path",
            description="Checks path metadata: existence, file vs directory, size, mtime.",
            properties={"path": {"type": "string", "description": "Absolute or relative path to inspect."}},
            required=["path"],
        ),
        runner=_fs_stat,
    ),
    "fs_read_file": ToolSpec(
        name="fs_read_file",
        scope="filesystem",
        schema=_schema(
            name="fs_read_file",
            description="Reads text file content from the server (UTF-8 with replacement).",
            properties={
                "path": {"type": "string", "description": "File path to read."},
                "max_bytes": {"type": "integer", "description": "Optional byte limit."},
            },
            required=["path"],
        ),
        runner=_fs_read,
    ),
    "fs_write_file": ToolSpec(
        name="fs_write_file",
        scope="filesystem",
        schema=_schema(
            name="fs_write_file",
            description="Creates or overwrites a text file on the server.",
            properties={
                "path": {"type": "string", "description": "Target file path."},
                "content": {"type": "string", "description": "Full replacement content."},
                "encoding": {"type": "string", "description": "Write encoding.", "default": "utf-8"},
                "create_parents": {
                    "type": "boolean",
                    "description": "Create missing parent directories.",
                    "default": False,
                },
            },
            required=["path", "content"],
        ),
        runner=_fs_write,
    ),
    "fs_mkdir": ToolSpec(
        name="fs_mkdir",
        scope="filesystem",
        schema=_schema(
            name="fs_mkdir",
            description="Creates a directory (single level or recursive with parents=true).",
            properties={
                "path": {"type": "string", "description": "New directory path."},
                "parents": {"type": "boolean", "description": "Create all missing path segments.", "default": False},
            },
            required=["path"],
        ),
        runner=_fs_mkdir,
    ),
    "fs_delete_path": ToolSpec(
        name="fs_delete_path",
        scope="filesystem",
        schema=_schema(
            name="fs_delete_path",
            description="Deletes a single file or an empty directory.",
            properties={"path": {"type": "string", "description": "File or empty directory to delete."}},
            required=["path"],
        ),
        runner=_fs_delete,
    ),
    "fs_rename_path": ToolSpec(
        name="fs_rename_path",
        scope="filesystem",
        schema=_schema(
            name="fs_rename_path",
            description="Renames or moves a file/directory inside allowed paths.",
            properties={
                "from_path": {"type": "string", "description": "Existing source path."},
                "to_path": {"type": "string", "description": "New destination path."},
            },
            required=["from_path", "to_path"],
        ),
        runner=_fs_rename,
    ),
    "shell_run_diagnostic": ToolSpec(
        name="shell_run_diagnostic",
        scope="shell",
        schema=_schema(
            name="shell_run_diagnostic",
            description="Runs a restricted server diagnostic command through MCP shell tool.",
            properties={
                "action": {
                    "type": "string",
                    "enum": ["disk_usage", "memory_usage", "cpu_load", "uptime", "ping"],
                    "description": "Diagnostic action to run on the MCP server.",
                },
                "host": {"type": "string", "description": "Target host for ping."},
                "count": {"type": "integer", "description": "Ping packet count (1..4).", "default": 2},
            },
            required=["action"],
        ),
        runner=_shell_run,
    ),
    "microsoft_integration_status": ToolSpec(
        name="microsoft_integration_status",
        scope="microsoft",
        schema=_schema(
            name="microsoft_integration_status",
            description=(
                "Returns whether this request includes a Microsoft Graph bearer token (X-Graph-Authorization). "
                "MCP does not configure Azure; tokens come from the agent. "
                "**Optional diagnostic only** (e.g. user asks if Graph auth is wired, or after a missing-token error). "
                "**Do not** call this as a routine preamble before every other microsoft_* tool — call the tool that "
                "actually performs the task (e.g. `microsoft_graph_me`, `microsoft_graph_api`)."
            ),
            properties={},
            required=[],
        ),
        runner=ms_ops.microsoft_integration_status,
    ),
    "microsoft_graph_me": ToolSpec(
        name="microsoft_graph_me",
        scope="microsoft",
        schema=_schema(
            name="microsoft_graph_me",
            description="Reads the signed-in Microsoft profile via Graph GET /me.",
            properties={},
            required=[],
        ),
        runner=ms_ops.microsoft_graph_me,
    ),
    "microsoft_mail_list_messages": ToolSpec(
        name="microsoft_mail_list_messages",
        scope="microsoft",
        schema=_schema(
            name="microsoft_mail_list_messages",
            description="Lists recent messages from the signed-in user's Inbox (metadata only).",
            properties={
                "top": {
                    "type": "integer",
                    "description": "Max messages to return (1..50, default 10).",
                    "default": 10,
                }
            },
            required=[],
        ),
        runner=ms_ops.microsoft_mail_list_messages,
    ),
    "microsoft_mail_mark_read": ToolSpec(
        name="microsoft_mail_mark_read",
        scope="microsoft",
        schema=_schema(
            name="microsoft_mail_mark_read",
            description=(
                "Marks many mail messages as read: PATCHes `{\"isRead\": true}` per id. "
                "Primary path is **PATCH /me/messages/{id}** (Graph canonical). Optional `mail_folder_id` is only used "
                "as a **fallback** if that PATCH returns 404. Pass every `value[].id` from your GET (up to 40). "
                "To mark **all** unread in one folder without manual paging, use **`microsoft_mail_mark_folder_read`** instead. "
                "Requires Mail.ReadWrite."
            ),
            properties={
                "message_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Graph message id strings from a prior messages GET (value[].id).",
                    "minItems": 1,
                    "maxItems": 40,
                },
                "mail_folder_id": {
                    "type": "string",
                    "description": "Optional folder id — used only if PATCH /me/messages/{id} returns 404 (retry folder-scoped).",
                },
            },
            required=["message_ids"],
        ),
        runner=ms_ops.microsoft_mail_mark_read,
    ),
    "microsoft_mail_mark_folder_read": ToolSpec(
        name="microsoft_mail_mark_folder_read",
        scope="microsoft",
        schema=_schema(
            name="microsoft_mail_mark_folder_read",
            description=(
                "Marks **every** unread message in one mail folder as read: pages through `isRead eq false` results "
                "via **@odata.nextLink** (no `$skip`), then PATCHes each id with `/me/messages/{id}`. "
                "Use when the user wants the whole folder cleared without listing ids manually. "
                "For multiple folders, call once per `mail_folder_id`. Max ~500 messages per call. Requires Mail.ReadWrite."
            ),
            properties={
                "mail_folder_id": {
                    "type": "string",
                    "description": "Graph mailFolder id (same as in .../mailFolders/{id}/messages).",
                },
                "top": {
                    "type": "integer",
                    "description": "Page size for each GET (1..50, default 50).",
                    "default": 50,
                },
            },
            required=["mail_folder_id"],
        ),
        runner=ms_ops.microsoft_mail_mark_folder_read,
    ),
    "microsoft_calendar_list_events": ToolSpec(
        name="microsoft_calendar_list_events",
        scope="microsoft",
        schema=_schema(
            name="microsoft_calendar_list_events",
            description="Lists upcoming calendar events for the signed-in user (metadata).",
            properties={
                "top": {
                    "type": "integer",
                    "description": "Max events to return (1..50, default 10).",
                    "default": 10,
                }
            },
            required=[],
        ),
        runner=ms_ops.microsoft_calendar_list_events,
    ),
    "microsoft_onedrive_list_root": ToolSpec(
        name="microsoft_onedrive_list_root",
        scope="microsoft",
        schema=_schema(
            name="microsoft_onedrive_list_root",
            description="Lists children of the signed-in user's OneDrive root folder (up to 50 items).",
            properties={},
            required=[],
        ),
        runner=ms_ops.microsoft_onedrive_list_root,
    ),
    "microsoft_graph_api": ToolSpec(
        name="microsoft_graph_api",
        scope="microsoft",
        schema=_schema(
            name="microsoft_graph_api",
            description=(
                "Low-level Microsoft Graph v1.0 call for the signed-in user. "
                "`path` must start with `/me` or `/me/...` (mailFolders, messages, sendMail, calendar/events, drive, …). "
                "Use GET+query for reads; POST/PATCH/DELETE+body for writes (e.g. send mail, create/update/delete event, upload file). "
                "For listing recent messages without full content, prefer `$select=id,subject,receivedDateTime,from` (omit body/bodyPreview) "
                "so responses stay small. Requires matching delegated scopes on the token (Mail.ReadWrite, Mail.Send, Calendars.ReadWrite, Files.ReadWrite.All)."
            ),
            properties={
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PATCH", "PUT", "DELETE"],
                    "description": "HTTP method.",
                },
                "path": {
                    "type": "string",
                    "description": "Graph path starting with /me or /me/...",
                },
                "query": {
                    "type": "object",
                    "description": "Optional query parameters ($top, $select, etc.).",
                    "additionalProperties": True,
                },
                "body": {
                    "type": "object",
                    "description": (
                        "JSON object for POST/PATCH/PUT (e.g. sendMail message payload). "
                        "To mark a message read: PATCH /me/messages/{id} with {\"isRead\": true} (boolean, exact key isRead)."
                    ),
                    "additionalProperties": True,
                },
            },
            required=["method", "path"],
        ),
        runner=ms_ops.microsoft_graph_api,
    ),
    "mcp_refresh_tool_manifest": ToolSpec(
        name="mcp_refresh_tool_manifest",
        scope="meta",
        schema=_schema(
            name="mcp_refresh_tool_manifest",
            description=(
                "Fetches the current MCP tool manifest for this API key from the server (same as GET /v1/tools). "
                "Always call this when the user asks which tools exist, what capabilities are available, "
                "or wants an up-to-date tool list. Do not answer from memory or earlier turns."
            ),
            properties={},
            required=[],
        ),
        runner=_mcp_refresh_tool_manifest,
    ),
}


def manifest_for_auth(auth: ApiKeyAuth) -> list[dict[str, Any]]:
    tools = [spec.schema for spec in TOOL_SPECS.values() if auth.allows(spec.scope)]
    tools.sort(key=lambda t: str(t["function"]["name"]))
    return tools


def run_tool_call(
    name: str,
    arguments: dict[str, Any],
    auth: ApiKeyAuth,
    *,
    graph_access_token: str | None = None,
) -> dict[str, Any]:
    spec = TOOL_SPECS.get(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
    if not auth.allows(spec.scope):
        raise HTTPException(status_code=403, detail=f"API key is not allowed to use: {spec.scope}")
    set_graph_bearer(graph_access_token)
    try:
        return spec.runner(arguments or {}, auth)
    finally:
        set_graph_bearer(None)

