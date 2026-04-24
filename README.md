# mcp.jarvis1.net — HTTP API (MCP-style)

Hosted tools API for **agents and scripts** (for example, function-calling models).  
This README explains **how to use the hosted service**.

> The code is public for transparency and auditability.  
> We provide API utility at `https://mcp.jarvis1.net` as a single hosted instance.

---

## How to get an API key

API keys are issued manually. Contact:

- **DM:** [github.com/marionet1](https://github.com/marionet1)

In your DM, briefly explain your use case (bot, testing, project).  
You will receive a one-time key value (`Bearer ...`) and assigned scopes.

---

## Base URL

```
https://mcp.jarvis1.net
```

(No trailing slash is fine for `MCP_SERVER_URL` in clients.)

---

## Authorization

All tool endpoints and `GET /sse` require this header:

```http
Authorization: Bearer <YOUR_API_KEY>
```

`GET /health` is public (smoke test / monitoring).

---

## Available tools (HTTP)

Paths are relative to the base URL:

| Scope | Method | Path | Description |
|------------------|--------|---------|------|
| key-scoped | GET | `/v1/tools` | Returns tool schemas available for your API key |
| key-scoped | POST | `/v1/tools/call` | Generic tool execution: JSON `{name, arguments}` |
| `meta` | (tool) | `mcp_refresh_tool_manifest` via `/v1/tools/call` | Same payload as `GET /v1/tools` (always fresh; allowed for any valid API key) |
| `filesystem` | GET | `/v1/tools/filesystem/list` | Directory listing (`?path=`) |
| `filesystem` | GET | `/v1/tools/filesystem/stat` | Path metadata (`?path=`) |
| `filesystem` | GET | `/v1/tools/filesystem/read` | Read text file (`?path=`, optional `max_bytes`) |
| `filesystem` | POST | `/v1/tools/filesystem/write` | JSON: `path`, `content`, optional `encoding`, `create_parents` |
| `filesystem` | POST | `/v1/tools/filesystem/mkdir` | JSON: `path`, `parents` |
| `filesystem` | POST | `/v1/tools/filesystem/delete` | JSON: `path` (file or empty directory) |
| `filesystem` | POST | `/v1/tools/filesystem/rename` | JSON: `from_path`, `to_path` |
| `shell` | POST | `/v1/tools/shell/run` | JSON diagnostics action (`disk_usage`, `memory_usage`, `cpu_load`, `uptime`, `ping`) |
| `microsoft` | GET | `/v1/tools/microsoft/oauth/start` | Start delegated Microsoft login (requires Bearer key + `microsoft` scope; returns 302) |
| `microsoft` | GET | `/v1/tools/microsoft/oauth/callback` | OAuth redirect target (public; validates `state`) |
| `microsoft` | (tool) | `microsoft_*` via `/v1/tools/call` | Graph helpers: profile, inbox messages, calendar events, OneDrive root listing |
| `outlook` | GET | `/v1/tools/outlook/status` | Status stub |
| `sse` | GET | `/sse` | SSE stream |

Endpoint access depends on scopes assigned to your key (`filesystem`, `shell`, `outlook`, `microsoft`, `sse`, or `*` for all).  
The `meta` tool `mcp_refresh_tool_manifest` is available to **any valid API key** (it only returns the same filtered manifest as `GET /v1/tools`).  
A `403` scope error means your key does not include the requested permission.

---

## `curl` examples

**Health:**

```bash
curl -sS https://mcp.jarvis1.net/health
```

**List directory (requires key):**

```bash
curl -sS -H "Authorization: Bearer YOUR_KEY" \
  "https://mcp.jarvis1.net/v1/tools/filesystem/list?path=/allowed/service/path"
```

**Read file:**

```bash
curl -sS -H "Authorization: Bearer YOUR_KEY" \
  "https://mcp.jarvis1.net/v1/tools/filesystem/read?path=/path/to/file.txt"
```

**Shell diagnostic (disk usage):**

```bash
curl -sS -X POST "https://mcp.jarvis1.net/v1/tools/shell/run" \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"disk_usage"}'
```

**Get tool manifest (recommended for agents):**

```bash
curl -sS -H "Authorization: Bearer YOUR_KEY" \
  "https://mcp.jarvis1.net/v1/tools"
```

**Call tool generically (recommended for agents):**

```bash
curl -sS -X POST "https://mcp.jarvis1.net/v1/tools/call" \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"shell_run_diagnostic","arguments":{"action":"disk_usage"}}'
```

**Microsoft Graph (operator):** set `MICROSOFT_*` variables in `.env` (see `.env.example`), add **`microsoft`** to the API key scopes, then link an account:

```bash
curl -sS -I -H "Authorization: Bearer YOUR_KEY" \
  "https://mcp.jarvis1.net/v1/tools/microsoft/oauth/start"
```

Follow the `Location` redirect in a browser, sign in, then call tools such as `microsoft_graph_me` via `/v1/tools/call`.

---

## Limits and security

- Keys are stored server-side as **hashes** and cannot be recovered from the database.
- File read/write size limits are enforced on the server.
- Access is restricted to allowed filesystem roots on this hosted instance.
- Microsoft tokens are stored only on the server path from `MICROSOFT_TOKEN_CACHE_PATH` (never commit that file).
