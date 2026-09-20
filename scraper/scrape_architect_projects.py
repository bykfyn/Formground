"""
Architect per-project ("house as product") extractor - test/prototype pass.

WHAT THIS DOES:
  For a hardcoded list of firms already confirmed (2026-09-19, real manual
  browsing this session) to have genuine individually-named house/project
  pages, renders each firm's project listing with a real browser (Playwright -
  plain `requests` misses client-side-rendered nav entirely, confirmed live
  on Ascape's site), follows links that look like individual project pages,
  and asks Claude (text only, cheap model) to extract structured fields and
  classify whether each one is genuinely an individual house - not a
  multi-family building, commercial premises, public building, or a pure
  restoration of an existing structure. See project memory
  (architects_craftspeople_search_gap.md) for why this bar exists.

STATUS: prototype, testing against 2 firms (Björn Lundquist, Ascape) before
scaling to the other 8 confirmed-qualifying firms.

2026-09-20 UPDATE: the curated firm list (scraper/architects.json) was
entirely replaced with 16 new candidates sourced from ArchDaily/Divisare/
Architizer (editorially curated for design quality, per the user's own
finding that the prior Sveriges Arkitekter member-list source wasn't
style-vetted at all - zero overlap between the two pools). Real-site
survey that same day found 12 of the 16 have genuine, separately-URLed
project pages; the other 4 (Metropolis Arkitekter, Mikael Bergquist/
mba.nu, Jonas Lindvall, GIPP Arkitektur) don't - no real per-project
links exist in their page DOM (spatial-nav grid, stale Blogspot, image-
only slideshow, unlabeled JS gallery), so they're excluded here, same as
LZN/Aldén/Yep/Siegel were excluded from the original 10 for their own
reasons. Reppen Vilson (also from the new sourcing) is ALSO excluded
here even though it has real project names - they live as same-page
hash anchors with no separate URL per project, so this page's per-URL
fetch model can't isolate one project's content from the rest; it would
need bespoke DOM-scoped extraction, not attempted this pass. ALL_FIRMS
below is now the new 11, replacing the original 10 (that earlier batch
already shipped as the previous docs/architects/ roster and is being
fully replaced, not extended - see the user's own instruction to
replace, not add to, the old roster).

RUN: python3 scrape_architect_projects.py
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from scrape_architects import is_architecture_relevant

SCRAPER_DIR = Path(__file__).parent
load_dotenv(SCRAPER_DIR.parent / "backend" / ".env")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TEXT_MODEL = "claude-haiku-4-5-20251001"

# The new 11 (2026-09-20), real-browsed to find each firm's actual project
# listing page and URL pattern - see the module docstring for why 5 of the
# 16 new candidates (Metropolis, mba.nu, Jonas Lindvall, GIPP, Reppen Vilson)
# aren't here. "url" is each firm's real project-listing page, not
# necessarily its homepage - matches the pattern already established below
# (e.g. Andersson Arfwedson's old entry pointed straight at /projekt/).
ALL_FIRMS = [
    {
        "name": "Arrhov Frick Arkitektkontor",
        "url": "http://www.arrhovfrick.se/archive",
        "nav_click_text": None,
        "link_prefix": None,  # no shared prefix - real projects are root-level slugs
    },
    {
        "name": "Elding Oscarson",
        "url": "https://www.eldingoscarson.com/work",
        "nav_click_text": None,
        "link_prefix": "/work/",
    },
    {
        "name": "Förstberg Ling",
        "url": "https://www.forstbergling.com/",
        "nav_click_text": None,
        "link_prefix": "/work/",
    },
    {
        "name": "Murman Arkitekter",
        "url": "https://www.murman.se/projekt/",
        "nav_click_text": None,
        "link_prefix": None,  # no shared prefix - real projects are root-level slugs
    },
    {
        "name": "Ateljé Ö",
        "url": "https://ateljeo.se/archive/",
        "nav_click_text": None,
        "link_prefix": "/archive/",
    },
    {
        "name": "Kolman Boye Architects",
        "url": "https://kolmanboye.se/works/",
        "nav_click_text": None,
        "link_prefix": "/project/",
    },
    {
        "name": "Jägnefält Milton",
        "url": "https://jagnefaltmilton.se/selected/",
        "nav_click_text": None,
        "link_prefix": "/catalogue/",
    },
    {
        "name": "Johan Sundberg Arkitektur",
        "url": "https://www.johansundberg.com/projekt",
        "nav_click_text": None,
        "link_prefix": "/projekt/alla/privatbostader/",
    },
    {
        "name": "Tham & Videgård Arkitekter",
        "url": "https://www.tvark.se/works",
        "nav_click_text": None,
        "link_prefix": "/work/",
    },
    {
        "name": "Karlsson/Lauri Arkitekter",
        "url": "https://www.karlssonlauri.se/work",
        "nav_click_text": None,
        "link_prefix": None,  # no shared prefix - real projects are root-level slugs
    },
    {
        "name": "CAMPUS",
        "url": "https://www.thecampus.se/buildings",
        "nav_click_text": None,
        "link_prefix": "/buildings/",
    },
]

LINK_CAP_PER_FIRM = 40  # bounded run, not unlimited - see feedback_resource_conscious_scraping.md

EXTRACT_PROMPT = """You are looking at the text content of a page from an architecture firm's website, describing one project.

Return ONLY a JSON object, no other text, with these fields:
- "is_house": true only if this is a single, individually-designed house (a private home, villa, vacation house, or similar single-dwelling residence) that this firm designed. false for: multi-family/apartment buildings, commercial or office buildings, public buildings (schools, museums, churches), industrial buildings, agricultural/outbuildings (garages, stables), landscape/urban projects, or a restoration/conservation project on an existing older building where this firm did not design the original structure.
- "name": the project's real name as given on the page (or null if none)
- "location": city/place mentioned (or null)
- "year": year or year range mentioned (or null)
- "description": one honest sentence summarizing the house and its notable materials/features, using only what's actually in the text (or null if there's not enough real content to summarize)

Page text:
---
{text}
---"""


def call_claude_extract(text):
    if not ANTHROPIC_API_KEY:
        print("  (no ANTHROPIC_API_KEY set - skipping extraction)")
        return None
    if not text or len(text.strip()) < 8:
        return {"is_house": False, "name": None, "location": None, "year": None, "description": None}
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": TEXT_MODEL,
                "max_tokens": 300,
                "messages": [{"role": "user", "content": EXTRACT_PROMPT.format(text=text[:4000])}],
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"].strip()
        # Strip markdown code fences if the model wrapped the JSON in them.
        if content.startswith("```"):
            content = content.split("```")[1].removeprefix("json").strip()
        return json.loads(content)
    except Exception as e:
        print(f"    extract error: {e}")
        return None


def discover_project_links(page, firm):
    page.goto(firm["url"], timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    if firm["nav_click_text"]:
        try:
            page.get_by_text(firm["nav_click_text"], exact=True).first.click(timeout=5000)
            page.wait_for_timeout(1500)
        except Exception as e:
            print(f"  couldn't click '{firm['nav_click_text']}': {e}")

    links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    # Same-domain, not path-prefix - a real bug found running this: Arén &
    # Yde's real project pages live under /projects-item/, a totally
    # different path than the /projekt-privatbostader/ entry page, which an
    # earlier same-path-prefix check silently missed (0 links found).
    domain = urlparse(firm["url"]).netloc
    seen = []
    for link in links:
        if firm["link_prefix"] and firm["link_prefix"] in link:
            if link not in seen:
                seen.append(link)
        elif not firm["link_prefix"] and urlparse(link).netloc == domain and link != firm["url"] and link.rstrip("/") != firm["url"].rstrip("/"):
            # Heuristic for firms with no known prefix yet: same-domain links
            # that aren't just the homepage/anchors - narrowed further by hand
            # once real output is inspected.
            if "#" not in link and link not in seen:
                seen.append(link)
    return seen


def extract_page_content(page):
    """Body text alone misses pure-gallery pages with almost no prose (found
    running this on Arkitekt Lotta Lander's Squarespace site - real project
    pages there have essentially empty body text, but the page <title> and
    image alt attributes carry the real signal, e.g. title "Christinas hus").
    Combine all three rather than relying on body text alone."""
    title = page.title()
    body_text = page.inner_text("body")
    alts = page.eval_on_selector_all("img[alt]", "els => els.map(e => e.alt).filter(a => a && a.length > 2)")
    parts = [f"Page title: {title}"]
    if alts:
        parts.append("Image captions: " + "; ".join(alts[:20]))
    if body_text.strip():
        parts.append(body_text)
    return "\n\n".join(parts)


def candidate_images(page):
    """Ordered list of real-photo candidates for one project page: og:image
    first (a portfolio site's own chosen representative image for the
    page), then every other rendered <img> large enough to not be a logo/
    icon/nav thumbnail (naturalWidth > 400), largest first. Returns a list,
    not one answer, because og:image is sometimes a floor plan or process
    sketch rather than a finished-building photo (confirmed live on Arrhov
    Frick's site) - main() vision-checks candidates in this order and
    takes the first that's a real building/interior photo.

    eval_on_selector_all, not eval_on_selector, for the og:image lookup -
    confirmed live on Murman's site (no og:image tag at all): the single-
    element version throws when zero elements match instead of returning
    null, which was silently killing extraction for the whole page, not
    just the image, since both shared one try/except in main()."""
    og_images = page.eval_on_selector_all('meta[property="og:image"]', "els => els.map(e => e.content)")
    other_images = page.eval_on_selector_all(
        "img",
        """els => els
            .filter(e => e.naturalWidth > 400 && e.naturalHeight > 300)
            .sort((a, b) => (b.naturalWidth * b.naturalHeight) - (a.naturalWidth * a.naturalHeight))
            .map(e => e.src)""",
    )
    seen = []
    for src in og_images + other_images:
        if not src:
            continue
        # Upgraded to https unconditionally, not just when the domain is
        # known to support it - confirmed live 2026-09-20 on real pushed
        # data: an http:// image URL is already unusable on formground.com
        # (an https page) regardless of source-domain support, since
        # browsers block/fail to fetch it as mixed content. Rewriting to
        # https can only help (the 4-of-5 real domains checked that day
        # all supported it fine) and never makes an already-broken image
        # worse. A domain with truly no HTTPS at all (confirmed that day
        # for arrhovfrick.se) still needs its images rehosted by hand -
        # this doesn't solve that case, just stops it from being silent.
        if src.startswith("http://"):
            src = "https://" + src[len("http://"):]
        if src not in seen:
            seen.append(src)
    return seen


def main():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for firm in ALL_FIRMS:
            print(f"=== {firm['name']} ===")
            links = discover_project_links(page, firm)
            print(f"  found {len(links)} candidate links")
            firm_results = []
            for link in links[:LINK_CAP_PER_FIRM]:
                try:
                    page.goto(link, timeout=15000, wait_until="domcontentloaded")
                    page.wait_for_timeout(800)
                    text = extract_page_content(page)
                except Exception as e:
                    print(f"  fetch error {link}: {e}")
                    continue
                extracted = call_claude_extract(text)
                if not extracted:
                    continue
                extracted["url"] = link
                image = None
                img_mark = "skip"
                if extracted.get("is_house"):
                    # Vision-check candidates in order, cheapest-first
                    # (skip the check entirely for non-houses - their
                    # image is never used, so it's not worth the API
                    # call). Confirmed live on Arrhov Frick: og:image is
                    # sometimes a floor plan or process sketch, not a
                    # finished-building photo - the vision check (already
                    # built for this exact case in scrape_architects.py)
                    # catches that instead of silently using the wrong
                    # image or, worse, none at all.
                    for candidate in candidate_images(page):
                        if is_architecture_relevant(candidate):
                            image = candidate
                            break
                    img_mark = "img" if image else "NO-REAL-IMG"
                extracted["image"] = image
                firm_results.append(extracted)
                mark = "HOUSE" if extracted.get("is_house") else "skip"
                print(f"  [{mark}][{img_mark}] {link} -> {extracted.get('name')}")
                time.sleep(0.3)
            results[firm["name"]] = firm_results
        browser.close()

    out_path = SCRAPER_DIR.parent / "data" / "architect_projects_test.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
