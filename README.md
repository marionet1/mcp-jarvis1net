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

## Environment variables (`.env`)

- `MCP_ALLOWED_ROOTS` - comma-separated filesystem roots allowed for `fs_*` tools
- `MCP_GRAPH_ACCESS_TOKEN` - default Microsoft Graph token (optional)
- `MCP_MAX_READ_BYTES` - max file read size
- `MCP_MAX_WRITE_BYTES` - max file write size
- `MCP_SHELL_TIMEOUT_SEC` - timeout for shell diagnostic tools
- `OPENROUTER_API_KEY` - embedding API key (required when backend is `qdrant`)
- `RAG_EMBED_API_KEY` - optional dedicated embedding key (overrides `OPENROUTER_API_KEY`)
- `QDRANT_API_KEY` - optional Qdrant auth secret (if enabled)

## RAG configuration file

RAG runtime settings now live in:
- `config/rag_config.json`

Example fields:
- `rag_root`
- `backend`
- `qdrant_url`
- `qdrant_collection`
- `qdrant_api_key_env`
- `openrouter_base_url`
- `embed_model`
- `guidance_auto`

## Main tool groups

- `fs_*` - filesystem operations
- `shell_run_diagnostic` - host diagnostics (disk/memory/cpu/uptime/ping)
- `microsoft_*` - Microsoft Graph operations
- `mcp_refresh_tool_manifest`
- `rag_*` - local tool-guidance RAG index management and search

## Tool-guidance RAG (local)

This server includes a lightweight local RAG layer for tool execution guidance.
You can store documentation snippets per tool family/tool name and search them during runtime.

Primary RAG tools:
- `rag_refresh_tool_catalog`
- `rag_list_tool_catalog`
- `rag_upsert_document`
- `rag_delete_document`
- `rag_list_documents`
- `rag_search_tool_guidance`
- `rag_get_tool_execution_guidance`

Recommended first setup:
1. Run `rag_refresh_tool_catalog` once.
2. Ingest Microsoft docs into `tool_family=microsoft` (and optionally specific `tool_name`).
3. Add internal docs for `tool_family=filesystem` and `tool_family=shell`.

## Production RAG setup (Qdrant + API embeddings)

1. Set environment variables in the root stack `.env`:
   - one key variable: `OPENROUTER_API_KEY` or `RAG_EMBED_API_KEY`
   - optional: `QDRANT_API_KEY`

2. Configure non-secret RAG settings in:
   - `config/rag_config.json`

3. Start stack services:

```bash
docker compose up -d --build
```

4. Ingest source sets:

```bash
cd mcp-jarvis1net
python3 scripts/ingest_docs.py --source scripts/sources_microsoft.yaml --source scripts/sources_internal.yaml
```

5. Run retrieval evaluation:

```bash
python3 tests/rag_eval/evaluate_rag.py
```

## Ingest pipeline files

- `scripts/ingest_docs.py` - fetch/normalize/upsert pipeline
- `scripts/sources_microsoft.yaml` - official Microsoft Graph source list
- `scripts/sources_internal.yaml` - filesystem/shell internal playbooks

## Operations runbook

### Reindex workflow
1. Update YAML source files.
2. Run `ingest_docs.py` again.
3. Run `tests/rag_eval/evaluate_rag.py`.

### Weekly and monthly cadence
- Weekly: incremental ingest from source YAML.
- Monthly: full refresh (`rag_refresh_tool_catalog` + full ingest + eval).

### Backup and restore (Qdrant volume)
- Backup:
  - `docker run --rm -v stack-jarvis1net_qdrant_data:/data -v "$PWD":/backup alpine tar czf /backup/qdrant-backup.tgz -C /data .`
- Restore:
  - stop stack,
  - recreate volume data from archive,
  - start stack and run eval.

### Monitoring and telemetry
- Search telemetry is written to `<rag_root>/telemetry.jsonl` from `config/rag_config.json`.
- Track `fallback_used`, `elapsed_ms`, `result_count` trends over time.

