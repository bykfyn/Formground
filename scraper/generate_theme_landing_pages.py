"""
Formground Theme Landing Page generator.

WHAT THIS DOES: generates dedicated, real static SEO/ad landing pages
(docs/{slug}.html) for specific long-tail search themes, reusing the
exact same category/style/geography filtering already live in
backend/query_engine.py's filter_products() - not a separate
reimplementation - so what an ad promises is exactly what /work.html's
own search would also return for the same query.

WHY THIS EXISTS: work.html?q=... already returns these same results,
but a generic search-results page has no dedicated <title>/H1/meta
description matching an ad's exact keyword, and doesn't read as a real
landing page for ad quality-score purposes. These are additive,
purpose-built pages for the locked ad-keyword shortlist (see
project-docs/FORMGROUND_STRATEGY_28.md, kept local/private) - not a
replacement for /work.html, which still does everything these pages do
and more (free-text search, every other category/theme).

THEMES BUILT (2026-09-28), real counts at build time: floor lamp (238),
round dining table (36), round coffee table (23 - thin, flagged as a
scraping-priority follow-up per feedback_advertising_drives_content),
scandinavian dining table (149).

THEMES DELIBERATELY NOT BUILT: "modern vase" and "contemporary
ceramics" were also on the same shortlist, but "modern"/"contemporary"
are confirmed no-ops against the real style-descriptor narrowing today
(0 of 2752/784 products get excluded either way - there's no aesthetic
attribute in the data, just literal name-text matching, and these words
essentially never appear in product names). A dedicated page for either
would show the exact same content as the existing bare vase/ceramics
search while promising something narrower in its own title - so those
two route straight to /work.html?q=vase / ?q=ceramics instead, until a
real hand-curated "designer tier" exists across vases/ceramics/lighting
together (see project memory).

RUN (after generate_brand_pages.py, since it needs sitemap.xml and
appends to it):
    python3 generate_theme_landing_pages.py
"""

import html
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
SITEMAP_PATH = DOCS_DIR / "sitemap.xml"
BACKEND_DIR = SCRAPER_DIR.parent / "backend"

sys.path.insert(0, str(BACKEND_DIR))
import query_engine as qe  # noqa: E402

from generate_brand_pages import (  # noqa: E402
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_NAV_HTML,
    SITE_URL,
    product_card_html,
)

# Each theme's `intent` is passed straight to query_engine.filter_products()
# - the identical function /work.html's own search calls - so these pages
# can never drift out of sync with what search itself returns for the
# same phrase.
THEMES = [
    {
        "slug": "floor-lamps",
        "title": "Floor Lamps",
        "intent": {"category": "floor lamp"},
        "intro": "Floor lamps from independent makers - every result links straight to the maker's own site.",
    },
    {
        "slug": "round-dining-tables",
        "title": "Round Dining Tables",
        "intent": {"category": "dining table", "style_descriptors": ["round"]},
        "intro": "Round dining tables from independent makers - every result links straight to the maker's own site.",
    },
    {
        "slug": "round-coffee-tables",
        "title": "Round Coffee Tables",
        "intent": {"category": "coffee table", "style_descriptors": ["round"]},
        "intro": "Round coffee tables from independent makers - every result links straight to the maker's own site.",
    },
    {
        "slug": "scandinavian-dining-tables",
        "title": "Scandinavian Dining Tables",
        "intent": {"category": "dining table", "countries": ["Sweden", "Denmark", "Norway"]},
        "intro": "Dining tables from Swedish, Danish, and Norwegian makers - new work by independent, living designers, not a vintage or antiques listing. Every result links straight to the maker's own site.",
    },
]


def render_theme_page(theme, products):
    slug = theme["slug"]
    title = theme["title"]
    page_url = f"{SITE_URL}/{slug}.html"
    n = len(products)
    description = f"{n} real {title.lower()}{'' if title.lower().endswith('s') else 's'}, from independent makers. {theme['intro']}"

    if products:
        cards = "".join(product_card_html(p, show_brand=True) for p in products)
        body = f'<div class="grid">{cards}</div>'
    else:
        body = '<p class="empty-state">Check back soon - new pieces are added here as they are found.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)} — Formground">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/favicon-192x192.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{html.escape(title)} — Formground">
<meta name="twitter:description" content="{html.escape(description)}">
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline">Discover design from makers.</p>
  <h1>{html.escape(title)}</h1>
  <p class="category-intro">{html.escape(theme["intro"])}</p>
  {body}
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/work.html">Search everything</a> &middot; <a href="/about.html">About</a>
  </p>
</main>
<script>
  // Same fix as render_new_page/render_brand_page's own script (see
  // project memory) - these cards come from the same
  // product_card_html()/.card-image markup, so they need the same
  // aspect-ratio safety net.
  document.querySelectorAll(".card-image img").forEach(function (img) {{
    img.addEventListener("load", function () {{
      var ratio = img.naturalWidth / img.naturalHeight;
      if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
    }});
  }});
</script>
<script>{CARD_CLICK_TRACKING_JS}</script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def append_to_sitemap(slugs):
    if not SITEMAP_PATH.exists():
        print(f"Warning: {SITEMAP_PATH} not found - run generate_brand_pages.py first. Skipping sitemap update.")
        return
    import datetime

    today = datetime.date.today().isoformat()
    text = SITEMAP_PATH.read_text()
    new_entries = []
    for slug in slugs:
        loc = f"{SITE_URL}/{slug}.html"
        if loc in text:
            continue
        new_entries.append(
            f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.6</priority>\n  </url>"
        )
    if not new_entries:
        print("Sitemap already has all theme landing page entries - regenerate docs/sitemap.xml from scratch to refresh dates.")
        return
    updated = text.replace("</urlset>", "\n".join(new_entries) + "\n</urlset>")
    SITEMAP_PATH.write_text(updated)
    print(f"Appended {len(new_entries)} URLs to {SITEMAP_PATH}.")


def generate():
    slugs = []
    for theme in THEMES:
        products = qe.filter_products(theme["intent"])
        (DOCS_DIR / f"{theme['slug']}.html").write_text(render_theme_page(theme, products))
        slugs.append(theme["slug"])
        print(f"{theme['slug']}.html: {len(products)} products")
    append_to_sitemap(slugs)


if __name__ == "__main__":
    generate()
