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
import re
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


# Real vocabulary confirmed present across all 4 themes' product names
# (2026-09-29) - covers colors, wood species, and common finish/material
# words. Deliberately does NOT include size words ("Small"/"Large"/
# "Medium") or anything numeric (Ø-diameters, cm measurements, x-by-x
# dimensions) - those stay in the grouping key on purpose (see
# _group_color_variants's docstring for why).
COLOR_FINISH_WORDS = {
    "black", "white", "grey", "gray", "red", "blue", "green", "yellow",
    "brown", "beige", "cream", "natural", "natur", "dark", "light",
    "oak", "walnut", "ash", "teak", "pine", "birch", "timber", "moss",
    "marble", "limestone", "granite", "travertine", "concrete", "terrazzo",
    "lacquered", "lacquer", "stain", "stained", "matt", "glossy", "waxed",
    "smoked", "veneer", "laminate",
    "steel", "stainless", "brass", "chrome", "bronze", "gold", "silver",
    "nickel", "copper",
    "waste", "sirka",
}


def _group_color_variants(products):
    """
    Collapses same-size color/finish variants of one product into a
    single representative card (first one listed, in whatever order
    filter_products() returned) with a "N finishes" badge - built after
    a real case was found live on scandinavian-dining-tables.html:
    Davsjo alone contributed ~18 near-duplicate cards (5 wood finishes x
    several sizes) that drowned out the other 15 brands on the page.

    Deliberately does NOT collapse different SIZES into one card (user's
    explicit call, 2026-09-29) - "Coin Dining Table - O120" and "- O150"
    stay as two real, separately-clickable cards, since a size is often
    a genuine functional choice someone is searching for, unlike a
    color/finish. The grouping key keeps every digit, "O"-diameter, "cm"
    measurement, and size word (Small/Large/Medium) from the original
    name untouched - only known color/material words (COLOR_FINISH_WORDS)
    are stripped before comparing, so two names that differ ONLY by a
    color word collapse together, and anything else (including a size
    difference) keeps them apart.

    Returns (products_to_render, variant_counts) where variant_counts
    maps a rendered product's id() to its group's real size (omitted /
    1 for a product with no real variants).
    """
    def grouping_key(p):
        words = re.findall(r"[A-Za-zÀ-ÿ]+|[0-9]+|Ø|/", p["product_name"])
        kept = [w for w in words if w.lower() not in COLOR_FINISH_WORDS]
        return (p["brand"], " ".join(kept).lower())

    groups = {}
    order = []
    for p in products:
        key = grouping_key(p)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(p)

    result = []
    variant_counts = {}
    for key in order:
        group = groups[key]
        representative = dict(group[0])
        if len(group) > 1:
            representative["product_name"] = _strip_color_words_for_display(representative["product_name"])
            variant_counts[id(representative)] = len(group)
        result.append(representative)
    return result, variant_counts


def _strip_color_words_for_display(name):
    """
    Removes the same COLOR_FINISH_WORDS from a representative card's own
    title (not just the grouping key) so a grouped card reads "Sintra
    Dining Table" instead of "Sintra Dining Table | Black Marble" -
    misleading once the card actually stands in for 5 different colors.
    Collapses whatever delimiter mess stripping words out of the middle
    of a "|"-separated name leaves behind.
    """
    def strip_word(m):
        return "" if m.group(0).lower() in COLOR_FINISH_WORDS else m.group(0)

    cleaned = re.sub(r"[A-Za-zÀ-ÿ]+", strip_word, name)
    cleaned = re.sub(r"\s*\|\s*\|\s*", " | ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"^\s*[|,-]\s*|\s*[|,-]\s*$", "", cleaned)
    cleaned = re.sub(r"\s*\|\s*", " | ", cleaned)
    return cleaned.strip()


def render_theme_page(theme, products):
    slug = theme["slug"]
    title = theme["title"]
    page_url = f"{SITE_URL}/{slug}.html"
    # The meta description counts every real, distinct product - grouping
    # same-size color variants below is a display choice, not a content
    # reduction, so the honest "how much is here" number stays ungrouped.
    n = len(products)
    description = f"{n} real {title.lower()}{'' if title.lower().endswith('s') else 's'}, from independent makers. {theme['intro']}"

    cards_to_render, variant_counts = _group_color_variants(products)

    if cards_to_render:
        cards = "".join(
            product_card_html(p, show_brand=True, variant_count=variant_counts.get(id(p)))
            for p in cards_to_render
        )
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
