"""
Checks that the hand-picked photos on the pages people see first still load (2026-10-11: the Log chair on the home page
pointed at a photo address Raawii had removed, and nothing noticed).

Covers the home page, the Edits hub, every Edit and the Creators page: about 300 photos on the makers' own servers.
Only a clear failure counts - HTTP 404/410, or a 200 that is not an image - because timeouts, 403s and 429s say nothing
about whether the photo exists. One request at a time per host, 0.7s apart (shops rate-limit hard; see the DCW note in
memory). Prints the broken ones with the pages that show them, writes them to the GitHub step summary when run there,
and exits 1 so the daily workflow goes red.

    python3 scraper/check_curated_images.py
"""

import html
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests

DOCS = Path(__file__).parent.parent / "docs"
PAGES = ["index.html", "edits.html", "creators.html"] + [f"edits/{p.name}" for p in sorted((DOCS / "edits").glob("*.html"))]
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://formground.com/"}
DELAY = 0.7
IMG_RE = re.compile(r'<img\b[^>]*?\bsrc="(https?://[^"]+)"', re.I)


def photos_by_page():
    """{photo url: [pages that show it]} for every photo hosted on another server."""
    out = defaultdict(list)
    for page in PAGES:
        path = DOCS / page
        if not path.exists():
            continue
        for url in IMG_RE.findall(path.read_text()):
            url = html.unescape(url)
            if urlparse(url).netloc.endswith("formground.com"):
                continue
            if page not in out[url]:
                out[url].append(page)
    return out


def check(url):
    """'ok', 'broken: <why>', or 'unclear: <why>' (never counted as a failure)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=25, stream=True)
    except requests.RequestException as e:
        return f"unclear: {type(e).__name__}"
    try:
        if r.status_code in (404, 410):
            return f"broken: HTTP {r.status_code}"
        if r.status_code == 200:
            kind = r.headers.get("content-type", "").split(";")[0].strip().lower()
            if kind and not kind.startswith("image/") and kind != "application/octet-stream":
                return f"broken: 200 but {kind}"
            return "ok"
        return f"unclear: HTTP {r.status_code}"
    finally:
        r.close()


def main():
    photos = photos_by_page()
    print(f"{len(photos)} photos on {len(PAGES)} pages")
    last_hit = {}
    broken, unclear = [], 0
    for url, pages in photos.items():
        host = urlparse(url).netloc
        wait = DELAY - (time.monotonic() - last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        result = check(url)
        last_hit[host] = time.monotonic()
        if result.startswith("broken"):
            broken.append((url, result, pages))
        elif result.startswith("unclear"):
            unclear += 1
    lines = [f"{len(photos)} photos checked, {len(broken)} broken, {unclear} unclear (not counted)"]
    for url, why, pages in broken:
        lines.append(f"- {why}: {url}\n    shown on: {', '.join(pages[:6])}{' ...' if len(pages) > 6 else ''}")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### Curated photos\n\n```\n" + report + "\n```\n")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
