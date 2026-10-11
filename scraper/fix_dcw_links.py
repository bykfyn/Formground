"""
DCW éditions lists some pieces under US-market handles ("-etl", "-us", "-us-adapt") in its public product feed; those
addresses answer 404 on the main storefront (confirmed 2026-10-11: .../products/isp-table-us is a 404 while
.../products/isp-table, the same piece, works), so cards linked to a dead page and check_links did not flag them.

This script finds, for every DCW product stored under such a handle, the plain handle that really loads, verifies the
page (HTTP 200 and the piece's name in the page title) and writes the pairs to data/dcw_url_fixes.json, which
scrape.py applies after every DCW scrape. Pieces with no working plain page are listed and left alone.

Polite on purpose: one request every 3 seconds, backing off on a 429 (the shop rate-limits fast).

    python3 scraper/fix_dcw_links.py
"""

import json
import re
import sqlite3
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
FIXES = ROOT / "data" / "dcw_url_fixes.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}
SUFFIX = re.compile(r"-(?:etl|us-adapt|us)$")


def fetch(url):
    delay = 20
    for _ in range(8):
        time.sleep(3)
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        if r.status_code != 429:
            return r
        time.sleep(delay)
        delay = min(delay * 2, 300)
    return r


def main():
    conn = sqlite3.connect(ROOT / "data" / "formground.db")
    rows = conn.execute("SELECT product_name, product_url FROM products WHERE brand = 'DCW éditions'").fetchall()
    conn.close()
    fixes = json.loads(FIXES.read_text()) if FIXES.exists() else {}
    unresolved = []
    for name, url in rows:
        handle = url.rsplit("/", 1)[1]
        if not SUFFIX.search(handle) or url in fixes:
            continue
        plain = url.rsplit("/", 1)[0] + "/" + SUFFIX.sub("", handle)
        r = fetch(plain)
        title = re.search(r"<title>(.*?)</title>", r.text, re.S | re.I)
        title = re.sub(r"\s+", " ", title.group(1)).lower() if title else ""
        words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) > 1]
        if r.status_code == 200 and words and all(w in title for w in words[:2]):
            fixes[url] = plain
            print(f"OK   {name}: {plain}")
        else:
            unresolved.append((name, url, r.status_code))
            print(f"--   {name}: {plain} -> {r.status_code}")
        FIXES.write_text(json.dumps(fixes, indent=1, sort_keys=True))
    print(f"\n{len(fixes)} fixed, {len(unresolved)} unresolved")


if __name__ == "__main__":
    main()
