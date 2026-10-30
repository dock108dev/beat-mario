"""Pure shared page rendering; HTTP and session authority stay in lab_ui."""

from __future__ import annotations

import html

from smb3_agent.conversation_ui import CONVERSATION_CSS
from smb3_agent.glass_ui import GLASS_CSS
from smb3_agent.lab_page_styles import LAB_PAGE_CSS


def render_page(*, title: str, body: str, csrf_token: str | None = None) -> str:
    if csrf_token is not None:
        csrf_field = (
            '<input type="hidden" name="csrf_token" '
            f'value="{html.escape(csrf_token, quote=True)}">'
        )
        body = _inject_csrf_fields(body, csrf_field)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <title>{html.escape(title, quote=True)}</title>
  <style>
{LAB_PAGE_CSS}  </style>
</head>
<body>{body}<style>{GLASS_CSS}
{CONVERSATION_CSS}</style></body>
</html>"""


def _inject_csrf_fields(body: str, csrf_field: str) -> str:
    parts: list[str] = []
    cursor = 0
    while True:
        start = body.find("<form", cursor)
        if start < 0:
            parts.append(body[cursor:])
            return "".join(parts)
        end = body.find(">", start + 5)
        if end < 0:
            parts.append(body[cursor:])
            return "".join(parts)
        parts.append(body[cursor : end + 1])
        opening_tag = body[start : end + 1]
        close = body.find("</form>", end + 1)
        form_body = body[end + 1 : close] if close >= 0 else ""
        if 'method="post"' in opening_tag and 'name="csrf_token"' not in form_body:
            parts.append(csrf_field)
        cursor = end + 1
