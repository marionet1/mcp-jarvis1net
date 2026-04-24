from __future__ import annotations

import secrets
import time

_STATE_TTL_SEC = 600.0
_states: dict[str, float] = {}


def issue_state() -> str:
    now = time.monotonic()
    dead = [k for k, t in _states.items() if now - t > _STATE_TTL_SEC]
    for k in dead:
        del _states[k]
    s = secrets.token_urlsafe(32)
    _states[s] = now
    return s


def consume_state(state: str) -> bool:
    now = time.monotonic()
    t = _states.pop(state, None)
    if t is None:
        return False
    return (now - t) <= _STATE_TTL_SEC
