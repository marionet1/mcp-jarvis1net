import hashlib
import os
from dataclasses import dataclass
from typing import Callable

import psycopg
from fastapi import Depends, Header, HTTPException

DATABASE_URL = os.getenv("MCP_DATABASE_URL", "")
REQUIRE_API_KEY = os.getenv("MCP_REQUIRE_API_KEY", "true").lower() == "true"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def api_key_hash(plain: str) -> str:
    """SHA-256 hex used for api_keys.key_hash storage."""
    return _sha256(plain)


def db_conn() -> psycopg.Connection:
    if not DATABASE_URL:
        raise RuntimeError("MCP_DATABASE_URL is missing.")
    return psycopg.connect(DATABASE_URL)


@dataclass(frozen=True)
class ApiKeyAuth:
    owner_name: str
    scopes_raw: str

    def allows(self, module: str) -> bool:
        """Checks scope for a module (filesystem/shell/outlook/microsoft/sse, * / all). ``meta`` is allowed for any valid API key."""
        if module == "meta":
            return True
        s = (self.scopes_raw or "").strip()
        if not s or s == "*":
            return True
        parts = {p.strip() for p in s.split(",") if p.strip()}
        if "*" in parts or "all" in parts:
            return True
        if module in parts:
            return True
        if f"{module}:*" in parts:
            return True
        return False


def ensure_db_schema() -> None:
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id BIGSERIAL PRIMARY KEY,
                    key_hash TEXT UNIQUE NOT NULL,
                    owner_name TEXT NOT NULL,
                    scopes TEXT NOT NULL DEFAULT '*',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_used_at TIMESTAMPTZ NULL
                );
                """
            )
        conn.commit()


def require_api_key(authorization: str | None = Header(default=None)) -> ApiKeyAuth:
    if not REQUIRE_API_KEY:
        return ApiKeyAuth(owner_name="dev-mode", scopes_raw="*")
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="API key database is not configured.")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token.")

    token = authorization.split(" ", 1)[1].strip()
    key_hash = _sha256(token)

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT owner_name, scopes FROM api_keys
                WHERE key_hash = %s AND is_active = TRUE
                """,
                (key_hash,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=403, detail="Invalid API key.")
            cur.execute("UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = %s", (key_hash,))
        conn.commit()
    return ApiKeyAuth(owner_name=str(row[0]), scopes_raw=str(row[1]) if row[1] is not None else "*")


def require_scope(module: str) -> Callable[..., None]:
    """Returns a FastAPI dependency that enforces Bearer API key scope access for `module`."""

    def _check(auth: ApiKeyAuth = Depends(require_api_key)) -> None:
        if not auth.allows(module):
            raise HTTPException(
                status_code=403,
                detail=f"API key is not allowed to use: {module}. Allowed scopes: {auth.scopes_raw!r}",
            )

    return _check
