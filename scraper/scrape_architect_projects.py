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

SCRAPER_DIR = Path(__file__).parent
load_dotenv(SCRAPER_DIR.parent / "backend" / ".env")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TEXT_MODEL = "claude-haiku-4-5-20251001"

# All 10 firms confirmed 2026-09-19 (real manual browsing this session) to
# pass the dual bar: real individually-designed houses exist, and the firm's
# real work is contemporary/modern (not restoration, not large-scale
# multi-unit/commercial only). Excluded: LZN (no real project data), Aldén
# Arkitektur (restoration-focused), Yep Arkitekter (institutional/commercial),
# Siegel (large-scale apartment blocks only) - see project memory
# (architects_craftspeople_search_gap.md) for the full reasoning.
ALL_FIRMS = [
    {
        "name": "Björn Lundquist Arkitektur AB",
        "url": "https://www.bjornlundquist.se/",
        "nav_click_text": None,
        "link_prefix": "/work/",
    },
    {
        "name": "Ascape Arkitektur AB",
        "url": "https://www.ascape.se/",
        "nav_click_text": "Projekt",  # client-side rendered, needs a real click
        "link_prefix": None,
    },
    {
        "name": "Arkitekt Lotta Lander",
        "url": "http://www.lottalander.se/",
        "nav_click_text": None,
        "link_prefix": None,
    },
    {
        "name": "Malmström Edström Arkitekter Ingenjörer AB",
        "url": "https://www.malmstromedstrom.se/projekt-arkiv/",
        "nav_click_text": None,
        "link_prefix": "/projekt/",
    },
    {
        "name": "Arkitektkontor Arén & Yde AB",
        "url": "https://aren-yde.se/projekt-privatbostader/",
        "nav_click_text": None,
        "link_prefix": None,
    },
    {
        "name": "Accent Arkitekter AB",
        "url": "http://accentarkitekter.se/projekt/",
        "nav_click_text": None,
        "link_prefix": None,
    },
    {
        "name": "Andersson Arfwedson arkitekter AB",
        "url": "https://www.andersson-arfwedson.se/projekt/",
        "nav_click_text": None,
        "link_prefix": "/projekt/",
    },
    {
        "name": "Dahlberg Busnardo Arkitektur & Landskap AB",
        "url": "https://dabuark.se/work/",
        "nav_click_text": None,
        "link_prefix": None,
    },
    {
        "name": "Kontrast AB",
        "url": "https://kontrastarkitekter.se/projekt",
        "nav_click_text": None,
        "link_prefix": "/projekt/",
    },
    {
        "name": "Åbergs Arkitektkontor AB",
        "url": "https://abergsarkitektkontor.se/privat/",
        "nav_click_text": None,
        "link_prefix": None,
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
                if extracted:
                    extracted["url"] = link
                    firm_results.append(extracted)
                    mark = "HOUSE" if extracted.get("is_house") else "skip"
                    print(f"  [{mark}] {link} -> {extracted.get('name')}")
                time.sleep(0.3)
            results[firm["name"]] = firm_results
        browser.close()

    out_path = SCRAPER_DIR.parent / "data" / "architect_projects_test.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
