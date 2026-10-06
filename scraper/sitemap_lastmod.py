"""
Honest <lastmod> dates for docs/sitemap.xml (2026-10-06).

The generators stamp every URL with the build date, which makes the field useless: Google learns to ignore
lastmod when it changes on every page every day. This post-pass runs last in the build and gives each URL the
date its page content really last changed.

How: data/sitemap_lastmod.json keeps {url: {hash, lastmod}}. A page's hash is taken over its HTML with the
versioned asset query strings (?v=abc12345) removed, so a stylesheet version bump alone does not count as a
change. New or changed pages get today's date; unchanged pages keep the date they had. URLs that leave the
sitemap are dropped from the record. The first run has no history, so everything is dated that day.
"""

import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SITE_URL = "https://formground.com"
STORE_PATH = ROOT / "data" / "sitemap_lastmod.json"

_VERSION_PARAM = re.compile(r"\?v=[0-9a-f]{6,}")
_URL_BLOCK = re.compile(r"<url>.*?</url>", re.S)


def page_hash(text):
    return hashlib.sha1(_VERSION_PARAM.sub("", text).encode("utf-8")).hexdigest()


def _file_for(loc, docs):
    path = loc[len(SITE_URL):] if loc.startswith(SITE_URL) else loc
    path = path.lstrip("/") or "index.html"
    return docs / path


def apply(docs=None, store_path=None, today=None):
    """Rewrites docs/sitemap.xml in place with real lastmod dates; returns (changed_urls, total_urls)."""
    docs = Path(docs) if docs else ROOT / "docs"
    store_path = Path(store_path) if store_path else STORE_PATH
    today = today or datetime.date.today().isoformat()
    sitemap_path = docs / "sitemap.xml"
    if not sitemap_path.exists():
        print("sitemap_lastmod: no sitemap.xml, nothing to do.")
        return 0, 0
    store = json.loads(store_path.read_text()) if store_path.exists() else {}
    new_store, changed = {}, 0

    def rewrite(match):
        nonlocal changed
        block = match.group(0)
        loc = re.search(r"<loc>(.*?)</loc>", block).group(1)
        page = _file_for(loc, docs)
        if not page.exists():
            new_store[loc] = store.get(loc, {"hash": "", "lastmod": today})
            lastmod = new_store[loc]["lastmod"]
        else:
            digest = page_hash(page.read_text(errors="ignore"))
            old = store.get(loc)
            if old and old.get("hash") == digest:
                lastmod = old["lastmod"]
            else:
                lastmod = today
                changed += 1
            new_store[loc] = {"hash": digest, "lastmod": lastmod}
        block = re.sub(r"\s*<lastmod>.*?</lastmod>", "", block)
        return block.replace("</loc>", f"</loc>\n    <lastmod>{lastmod}</lastmod>", 1)

    text = _URL_BLOCK.sub(rewrite, sitemap_path.read_text())
    sitemap_path.write_text(text)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(new_store, indent=0, sort_keys=True))
    print(f"sitemap_lastmod: {len(new_store)} URLs, {changed} new or changed since the last build.")
    return changed, len(new_store)


if __name__ == "__main__":
    apply()
