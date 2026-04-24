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
    detail = html.escape(f"{err}: {desc}".strip(": ") or "(no details)")

    body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>mcp.jarvis1.net — Microsoft</title>
<style>body{{font-family:system-ui,sans-serif;max-width:42rem;margin:2rem;line-height:1.45}}
code{{background:#f4f4f4;padding:0.15rem 0.35rem}} pre{{background:#111;color:#eee;padding:1rem;overflow:auto;font-size:0.85rem}}</style>
</head>
<body>
<h1>Microsoft — OAuth on this MCP URL is disabled</h1>
<p>Sign-in now happens on the <strong>agent</strong> (device code): in Telegram send
<code>/microsoft-login</code> to the <strong>jarvis1net</strong> bot, not on this page.</p>
<p>In <strong>Azure Portal</strong> → your app → <strong>Authentication</strong>:</p>
<ul>
<li>Remove the Web redirect pointing at <code>mcp.jarvis1.net/.../oauth/callback</code> (no longer used).</li>
<li>Enable <strong>Allow public client flows</strong> and under “Mobile and desktop applications”
add <strong>one</strong> redirect <code>https://login.microsoftonline.com/&lt;tenant&gt;/oauth2/nativeclient</code>
matching the agent tenant (<code>common</code>, <code>organizations</code>, <code>consumers</code>, or GUID).
Do not mix multiple segments at once — that can yield <code>invalid_request</code> / missing <code>response_type</code>.</li>
</ul>
<p>Redirect query (for debugging):</p>
<pre>{html.escape(qs[:2000]) if qs else "(empty)"}</pre>
<p>Error summary: {detail}</p>
</body>
</html>"""
    return HTMLResponse(content=body, status_code=200)
