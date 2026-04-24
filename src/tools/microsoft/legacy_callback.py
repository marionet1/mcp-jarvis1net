"""Legacy OAuth callback URL — server-side Microsoft login was removed; returns a help page instead of 404."""

from __future__ import annotations

import html
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/v1/tools/microsoft", tags=["microsoft"])


@router.get("/oauth/callback", include_in_schema=False)
def microsoft_oauth_callback_legacy(request: Request) -> HTMLResponse:
    """Some Azure apps still redirect here after login; OAuth on MCP is disabled — use agent device code."""
    qs = urlsplit(str(request.url)).query
    params = parse_qs(qs, keep_blank_values=True)
    err = (params.get("error") or [""])[0]
    desc = (params.get("error_description") or [""])[0]
    detail = html.escape(f"{err}: {desc}".strip(": ") or "(brak szczegółów)")

    body = f"""<!DOCTYPE html>
<html lang="pl">
<head><meta charset="utf-8"/><title>mcp.jarvis1.net — Microsoft</title>
<style>body{{font-family:system-ui,sans-serif;max-width:42rem;margin:2rem;line-height:1.45}}
code{{background:#f4f4f4;padding:0.15rem 0.35rem}} pre{{background:#111;color:#eee;padding:1rem;overflow:auto;font-size:0.85rem}}</style>
</head>
<body>
<h1>Microsoft — ten adres OAuth na MCP jest wyłączony</h1>
<p>Logowanie odbywa się teraz <strong>na agencie</strong> (device code): w Telegramie wyślij
<code>/microsoft-login</code> na bota <strong>jarvis1net</strong>, nie na tej stronie.</p>
<p>W <strong>Azure Portal</strong> → Twoja aplikacja → <strong>Authentication</strong>:</p>
<ul>
<li>Usuń redirect typu Web wskazujący na <code>mcp.jarvis1.net/.../oauth/callback</code> (nie jest już używany).</li>
<li>Włącz <strong>Allow public client flows</strong> i dodaj platformę
„Mobile and desktop applications” z redirectem <strong>dokładnie</strong>
<code>https://login.microsoftonline.com/&lt;tenant&gt;/oauth2/nativeclient</code>,
gdzie <code>&lt;tenant&gt;</code> to ten sam wpis co w agencie (<code>common</code>, <code>organizations</code> lub GUID katalogu) — inaczej po logowaniu pojawia się <code>invalid_request</code> na stronie nativeclient.</li>
</ul>
<p>Parametry z przekierowania (do debugowania):</p>
<pre>{html.escape(qs[:2000]) if qs else "(puste)"}</pre>
<p>Skrót błędu: {detail}</p>
</body>
</html>"""
    return HTMLResponse(content=body, status_code=200)
