# mcp-jarvis1net

Python implementation of a Model Context Protocol (MCP) server over stdio.

## Requirements

- Python 3.11+

## Local installation

Linux/macOS:

```bash
cd mcp-jarvis1net
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell:

```powershell
cd mcp-jarvis1net
py -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -e .
```

## Run

```bash
python3 src/server.py
```

## MCP client configuration example

```jsonc
{
  "mcpServers": {
    "jarvis1net-tools": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp-jarvis1net/src/server.py"],
      "env": {
        "MCP_ALLOWED_ROOTS": "/home/you/project"
      }
    }
  }
}
```

## Environment variables

- `MCP_ALLOWED_ROOTS` - comma-separated filesystem roots allowed for `fs_*` tools
- `MCP_GRAPH_ACCESS_TOKEN` - default Microsoft Graph token (optional)
- `MCP_MAX_READ_BYTES` - max file read size
- `MCP_MAX_WRITE_BYTES` - max file write size
- `MCP_SHELL_TIMEOUT_SEC` - timeout for shell diagnostic tools

## Main tool groups

- `fs_*` - filesystem operations
- `shell_run_diagnostic` - host diagnostics (disk/memory/cpu/uptime/ping)
- `microsoft_*` - Microsoft Graph operations
- `mcp_refresh_tool_manifest`

