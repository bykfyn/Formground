"""
Dusty NYC maker harvester - a LEAD list only (2026-10-03).

dustynyc.com is a New York showroom selling other makers' designs; each product
page credits the maker on the line just above the INQUIRE button. Per our rule
that a retailer is only ever a sourcing list (never a data source), this reads
nothing but the maker credit and a product name per page, and the output feeds
data/prospective_brands.json - each maker still has to be found on, and
triaged from, its OWN site before anything is published.

POLITENESS: robots.txt is checked (the site disallows named AI crawlers; this
bot is not one of them and the product pages are allowed for '*'), one request
at a time, ~1s apart, resumable, hard runtime ceiling.

RUN:  python3 dustynyc_makers.py            (resumes from data/dustynyc_makers_raw.json)
"""

import html
import json
import re
import time
from pathlib import Path

import requests

from scrape import HEADERS, _site_robots

BASE = "https://www.dustynyc.com"
RAW = Path(__file__).parent.parent / "data" / "dustynyc_makers_raw.json"
DELAY = 1.0
MAX_SECONDS = 50 * 60


def page_lines(page_html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", page_html, flags=re.S)
    return [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n") if l.strip()]


def parse_product(page_html):
    """-> (maker, product_name) from one product page; maker = the line before INQUIRE."""
    lines = page_lines(page_html)
    maker = None
    for i, l in enumerate(lines):
        if l.upper() == "INQUIRE" and i > 0:
            maker = lines[i - 1]
            break
    m = re.search(r'<meta property="og:title" content="([^"]+)"', page_html)
    name = html.unescape(m.group(1)).split(" — ")[0].strip() if m else None
    return maker, name


def main():
    robots = _site_robots(BASE)
    sitemap = requests.get(BASE + "/sitemap.xml", headers=HEADERS, timeout=30).text
    urls = sorted(set(re.findall(r"<loc>(https://www\.dustynyc\.com/all/p/[^<]+)</loc>", sitemap)))
    urls = [u for u in urls if robots.can_fetch("FormgroundBot", u)]
    raw = json.loads(RAW.read_text()) if RAW.exists() else {}
    todo = [u for u in urls if u not in raw]
    print(f"{len(urls)} product pages, {len(raw)} done, {len(todo)} to go")
    start = time.time()
    for n, u in enumerate(todo, 1):
        if time.time() - start > MAX_SECONDS:
            print("runtime ceiling reached - rerun to resume"); break
        try:
            r = requests.get(u, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                maker, name = parse_product(r.text)
                raw[u] = {"maker": maker, "name": name}
            else:
                raw[u] = {"error": r.status_code}
        except requests.RequestException as e:
            raw[u] = {"error": type(e).__name__}
        if n % 25 == 0:
            RAW.write_text(json.dumps(raw, indent=1, ensure_ascii=False))
            print(f"  {n}/{len(todo)}")
        time.sleep(DELAY)
    RAW.write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    print(f"saved {len(raw)} pages")


if __name__ == "__main__":
    main()
