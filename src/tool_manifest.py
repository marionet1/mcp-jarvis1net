from __future__ import annotations

GRAPH_TOKEN_PROP = {
    "type": "string",
    "description": (
        "Optional Microsoft Graph OAuth access token. "
        "If omitted, the server uses MCP_GRAPH_ACCESS_TOKEN from the environment."
    ),
}


def with_graph(schema: dict[str, object]) -> dict[str, object]:
    properties = dict(schema.get("properties", {}))  # type: ignore[arg-type]
    properties["graph_access_token"] = GRAPH_TOKEN_PROP
    return {
        "type": "object",
        "properties": properties,
        "required": schema.get("required", []),
    }


mcp_tool_list: list[dict[str, object]] = [
    {"name": "fs_list_directory", "description": "Lists directory contents on the MCP host.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "fs_stat_path", "description": "Checks path metadata: existence, file vs directory, size, mtime.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "fs_read_file", "description": "Reads a text file.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "max_bytes": {"type": "integer"}}, "required": ["path"]}},
    {"name": "fs_write_file", "description": "Creates or overwrites a text file.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "encoding": {"type": "string", "default": "utf-8"}, "create_parents": {"type": "boolean", "default": False}}, "required": ["path", "content"]}},
    {"name": "fs_mkdir", "description": "Creates a directory.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "parents": {"type": "boolean", "default": False}}, "required": ["path"]}},
    {"name": "fs_delete_path", "description": "Deletes a file or an empty directory.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "fs_rename_path", "description": "Renames or moves a file/directory within allowed roots.", "inputSchema": {"type": "object", "properties": {"from_path": {"type": "string"}, "to_path": {"type": "string"}}, "required": ["from_path", "to_path"]}},
    {"name": "shell_run_diagnostic", "description": "Runs a restricted host diagnostic (disk, memory, load, uptime, ping).", "inputSchema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["disk_usage", "memory_usage", "cpu_load", "uptime", "ping"]}, "host": {"type": "string"}, "count": {"type": "integer"}}, "required": ["action"]}},
    {"name": "mcp_refresh_tool_manifest", "description": "Returns the current tool list.", "inputSchema": {"type": "object", "properties": {}, "required": []}},
    {"name": "microsoft_integration_status", "description": "Whether a Graph token is available.", "inputSchema": with_graph({"type": "object", "properties": {}, "required": []})},
    {"name": "microsoft_graph_me", "description": "Graph GET /me.", "inputSchema": with_graph({"type": "object", "properties": {}, "required": []})},
    {"name": "microsoft_mail_list_messages", "description": "Recent messages in Inbox root only.", "inputSchema": with_graph({"type": "object", "properties": {"top": {"type": "integer"}}, "required": []})},
    {"name": "microsoft_mail_list_inbox_tree", "description": "Inbox root + first-level subfolders.", "inputSchema": with_graph({"type": "object", "properties": {"top_per_folder": {"type": "integer"}, "max_child_folders": {"type": "integer"}, "top": {"type": "integer"}}, "required": []})},
    {"name": "microsoft_mail_list_unread_inbox_tree", "description": "Unread in Inbox root + first-level subfolders.", "inputSchema": with_graph({"type": "object", "properties": {"top_per_folder": {"type": "integer"}, "max_child_folders": {"type": "integer"}, "top": {"type": "integer"}}, "required": []})},
    {"name": "microsoft_mail_search_messages", "description": "Graph $search across mail.", "inputSchema": with_graph({"type": "object", "properties": {"query": {"type": "string"}, "top": {"type": "integer"}, "include_body_preview": {"type": "boolean"}, "q": {"type": "string"}}, "required": ["query"]})},
    {"name": "microsoft_mail_mark_read", "description": "PATCH isRead=true for up to 40 ids.", "inputSchema": with_graph({"type": "object", "properties": {"message_ids": {"type": "array", "items": {"type": "string"}}, "mail_folder_id": {"type": "string"}, "folder_id": {"type": "string"}}, "required": ["message_ids"]})},
    {"name": "microsoft_mail_mark_folder_read", "description": "Mark every unread in one folder as read.", "inputSchema": with_graph({"type": "object", "properties": {"mail_folder_id": {"type": "string"}, "folder_id": {"type": "string"}, "top": {"type": "integer"}}, "required": []})},
    {"name": "microsoft_calendar_list_events", "description": "List calendar view in a date window.", "inputSchema": with_graph({"type": "object", "properties": {"top": {"type": "integer"}, "days": {"type": "integer"}, "past_days": {"type": "integer"}}, "required": []})},
    {"name": "microsoft_calendar_events_on_date", "description": "Events whose start maps to one date.", "inputSchema": with_graph({"type": "object", "properties": {"date": {"type": "string"}, "time_zone": {"type": "string"}, "top": {"type": "integer"}}, "required": ["date"]})},
    {"name": "microsoft_onedrive_list_root", "description": "Lists OneDrive root children.", "inputSchema": with_graph({"type": "object", "properties": {}, "required": []})},
    {"name": "microsoft_graph_api", "description": "Low-level Microsoft Graph v1.0 for /me/... paths.", "inputSchema": with_graph({"type": "object", "properties": {"method": {"type": "string", "enum": ["GET", "POST", "PATCH", "PUT", "DELETE"]}, "path": {"type": "string"}, "query": {"type": "object"}, "body": {"type": "object"}}, "required": ["method", "path"]})},
]

