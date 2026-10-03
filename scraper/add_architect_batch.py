"""
Architect batch adder - runs the house pipeline for NEW firms and merges the
results into data/houses.json and data/architects.json.

WHAT THIS DOES (per firm in BATCH): discovers the firm's project pages (its
sitemap first, filtered by an include regex; else its listing page in a real
browser), and for each page - using the SAME functions as
scrape_architect_projects.py - renders it with Playwright, asks Claude (text)
whether it is genuinely an individual house (single-dwelling, new design or
a renovation WITH a genuine extension; not renovation-only, not
multi-family/commercial/institutional) and to extract name/location/year/
description, then vision-checks candidate photos (scrape_architects.
is_architecture_relevant) to pick one real photo. A house without a real
photo is dropped. Qualifying houses are merged into data/houses.json (de-
duplicated by project URL) and the firm is added to data/architects.json
only if at least one house qualified (pages are only generated for firms
with houses). Raw per-firm results are kept in
data/architect_batch_<date>.json for review.

WHY A SEPARATE SCRIPT: scrape_architect_projects.py is the original
prototype (fixed ALL_FIRMS list, writes a test file); the 2026-09-24
expansion merged its output into houses.json by hand. This makes that step
repeatable and testable (merge_houses is pure).

POLITENESS: robots.txt is checked per firm and per page, one page at a
time, LINK_CAP pages per firm, ~1.5s apart.

RUN:
    python3 add_architect_batch.py                 # whole BATCH
    python3 add_architect_batch.py --firm "STRÅ arkitekter"   # one firm
    python3 add_architect_batch.py --dry-run       # discovery only, no API calls
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from scrape import _site_robots, _site_sitemap_paths
from scrape_architect_projects import (
    call_claude_extract,
    candidate_images,
    discover_project_links,
    extract_page_content,
)
from scrape_architects import is_architecture_relevant

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
HOUSES_PATH = DATA_DIR / "houses.json"
ARCHITECTS_PATH = DATA_DIR / "architects.json"
LINK_CAP = 45
PAGE_DELAY = 1.5
MIN_SITEMAP_PATHS = 3     # fewer than this and the listing page is used instead
SOURCE_TAG = "curated_2026-10-03"

NAV_SKIP = r"in-progress|^/(about|contact|news|press|team|office|cv|jobs|info|home|index|search|cart|shop|journal|publications|awards|exhibitions)/?$|^/(en|de|fr|it|es|pt)/?$"

# Each firm: name, site (homepage, stored on the firm record), city, country,
# include (regex on URL path that marks a project page), optional sitemap_url
# / listing_url / link_prefix (fallback discovery), exclude (regex).
BATCH = [
    {"name": "Bernardo Bader Architekten", "site": "https://www.bernardobader.com", "city": "Dornbirn", "country": "Austria",
     "sitemap_url": "https://www.bernardobader.com/en/sitemap.xml",
     "include": r"^/en/projekt/", "listing_url": "https://www.bernardobader.com/en/", "link_prefix": "/en/projekt/"},
    {"name": "Innauer Matt Architekten", "site": "https://www.innauer-matt.com", "city": "Bezau", "country": "Austria",
     "include": r"^/projekt/", "listing_url": "https://www.innauer-matt.com/", "link_prefix": "/projekt/"},
    {"name": "Galeotti Rizzato Architetti", "site": "https://galeottirizzato.com", "city": "Treviso", "country": "Italy",
     "include": r"^/en/project/", "listing_url": "https://galeottirizzato.com/en/", "link_prefix": "/en/project/"},
    {"name": "Loader Monteith", "site": "https://loadermonteith.co.uk", "city": "Glasgow", "country": "United Kingdom",
     "include": r"^/projects/[^/]+/?$", "listing_url": "https://loadermonteith.co.uk/project/dwelling/", "link_prefix": "/projects/"},
    {"name": "Studio Putinja", "site": "https://putinja.com", "city": "Pazin", "country": "Croatia", "strip_thumb": "_thumb",
     "include": r"^/en/\d+-", "listing_url": "https://putinja.com/en/", "link_prefix": "/en/"},
    {"name": "Herbst Architects", "site": "https://www.herbstarchitects.co.nz", "city": "Auckland", "country": "New Zealand",
     "include": r"^/projects/[^/]+", "listing_url": "https://www.herbstarchitects.co.nz/projects", "link_prefix": "/projects/"},
    {"name": "Patterson Associates", "site": "https://pattersons.com", "city": "Auckland", "country": "New Zealand",
     "include": r"^/project/[^/]+", "listing_url": "https://pattersons.com/projects/", "link_prefix": "/project/"},
    {"name": "Welsh + Major", "site": "https://welshmajor.com", "city": "Sydney", "country": "Australia",
     "include": r"^/project/[^/]+", "listing_url": "https://welshmajor.com/our-projects/?category=residential", "link_prefix": "/project/"},
    {"name": "Omar Gandhi Architect", "site": "https://www.omargandhi.com", "city": "Halifax", "country": "Canada",
     "include": r"^/work/[^/]+", "listing_url": "https://www.omargandhi.com/work", "link_prefix": "/work/"},
    {"name": "Wittman Estes", "site": "https://www.wittman-estes.com", "city": "Seattle", "country": "United States",
     "include": r"^/projects/[^/]+", "listing_url": "https://www.wittman-estes.com/projects", "link_prefix": "/projects/"},
    {"name": "Luciano Kruk Arquitectos", "site": "https://lucianokruk.com", "city": "Buenos Aires", "country": "Argentina",
     "excluded": "hotlink-protected: lucianokruk.com answers 403 to image requests from other sites (checked 2026-10-03, 41/41 images) - not bypassed, not rehosted",
     "include": r"^/proyecto/[^/]+", "listing_url": "https://lucianokruk.com/", "link_prefix": "/proyecto/"},
    {"name": "Felipe Assadi", "site": "https://www.felipeassadi.com", "city": "Santiago", "country": "Chile",
     "include": r"^/(casa|copia-de-casa)", "listing_url": "https://www.felipeassadi.com/casas", "link_prefix": None},
    {"name": "Tato Architects", "site": "https://tat-o.com", "city": "Kobe", "country": "Japan",
     "name_selector": "div.eng h2.slideTtl", "location_selector": "div.eng p.slideDtl",
     "include": r"^/projects/\d+/?$", "listing_url": "https://tat-o.com/projects/", "link_prefix": "/projects/"},
    {"name": "STRÅ arkitekter", "site": "https://www.straaa.com", "city": "Oslo", "country": "Norway",
     "sitemap_url": "https://www.straaa.com/pages-sitemap.xml", "include": r"^/[^/]+$", "exclude": NAV_SKIP,
     "listing_url": "https://www.straaa.com/work-houses", "link_prefix": None},
    # --- 2026-10-03 England + France (Manser Medal / RIBA / Archinovo / Divisare signals) ---
    {"name": "Surman Weston", "site": "https://surmanweston.com", "city": "London", "country": "United Kingdom",
     "include": r"^/projects/[^/]+", "listing_url": "https://surmanweston.com/projects/", "link_prefix": "/projects/"},
    {"name": "Sandy Rendel Architects", "site": "https://sandyrendel.com", "city": "London", "country": "United Kingdom",
     "include": r"^/projects/[^/]+", "listing_url": "https://sandyrendel.com/projects", "link_prefix": "/projects/"},
    {"name": "Hugh Strange Architects", "excluded": "only 1 qualifying house (Strange House & Studio); below the >=4 bar", "site": "https://www.hughstrange.com", "city": "London", "country": "United Kingdom",
     "include": r"^/[a-z0-9-]+\.html$", "exclude": r"^/(index|about|contact|news|press|projects|studio|team|practice|publications)\.html$",
     "listing_url": "https://www.hughstrange.com/", "link_prefix": None},
    {"name": "Sanei + Hopkins Architects", "site": "https://www.saneihopkins.co.uk", "city": "London", "country": "United Kingdom",
     "include": r"^/projects/[^/]+", "listing_url": "https://www.saneihopkins.co.uk/projects", "link_prefix": "/projects/"},
    {"name": "Gianni Botsford Architects", "site": "https://www.giannibotsford.com", "city": "London", "country": "United Kingdom",
     "include": r"^/projects/[^/]+", "listing_url": "https://www.giannibotsford.com/projects/", "link_prefix": "/projects/"},
    {"name": "Haysom Ward Miller Architects", "site": "https://www.haysomwardmiller.co.uk", "city": "Cambridge", "country": "United Kingdom",
     "include": r"^/projects/private-houses/[^/]+", "listing_url": "https://www.haysomwardmiller.co.uk/projects/private-houses", "link_prefix": "/projects/private-houses/"},
    {"name": "Hudson Architects", "site": "https://hudsonarchitects.co.uk", "city": "Norwich", "country": "United Kingdom",
     "include": r"^/our-work/homes/new-homes/[^/]+", "listing_url": "https://hudsonarchitects.co.uk/our-work/homes/new-homes/", "link_prefix": "/new-homes/"},
    {"name": "RX Architects", "site": "https://rxarchitects.com", "city": "Rye", "country": "United Kingdom",
     "include": r"^/portfolio/[^/]+", "listing_url": "https://rxarchitects.com/portfolio/", "link_prefix": "/portfolio/"},
    {"name": "MawsonKerr Architects", "excluded": "hotlink-protected: serves a placeholder image when the Referer is formground.com", "site": "https://mawsonkerr.co.uk", "city": "Newcastle upon Tyne", "country": "United Kingdom",
     "include": r"^/projects/[^/]+", "listing_url": "https://mawsonkerr.co.uk/projects/", "link_prefix": "/projects/"},
    {"name": "Avignon Architecte", "site": "https://avignon-architecte.com", "city": "Nantes", "country": "France",
     "include": r"^/habitat-individuel/[^/]+", "listing_url": "https://avignon-architecte.com/habitat-individuel/", "link_prefix": "/habitat-individuel/"},
    {"name": "FMAU", "site": "https://www.fmau.fr", "city": "La Rochelle", "country": "France",
     "include": r"^/projet/\d+-", "listing_url": "https://www.fmau.fr/", "link_prefix": "/projet/"},
    {"name": "Tank Architectes", "site": "https://www.tank.fr", "city": "Lille", "country": "France",
     "include": r"^/projets/[^/]+", "listing_url": "https://www.tank.fr/projets", "link_prefix": "/projets/"},
    # NOTE: arba pages only expose the site-wide OG image to the extractor; the real photos were patched
    # into houses.json by hand from /images/realisations/<slug>/ - a --replace rerun would undo that.
    {"name": "arba", "site": "https://arba.pro", "city": "Paris", "country": "France",
     "include": r"^/realisations/[^/]+", "listing_url": "https://arba.pro/realisations/", "link_prefix": "/realisations/"},
    {"name": "Bodenez + Le Gal La Salle", "site": "https://www.bodenezlegallasalle.com", "city": "Rennes", "country": "France",
     "include": r"^/projets/[^/]+", "listing_url": "https://www.bodenezlegallasalle.com/projets", "link_prefix": "/projets/"},
    {"name": "Studio Razavi", "excluded": "project pages gave no locations/descriptions and many are unbuilt or urban interiors; needs a per-slug hand-written entry", "site": "https://studiorazavi.com", "city": "Paris", "country": "France",
     "include": r"^/work/[^/]+", "listing_url": "https://studiorazavi.com/work", "link_prefix": "/work/"},
]


def merge_houses(existing, new):
    """Pure: append `new` houses whose URL is not already present; returns
    (merged_list, number_added). Order of existing houses is preserved."""
    seen = {h["url"].rstrip("/") for h in existing}
    merged, added = list(existing), 0
    for h in new:
        key = h["url"].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        merged.append(h)
        added += 1
    return merged, added


# Quality filters (pure, applied identically to live and rebuilt results).
# Bar from project memory: renovation/refurbishment ALONE is excluded; a
# renovation WITH a genuine extension/addition is included.
RENOVATION_RE = re.compile(r"renovat|remodel|refurbish|alteration|reconfigur|refit|modernis|modernized|reorganiz", re.I)
EXTENSION_RE = re.compile(r"\b(extension|extended|extend|addition|added|adds|new[- ]build|new house|newly built|new construction|new concrete|expanded|expands|doubles)\b", re.I)
LISTING_SLUGS = {"work", "works", "projects", "projekte", "projekt", "archive", "portfolio", "residential", "houses", "casas"}


def is_renovation_only(name, description):
    text = f"{name or ''} {description or ''}"
    return bool(RENOVATION_RE.search(text)) and not EXTENSION_RE.search(description or "")


def is_listing_url(url):
    last = urlparse(url).path.rstrip("/").split("/")[-1].lower()
    return last in LISTING_SLUGS


def clean_location(loc):
    """A location may arrive as a whole info block ("Location／Mibu, Tochigi,
    Japan / Principal use／... / Family／...", Tato) - keep just the place."""
    if not loc:
        return loc
    m = re.search(r"Location\s*[／/:：]\s*([^\n\r]+)", loc)
    place = (m.group(1) if m else loc.splitlines()[0]).strip()
    return place or None


def filled(h):
    return sum(1 for k in ("location", "year", "description") if h.get(k))


# Hand curation of the 2026-10-03 England/France batch: pages the classifier
# let through that are conversions, extensions-only, apartments, housing
# schemes or public buildings, so a --replace rerun does not bring them back.
CURATED_DROPS = {
    "Sandy Rendel Architects": {"the old cycle club"},
    "Sanei + Hopkins Architects": {"secret garden", "extension, north london", "artists studio, london",
                                   "leamington road villas, london w11", "the extension, london"},
    "Gianni Botsford Architects": {"the old byre", "sustainable low cost ceb dwellings"},
    "Haysom Ward Miller Architects": {"cottage extension", "listed barn house"},
    "MawsonKerr Architects": {"gosforth residential reworking", "rectory road gosforth house extension",
                              "jesmond house", "luanda house"},
    "Avignon Architecte": {"penthouse sur loire", "barrettes de chic"},
    "Bodenez + Le Gal La Salle": {"maison caméléon", "maison gutenberg", "maison surélévation", "maison malouinière"},
    "Surman Weston": {"lantern studio"},
}
# page titles that are not the project's name
NAME_FIXES = {("arba", "realisations/entre-les-murs"): "Entre les murs",
              ("FMAU", "projet/136-"): "Maison cardio", ("FMAU", "projet/148-"): "Bella vita"}


def _curate(firm_name, house):
    name = (house["name"] or "").strip().lower()
    if name in CURATED_DROPS.get(firm_name, ()) or name.startswith("extension and remodel, holland park"):
        return None
    if firm_name == "Bodenez + Le Gal La Salle" and any(
            frag in house["url"] for frag in ("immeuble-collectif", "maison-renovation-rennes", "lancieux-maison-patrimoine",
                                                           "maison-2-en-1", "maison-sur-la-pente-frehel")):
        return None  # renovation/apartment/heritage pages that carry another project's title ("Maison sur la pente")
    for (f, frag), fixed in NAME_FIXES.items():
        if f == firm_name and frag in house["url"]:
            house["name"] = fixed
    return house


def houses_from_results(firm_name, results):
    """Pure: houses (with a real photo) from a firm's per-page extraction
    results, minus renovation-only projects, listing pages and same-name
    duplicates (keeping the record with more metadata). Returns
    (houses, dropped) where dropped is a list of (name, reason)."""
    kept, dropped = {}, []
    for r in results:
        if not (r.get("is_house") and r.get("image")) or str(r.get("image")).startswith("data:"):
            continue
        if is_listing_url(r["url"]):
            dropped.append((r.get("name"), "listing page")); continue
        if is_renovation_only(r.get("name"), r.get("description")):
            dropped.append((r.get("name"), "renovation only")); continue
        house = {"name": r.get("name"), "location": clean_location(r.get("location")), "region": None, "year": r.get("year"),
                 "description": r.get("description"), "image": r["image"], "url": r["url"], "firm": firm_name}
        house = _curate(firm_name, house)
        if house is None:
            dropped.append((r.get("name"), "curated out")); continue
        key = (r.get("name") or "").strip().lower()
        if key in kept:
            dropped.append((r.get("name"), "duplicate name"))
            if filled(house) > filled(kept[key]):
                kept[key] = house
            continue
        kept[key] = house
    return list(kept.values()), dropped


def firm_record(firm):
    return {
        "name": firm["name"], "url": firm["site"] + "/", "specialization": ["Architect"],
        "city": firm["city"], "country": firm["country"], "email": "", "phone": "",
        "source": SOURCE_TAG, "scrapable": True, "photos": [], "needs_review": False,
    }


def discover_links(page, firm):
    """Project-page URLs for one firm: sitemap first, listing page fallback."""
    base = firm["site"].rstrip("/")
    include = re.compile(firm["include"])
    exclude = re.compile(firm["exclude"], re.I) if firm.get("exclude") else None
    paths = [p for p in _site_sitemap_paths(base, firm.get("sitemap_url")) if include.search(p) and not (exclude and exclude.search(p))]
    seen, uniq = set(), []
    for p in paths:
        k = p.rstrip("/")
        if k and k not in seen:
            seen.add(k)
            uniq.append(base + p)
    if len(uniq) >= MIN_SITEMAP_PATHS:
        return uniq, "sitemap"
    listing = {"url": firm["listing_url"], "nav_click_text": None, "link_prefix": firm.get("link_prefix")}
    links = [l for l in discover_project_links(page, listing)
             if include.search(urlparse(l).path) and not (exclude and exclude.search(urlparse(l).path))]
    return links, "listing"


def run_firm(page, firm, dry_run=False):
    print(f"=== {firm['name']} ===")
    base = firm["site"].rstrip("/")
    robots = _site_robots(base)
    if not robots.can_fetch("FormgroundBot", base + "/"):
        print("  robots.txt disallows crawling - skipping.")
        return {"links": 0, "houses": [], "skipped": "robots"}
    links, how = discover_links(page, firm)
    print(f"  {len(links)} candidate project pages via {how}")
    if dry_run:
        for l in links[:6]:
            print("   ", l)
        return {"links": len(links), "houses": [], "all": []}
    all_results = []
    for link in links[:LINK_CAP]:
        if not robots.can_fetch("FormgroundBot", link):
            continue
        try:
            page.goto(link, timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            text = extract_page_content(page)
        except Exception as e:
            print(f"  fetch error {link}: {str(e)[:80]}")
            continue
        extracted = call_claude_extract(text)
        time.sleep(PAGE_DELAY)
        if not extracted:
            continue
        extracted["url"] = link
        # Per-firm overrides: some sites hold an English title/location in a
        # dedicated element while the page title is another language (Tato).
        for field, selector in (("name", firm.get("name_selector")), ("location", firm.get("location_selector"))):
            if selector:
                try:
                    value = page.inner_text(selector, timeout=2000).strip()
                    if value:
                        extracted[field] = value
                except Exception:
                    pass
        image = None
        if extracted.get("is_house"):
            try:
                # lazy-loaded galleries (Gatsby, Squarespace) only swap in the
                # real image after a scroll; until then <img> is a data: SVG
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1200)
                page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass
            candidates = []
            token = firm.get("strip_thumb")
            if token:
                # gallery serves 400px thumbnails (e.g. "x_thumb.jpg"); the
                # full-size file is the same URL without the token.
                thumbs = page.eval_on_selector_all("img", "(els, t) => els.map(e => e.src).filter(s => s.includes(t))", token)
                candidates += [t.replace(token, "") for t in thumbs]
            candidates += candidate_images(page)
            for candidate in dict.fromkeys(c for c in candidates if not c.startswith("data:")):
                if is_architecture_relevant(candidate):
                    image = candidate
                    break
        extracted["image"] = image
        all_results.append(extracted)
        mark = "HOUSE" if extracted.get("is_house") else "skip"
        print(f"  [{mark}][{'img' if image else ('NO-IMG' if extracted.get('is_house') else '-')}] {link.replace(base, '')} -> {extracted.get('name')}")
    houses, dropped = houses_from_results(firm["name"], all_results)
    if dropped:
        print(f"  dropped by quality filters: {dropped}")
    return {"links": len(links), "houses": houses, "all": all_results}


def _merge_and_save(firms, report, replace=False):
    houses = json.loads(HOUSES_PATH.read_text())
    if replace:
        # a rerun REPLACES the selected firms' houses instead of keeping old records
        names = {f["name"] for f in firms}
        houses = [h for h in houses if h["firm"] not in names]
    architects = json.loads(ARCHITECTS_PATH.read_text())
    have_firms = {a["name"] for a in architects}
    total_added = 0
    for firm in firms:
        new = report[firm["name"]]["houses"]
        houses, added = merge_houses(houses, new)
        total_added += added
        if added and firm["name"] not in have_firms:
            architects.append(firm_record(firm))
    HOUSES_PATH.write_text(json.dumps(houses, indent=2, ensure_ascii=False))
    ARCHITECTS_PATH.write_text(json.dumps(architects, indent=2, ensure_ascii=False))

    print("\n--- Summary ---")
    for firm in firms:
        r = report[firm["name"]]
        print(f"{firm['name']}: {r['links']} pages, {len(r['houses'])} houses with a real photo"
              + (f" ({r.get('skipped') or r.get('error')})" if r.get("skipped") or r.get("error") else ""))
    print(f"Added {total_added} houses; houses.json now {len(houses)}, architects.json {len(architects)}.")



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firm", action="append", default=None, help="run only this firm (exact name); repeat for several")
    parser.add_argument("--dry-run", action="store_true", help="discover pages only; no API calls, no writes")
    parser.add_argument("--replace", action="store_true",
                        help="drop the selected firms' existing houses before merging (use for reruns/rebuilds)")
    parser.add_argument("--from-raw", action="store_true",
                        help="rebuild houses from today's saved raw results (no browsing): re-applies the quality filters")
    args = parser.parse_args()
    wanted = {n.lower() for n in args.firm or []}
    firms = [f for f in BATCH if not wanted or f["name"].lower() in wanted]
    if not firms:
        sys.exit(f"No firm named {args.firm!r} in BATCH.")
    for f in firms:
        if f.get("excluded"):
            print(f"Skipping {f['name']}: {f['excluded']}")
    firms = [f for f in firms if not f.get("excluded")]
    if not firms:
        sys.exit("Nothing to run.")

    report = {}
    if args.from_raw:
        raw_path = DATA_DIR / f"architect_batch_{time.strftime('%Y-%m-%d')}.json"
        raw = json.loads(raw_path.read_text())
        for firm in firms:
            results = raw.get(firm["name"], [])
            houses_, dropped = houses_from_results(firm["name"], results)
            report[firm["name"]] = {"links": len(results), "houses": houses_, "all": results}
            print(f"{firm['name']}: {len(houses_)} houses from {len(results)} saved pages; dropped {dropped}")
        _merge_and_save(firms, report, replace=args.replace)
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for firm in firms:
            try:
                report[firm["name"]] = run_firm(page, firm, dry_run=args.dry_run)
            except Exception as e:
                print(f"  FIRM FAILED: {type(e).__name__}: {str(e)[:120]}")
                report[firm["name"]] = {"links": 0, "houses": [], "error": str(e)[:200]}
        browser.close()
    if args.dry_run:
        return

    raw_path = DATA_DIR / f"architect_batch_{time.strftime('%Y-%m-%d')}.json"
    existing_raw = json.loads(raw_path.read_text()) if raw_path.exists() else {}
    existing_raw.update({k: v.get("all", []) for k, v in report.items()})
    raw_path.write_text(json.dumps(existing_raw, indent=2, ensure_ascii=False))

    _merge_and_save(firms, report, replace=args.replace)


if __name__ == "__main__":
    main()
