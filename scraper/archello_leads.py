"""
Archello lead harvester - finds CANDIDATE architect firms for a country.

WHAT THIS DOES: pages through archello.com's "Private Houses" project list
for one country (the same list its Location filter shows), counts how many
house projects each firm has there, and for the firms with the most reads the
Website link from the firm's Archello profile. The output is a LEAD list
only (firm name, own website, how many Archello houses, a few titles): none
of Archello's photos or text is used or published. Every lead must still pass
the usual bar (own site with individual project pages, >= 4 contemporary
new-build houses, usable photos) via add_architect_batch.py before it is added.

WHY: Divisare's curated collections gave the best yield but nothing for
England or France (see project memory, architects_craftspeople_search_gap).
Archello's list is large and uncurated (38,316 private houses worldwide,
incl. interiors/apartments), so firms are ranked by house count in the
country and the Archello Awards filter can narrow further.

POLITENESS: robots.txt checked, one request at a time, ~1.2s apart, a page
cap, profiles only for the top firms.

RUN:
    python3 archello_leads.py --location "England, UK" --country-code GB
    python3 archello_leads.py --location "France" --country-code FR --min-projects 3
"""

import argparse
import datetime
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from scrape import HEADERS, _site_robots

BASE = "https://archello.com"
DATA_DIR = Path(__file__).parent.parent / "data"
DELAY = 4.0          # Archello rate-limits (HTTP 429 after ~7 pages at 1.2s, 2026-10-03)
BACKOFF = (60, 180, 300)   # seconds to wait after a 429 before each retry
# Titles that signal an inner-city extension/conversion rather than a
# standalone house (a London-heavy list is mostly these). Used to RANK firms,
# not to exclude: the pipeline's house classifier is the real judge.
URBAN_TITLE_RE = re.compile(
    r"extension|loft|mews|terrace|townhouse|town house|\bflat\b|apartment|basement|refurb|renovation|"
    r"conversion|maisonette|penthouse|victorian|georgian|edwardian|remodel|retrofit|\bstreet\b|\broad\b|\bsquare\b|\bgardens?\b|\bplace\b",
    re.I,
)
SOCIAL = re.compile(r"facebook|instagram|twitter|linkedin|pinterest|google|youtube|youtu\.be|vimeo|cloudflare|w3\.org|apple\.com|archello", re.I)


def list_url(location, country_code, page, awards=False):
    q = f"location={quote_plus(location)}&country_code={country_code}&city_name=&building_year_from=&page={page}"
    if awards:
        # the Awards filter as the site itself builds it (read from the live
        # address bar 2026-10-03): ceremonies 2023-2025, a very small, high-
        # signal subset (England private houses: 5 of 1,898)
        q += ("&ceremonies=ceremonies_archello-awards-2023_archello-awards-2024_archello-awards-2025"
              "&ceremonies_open=1")
    return f"{BASE}/projects/private-houses?{q}"


def parse_list_page(page_html):
    """-> [(project_slug, title, brand_slug, brand_name)] for one list page."""
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    for info in soup.select(".ah-project-listing-item-info"):
        name_a = info.select_one("a.ah-project-listing-item-name")
        brand_a = info.select_one('a[href^="/brand/"]')
        if not name_a:
            continue
        slug = name_a["href"].split("/project/")[-1].split("?")[0]
        out.append((slug, name_a.get_text(strip=True),
                    brand_a["href"].split("/brand/")[-1].split("/")[0] if brand_a else None,
                    brand_a.get_text(strip=True) if brand_a else None))
    return out


def parse_profile_website(page_html):
    """The firm's own site from its Archello profile (first non-social external link)."""
    for href in re.findall(r'href="(https?://[^"]+)"', page_html):
        if not SOCIAL.search(href):
            return href
    return None


def get_with_backoff(url):
    """GET that waits and retries on HTTP 429 instead of hammering the site."""
    for wait in (0,) + BACKOFF:
        if wait:
            print(f"  429 - waiting {wait}s before retrying...")
            time.sleep(wait)
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 429:
            return r
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--location", required=True, help='e.g. "England, UK"')
    ap.add_argument("--country-code", required=True, help="e.g. GB")
    ap.add_argument("--max-pages", type=int, default=70)
    ap.add_argument("--min-projects", type=int, default=3, help="only look up firms with at least this many houses")
    ap.add_argument("--top", type=int, default=60, help="profile lookups for at most this many firms")
    ap.add_argument("--awards", action="store_true", help="only projects from the Archello Awards 2023-2025 ceremonies")
    args = ap.parse_args()

    robots = _site_robots(BASE)
    if not robots.can_fetch("FormgroundBot", BASE + "/projects/private-houses"):
        raise SystemExit("robots.txt disallows the project list - stopping.")

    firms = defaultdict(lambda: {"name": None, "projects": []})
    seen_projects = set()
    for page in range(1, args.max_pages + 1):
        r = get_with_backoff(list_url(args.location, args.country_code, page, args.awards))
        if r.status_code != 200:
            print(f"page {page}: HTTP {r.status_code} - stopping.")
            break
        rows = [x for x in parse_list_page(r.text) if x[0] not in seen_projects]
        if not rows:
            break
        for slug, title, bslug, bname in rows:
            seen_projects.add(slug)
            if bslug:
                firms[bslug]["name"] = bname
                firms[bslug]["projects"].append(title)
        time.sleep(DELAY)
    print(f"{len(seen_projects)} projects, {len(firms)} firms")

    def house_like(info):
        return [t for t in info["projects"] if not URBAN_TITLE_RE.search(t)]

    # rank by standalone-house-looking titles first, then total projects
    ranked = sorted(firms.items(), key=lambda kv: (-len(house_like(kv[1])), -len(kv[1]["projects"])))
    ranked = [kv for kv in ranked if len(kv[1]["projects"]) >= args.min_projects][: args.top]
    leads = []
    for bslug, info in ranked:
        site = None
        try:
            pr = get_with_backoff(f"{BASE}/brand/{bslug}")
            if pr.status_code == 200:
                site = parse_profile_website(pr.text)
        except requests.RequestException:
            pass
        leads.append({"firm": info["name"], "archello": f"{BASE}/brand/{bslug}", "website": site,
                      "houses_on_archello": len(info["projects"]), "house_like_titles": len(house_like(info)),
                      "sample_projects": (house_like(info) or info["projects"])[:5]})
        time.sleep(DELAY)

    out = DATA_DIR / f"archello_leads_{args.country_code}_{datetime.date.today().isoformat()}.json"
    out.write_text(json.dumps(leads, indent=2, ensure_ascii=False))
    for l in leads:
        print(f"{l['house_like_titles']:3d}/{l['houses_on_archello']:3d}  {l['firm']}  |  {l['website']}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
