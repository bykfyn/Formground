"""
Formground agent-facing docs generator.

WHAT THIS DOES: writes two static files an AI agent or crawler can find on
the main domain, generated (not hand-written) so the counts and the
browse-page list never go stale:

  docs/llms.txt      llmstxt.org-style site summary: what Formground is,
                     how to search it, how to read price fields, where the
                     full static catalog pages are.
  docs/openapi.json  OpenAPI 3 description of the ONE public machine route,
                     /agent/search, taken from the real FastAPI app so it
                     cannot drift from the code. The site's own UI routes
                     (/search, /search/more, /discover, /event) are
                     deliberately left out - they are not a public API.

WHY HERE: the search backend lives on Cloud Run's own hostname, but
agents look for llms.txt and an API description on the site's own domain.

RUN (after generate_browse_pages.py, so the browse list is current):
    python3 generate_agent_docs.py
"""

import datetime
import json
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
sys.path.insert(0, str(SCRAPER_DIR.parent / "backend"))

import query_engine as qe  # noqa: E402
from generate_browse_pages import BROWSE_CATEGORIES, GROUP_ORDER  # noqa: E402
from generate_brand_pages import SITE_URL  # noqa: E402

API_BASE = "https://formground-git-182928637479.europe-west1.run.app"


def _catalog_counts():
    import sqlite3
    conn = sqlite3.connect(str(qe.DB_PATH))
    rows = conn.execute(
        "SELECT brand FROM products WHERE image_url IS NOT NULL AND image_url != '' "
        "AND COALESCE(link_dead, 0) = 0"
    ).fetchall()
    conn.close()
    brands = {b for (b,) in rows if b not in qe.HIDDEN_BRANDS}
    products = sum(1 for (b,) in rows if b not in qe.HIDDEN_BRANDS)
    return products, len(brands)


def build_openapi():
    """The real app's spec, reduced to the public agent route."""
    import main  # backend/main.py
    full = main.app.openapi()
    return {
        "openapi": full["openapi"],
        "info": {
            "title": "Formground agent search",
            "version": full["info"]["version"],
            "description": full["info"]["description"],
            "contact": {"url": f"{SITE_URL}/contact.html"},
        },
        "servers": [{"url": API_BASE}],
        "paths": {"/agent/search": full["paths"]["/agent/search"]},
    }


def build_llms_txt():
    products, brands = _catalog_counts()
    import work_menu
    browse_lines = []
    for cat, slug in work_menu.CATEGORY_SLUGS.items():
        if cat == "Houses":
            browse_lines.append(f"- [Houses]({SITE_URL}/work/houses.html): every architect-designed house in the catalog, with country pages (e.g. {SITE_URL}/work/houses-sweden.html), each house linking to the architect's own project page")
            continue
        groups = work_menu.TAXONOMY[cat]
        types = [c for g in groups for c in BROWSE_CATEGORIES if c["group"] == g]
        links = ", ".join(f"[{c['title']}]({SITE_URL}/work/{c['slug']}.html)" for c in types)
        browse_lines.append(f"- [{cat}]({SITE_URL}/work/{slug}.html): {links}")
    today = datetime.date.today().isoformat()
    return f"""# Formground

> Formground helps people discover furniture, lighting and objects from independent makers. It indexes {products:,} products from {brands} makers and links every result straight to the maker's own site. It sells nothing and shows no paid results in search.

Generated {today}; the catalog is re-scraped weekly. Prices and availability belong to the makers - always send people to the maker's own page (the `url` field), not to Formground.

## Search (machine-readable)

- [Agent search API]({API_BASE}/agent/search?q=round+dining+table): GET, no authentication. Natural-language query in `q` (product type, material, colour, maker country, seat count are understood). Returns schema.org Product-shaped JSON, balanced across makers so no single brand dominates.
- [OpenAPI description]({SITE_URL}/openapi.json): the exact request and response schema.

## Reading the price fields

- `priceStatus` is always present: `listed` (price and currency both known, see `offers`), `on_request` (the maker prices on application or to commission - send an enquiry), `dealer_priced` (the maker sets no public price; stockists do), or `unknown` (no data, no claim).
- A missing price is often correct, not an error: many makers do not publish prices. Do not estimate one.
- `offers.price` is exactly what the maker lists, in the maker's own currency (`offers.priceCurrency`, ISO 4217). Nothing is converted. Compare across currencies yourself if you need to.

## Browse the full catalog by type (static pages under /work/, every match listed)

- [Work]({SITE_URL}/work.html): search and the browse menu. {len(BROWSE_CATEGORIES)} product types in three categories, each type listed in full and paginated, with schema.org Product data on every page.
{chr(10).join(browse_lines)}

## Curated and reference pages

- [Edits]({SITE_URL}/edits.html): hand-picked selections by theme.
- [Makers]({SITE_URL}/makers.html): every maker, one page each at {SITE_URL}/brands/{{maker-slug}}.html listing their full range.
- [Designers]({SITE_URL}/designers.html): independent product designers and their pieces.
- [New arrivals]({SITE_URL}/new.html): pieces added in the last 90 days.
- [Sitemap]({SITE_URL}/sitemap.xml)

## Notes

- Categories are normalized by Formground and are not always the maker's own wording; footstools, ottomans/poufs and stools are separate types, as are candle holders and candles.
- `tier` is hand-curated: `established` marks a well-known or multinational design house, everything else is `independent`.
- Please keep request volume modest. Questions or corrections: [contact]({SITE_URL}/contact.html).
"""


def generate():
    (DOCS_DIR / "openapi.json").write_text(json.dumps(build_openapi(), indent=2, ensure_ascii=False) + "\n")
    (DOCS_DIR / "llms.txt").write_text(build_llms_txt())
    print("Wrote docs/openapi.json and docs/llms.txt")


if __name__ == "__main__":
    generate()
