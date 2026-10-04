"""
Versioned links to shared static assets (2026-10-04).

GitHub Pages lets browsers cache a stylesheet for ~10 minutes, so a page that
needs a NEW rule (the icon CSS replacing the icon font) could meet a stale cached
copy and show nothing. Every page therefore links shared assets with a content
hash - /icons.css?v=1a2b3c4d - so a changed file always has a new address.

    ICONS_CSS      the href generators put in their templates
    stamp_html()   rewrites / inserts the link in the hand-written pages
                   (frontend/*.html and their docs/ mirrors)
"""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"


def asset_href(name):
    digest = hashlib.sha1((FRONTEND / name).read_bytes()).hexdigest()[:8]
    return f"/{name}?v={digest}"


ICONS_CSS = asset_href("icons.css")
WORK_MENU_CSS = asset_href("work-menu.css")
WORK_MENU_JS = asset_href("work-menu.js")
_LINK_RE = re.compile(r'<link rel="stylesheet" href="/icons\.css(?:\?v=[0-9a-f]+)?">')
_MENU_CSS_RE = re.compile(r'<link rel="stylesheet" href="/work-menu\.css(?:\?v=[0-9a-f]+)?">')
_MENU_JS_RE = re.compile(r'<script src="/work-menu\.js(?:\?v=[0-9a-f]+)?" defer></script>')
MENU_HEAD_LINKS = f'<link rel="stylesheet" href="{WORK_MENU_CSS}">'
MENU_SCRIPT = f'<script src="{WORK_MENU_JS}" defer></script>'


def stamp_html(paths=None):
    """Make every hand-written page link the current icons.css (inserted after its
    site.css link, or before </head> when it has none). Idempotent."""
    link = f'<link rel="stylesheet" href="{ICONS_CSS}">'
    paths = paths or [p for d in (FRONTEND, DOCS) for p in d.glob("*.html")]
    changed = 0
    for p in paths:
        s = p.read_text()
        if "icons.css" in s:
            new = _LINK_RE.sub(link, s)
        elif re.search(r'<link rel="stylesheet" href="/?site\.css">', s):
            new = re.sub(r'(<link rel="stylesheet" href="/?site\.css">)', lambda m: m.group(1) + "\n" + link, s, count=1)
        elif "</head>" in s:
            new = s.replace("</head>", link + "\n</head>", 1)
        else:
            continue
        if 'class="work-menu"' in new:
            if "work-menu.css" in new:
                new = _MENU_CSS_RE.sub(MENU_HEAD_LINKS, new)
            else:
                new = new.replace("</head>", MENU_HEAD_LINKS + "\n</head>", 1)
            if "work-menu.js" in new:
                new = _MENU_JS_RE.sub(MENU_SCRIPT, new)
            else:
                new = new.replace("</body>", MENU_SCRIPT + "\n</body>", 1)
        if new != s:
            p.write_text(new)
            changed += 1
    return changed
