"""Shared HTML helpers for the generated reports (incident + SOC summary).

Every value interpolated into a report **must** go through :func:`esc` or
:func:`esc_list` so attacker-controlled data (incident titles, note bodies,
filenames, ...) can never break out into markup or script (XSS defence, task 9.2).
The reports are also rendered with a restrictive ``Content-Security-Policy``
meta tag so that, even if an escaping bug slipped through, inline/remote script
could not execute when the file is opened in a browser.
"""

from __future__ import annotations

import html

# Lock down the generated document: no scripts, no remote loads, no framing.
# ``style-src 'unsafe-inline'`` is required for the embedded <style> block.
CSP_META = (
    '<meta http-equiv="Content-Security-Policy" '
    "content=\"default-src 'none'; style-src 'unsafe-inline'; "
    "img-src data:; base-uri 'none'\">"
)

REPORT_STYLE = """
    body {
        font-family: Arial, sans-serif;
        margin: 40px;
        line-height: 1.5;
        color: #111;
    }
    h1, h2 {
        margin-bottom: 10px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 25px;
    }
    th, td {
        border: 1px solid #ccc;
        padding: 8px;
        text-align: left;
        vertical-align: top;
    }
    th {
        background: #f2f2f2;
    }
    .section {
        margin-top: 30px;
    }
    .muted {
        color: #666;
        font-size: 13px;
    }
"""


def esc(value) -> str:
    """HTML-escape a single value for safe interpolation into a report."""
    return html.escape(str(value)) if value is not None else ""


def esc_list(values) -> str:
    """Render a list field (e.g. affected hosts) as an escaped comma list."""
    if values is None:
        return ""
    if isinstance(values, (list, tuple)):
        return html.escape(", ".join(str(v) for v in values))
    return html.escape(str(values))


def report_page(title: str, body: str) -> str:
    """Wrap ``body`` in the common, CSP-locked report shell."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {CSP_META}
    <title>{esc(title)}</title>
    <style>{REPORT_STYLE}</style>
</head>
<body>
{body}
</body>
</html>
"""
