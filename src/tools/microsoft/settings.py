from __future__ import annotations

import os


def microsoft_configured() -> bool:
    return bool(
        os.getenv("MICROSOFT_CLIENT_ID", "").strip()
        and os.getenv("MICROSOFT_CLIENT_SECRET", "").strip()
    )


def client_id() -> str:
    return os.getenv("MICROSOFT_CLIENT_ID", "").strip()


def client_secret() -> str:
    return os.getenv("MICROSOFT_CLIENT_SECRET", "").strip()


def authority() -> str:
    tid = os.getenv("MICROSOFT_TENANT_ID", "common").strip() or "common"
    if tid in ("common", "organizations", "consumers"):
        return f"https://login.microsoftonline.com/{tid}"
    return f"https://login.microsoftonline.com/{tid}"


def redirect_uri() -> str:
    return os.getenv("MICROSOFT_REDIRECT_URI", "").strip()


def token_cache_path() -> str:
    return os.getenv("MICROSOFT_TOKEN_CACHE_PATH", "").strip() or "data/microsoft_token_cache.json"


def graph_scopes() -> list[str]:
    raw = os.getenv(
        "MICROSOFT_GRAPH_SCOPES",
        "offline_access User.Read Mail.ReadWrite Mail.Send Calendars.ReadWrite Files.ReadWrite.All",
    )
    return [s.strip() for s in raw.replace(",", " ").split() if s.strip()]
