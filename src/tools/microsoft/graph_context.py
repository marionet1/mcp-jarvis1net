"""Request-scoped Microsoft Graph bearer token (set by /v1/tools/call from agent)."""

from __future__ import annotations

from contextvars import ContextVar

_graph_bearer: ContextVar[str | None] = ContextVar("graph_bearer", default=None)


def set_graph_bearer(token: str | None) -> None:
    _graph_bearer.set(token)


def get_graph_bearer() -> str | None:
    return _graph_bearer.get()
