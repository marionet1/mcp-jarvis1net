import json
import os
from typing import Iterator

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse

from src.deps import DATABASE_URL, ApiKeyAuth, ensure_db_schema, require_api_key
from src.tools.filesystem.routes import router as filesystem_router
from src.tools.microsoft.legacy_callback import router as microsoft_legacy_callback_router
from src.tools.routes import router as tools_router
from src.tools.shell.routes import router as shell_router

APP_NAME = os.getenv("MCP_SERVER_NAME", "mcp-jarvis1net")

app = FastAPI(
    title=APP_NAME,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(filesystem_router)
app.include_router(shell_router)
app.include_router(microsoft_legacy_callback_router)
app.include_router(tools_router)


@app.on_event("startup")
def on_startup() -> None:
    if DATABASE_URL:
        ensure_db_schema()


@app.get("/", response_class=PlainTextResponse)
def home() -> str:
    return "Hello jarvis1net"


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": APP_NAME}


@app.get("/sse")
def sse_ping(auth: ApiKeyAuth = Depends(require_api_key)) -> StreamingResponse:
    if not auth.allows("sse"):
        raise HTTPException(status_code=403, detail="API key is not allowed to use SSE (add sse or * to scopes).")
    owner = auth.owner_name

    def event_stream() -> Iterator[str]:
        payload = {"service": APP_NAME, "owner": owner, "message": "sse-online"}
        yield f"event: hello\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
