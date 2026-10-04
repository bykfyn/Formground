"""
Redirect stubs for moved pages (2026-10-04).

GitHub Pages cannot send an HTTP 301, so a page that moved leaves a small stub at
its old address: a meta refresh + JS redirect to the new page and a canonical
pointing at it (search engines treat that as a move; visitors and old links land
on the right page at once). Used when the browse pages moved to /work/, the Edits
to /edits/, and the retired category pages to their /work/ category pages.
"""

import html
from pathlib import Path

SITE_URL = "https://formground.com"


def render_redirect(target):
    """target: a site path ("/work/lighting.html")."""
    t = html.escape(target)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Formground</title>
<meta http-equiv="refresh" content="0; url={t}">
<link rel="canonical" href="{SITE_URL}{t}">
<script>window.location.replace({target!r});</script>
</head>
<body>
<p>Formground has moved this page to <a href="{t}">{t}</a>.</p>
</body>
</html>
"""


def write_redirect(path, target):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(render_redirect(target))


def is_redirect_stub(text):
    return 'http-equiv="refresh"' in text and "Formground has moved this page" in text
