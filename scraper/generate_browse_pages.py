"""
Formground Browse (full category) page generator.

WHAT THIS DOES: generates uncapped, paginated, static category pages
(docs/browse/{slug}.html, {slug}-2.html, ...) plus a hub
(docs/browse/index.html) - one page per product TYPE ("Table Lamps",
"Sofas"), listing every real match, not a curated 12.

WHY THIS EXISTS (2026-10-02, agentic/organic findability review): the
catalog was reachable by crawlers only through brand pages. Work is a
JavaScript-fetched query UI with no stable URLs, the furniture/
lighting/ceramics/objects umbrella pages are noindex redirect stubs,
and the themed Edits (capped at MAX_PRODUCTS_PER_EDIT) are deliberately
a curated pick, not the category. So "find me a pendant lamp" had no
static entry point at all except Floor Lamps. These pages are that
entry point - same filter_products() call Work itself uses, so they
cannot drift from what search returns.

SCOPE: tiers A (ad-keyword categories) and C (other lighting) from the
scoping pass: table lamps, pendant lamps, dining tables, coffee tables,
sofas, wall lamps, ceiling lamps, chandeliers. The remaining tiers
(other furniture, soft furnishings, ceramics/objects) reuse this same
list - add an entry to BROWSE_CATEGORIES and re-run.

Lives under /browse/ because pendant-lamps, table-lamps, wall-lamps and
ceiling-lamps are already taken at the site root by the capped Edit
pages (each Edit links here for the full set). Floor Lamps stays at
/floor-lamps.html (generate_theme_landing_pages.py) - it predates this.

ORDERING: deterministic brand round-robin (one product per brand per
pass, brands alphabetical), NOT query_engine.round_robin_order(), which
randomizes - a static page that reshuffles on every rebuild would churn
every diff and move products between pages. Interleaving is the same
"brand is the minimum unit of inclusion" principle search applies; a
size-ordered list would put the biggest catalog (Serax, Seletti) first.

RUN (after generate_brand_pages.py - needs sitemap.xml - and before
generate_themed_edit_pages.py, whose pages link here):
    python3 generate_browse_pages.py
"""

import html
import json
import math
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
BROWSE_DIR = DOCS_DIR / "browse"
BACKEND_DIR = SCRAPER_DIR.parent / "backend"

sys.path.insert(0, str(BACKEND_DIR))
import query_engine as qe  # noqa: E402

from generate_brand_pages import (  # noqa: E402
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_NAV_HTML,
    SITE_URL,
    product_card_html,
)
from generate_theme_landing_pages import (  # noqa: E402
    _group_color_variants,
    append_to_sitemap,
)

# ~300 cards is ~145 KB of HTML - the same weight as the existing
# Floor Lamps page, which is the one uncapped category page already
# live and loading fine. Serax's single brand page is 1.3 MB for
# comparison, so this is deliberately well under what the site already
# serves.
CARDS_PER_PAGE = 300

# Each entry's `intent` goes straight to query_engine.filter_products().
# `plural` is the lowercase noun used in the intro/meta sentence.
BROWSE_CATEGORIES = [
    {"slug": "table-lamps", "title": "Table Lamps", "intent": {"category": "table lamp"}},
    {"slug": "pendant-lamps", "title": "Pendant Lamps", "intent": {"category": "pendant"}},
    {"slug": "wall-lamps", "title": "Wall Lamps", "intent": {"category": "wall lamp"}},
    {"slug": "ceiling-lamps", "title": "Ceiling Lamps", "intent": {"category": "ceiling lamp"}},
    {"slug": "chandeliers", "title": "Chandeliers", "intent": {"category": "chandelier"}},
    {"slug": "dining-tables", "title": "Dining Tables", "intent": {"category": "dining table"}},
    {"slug": "coffee-tables", "title": "Coffee Tables", "intent": {"category": "coffee table"}},
    {"slug": "sofas", "title": "Sofas", "intent": {"category": "sofa"}},
]

PAGER_CSS = """
  .pager { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 40px 0 8px; }
  .pager a, .pager span {
    min-width: 38px; padding: 8px 12px; text-align: center; font-size: 14px;
    border: 0.5px solid var(--border); border-radius: 8px; text-decoration: none;
    color: var(--text-secondary);
  }
  .pager a:hover { color: var(--text-primary); border-color: var(--text-muted); }
  .pager span.current { color: var(--text-primary); border-color: var(--text-secondary); font-weight: 600; }
  .browse-list { list-style: none; padding: 0; margin: 0 auto; max-width: 520px; }
  .browse-list li { border-bottom: 0.5px solid var(--border); }
  .browse-list a {
    display: flex; justify-content: space-between; padding: 14px 4px;
    text-decoration: none; color: inherit; font-size: 16px;
  }
  .browse-list a:hover .browse-name { text-decoration: underline; }
  .browse-list .browse-n { color: var(--text-muted); font-size: 14px; }
"""


def _interleave_by_brand(products):
    """Deterministic one-per-brand-per-pass ordering (brands alphabetical,
    each brand's own products in the order filter_products() returned
    them, which is stable DB order)."""
    by_brand = {}
    for p in products:
        by_brand.setdefault(p["brand"], []).append(p)
    queues = [by_brand[b] for b in sorted(by_brand, key=str.lower)]
    out = []
    i = 0
    while queues:
        remaining = []
        for q in queues:
            out.append(q[i])
            if i + 1 < len(q):
                remaining.append(q)
        queues = remaining
        i += 1
    return out


def _page_slug(slug, page):
    return slug if page == 1 else f"{slug}-{page}"


def _pager_html(slug, page, pages):
    if pages <= 1:
        return ""
    items = []
    if page > 1:
        items.append(f'<a href="/browse/{_page_slug(slug, page - 1)}.html" rel="prev">&larr; Prev</a>')
    for n in range(1, pages + 1):
        if n == page:
            items.append(f'<span class="current" aria-current="page">{n}</span>')
        else:
            items.append(f'<a href="/browse/{_page_slug(slug, n)}.html">{n}</a>')
    if page < pages:
        items.append(f'<a href="/browse/{_page_slug(slug, page + 1)}.html" rel="next">Next &rarr;</a>')
    return f'<nav class="pager" aria-label="Pages">{"".join(items)}</nav>'


def _head(title, description, page_url):
    return f"""<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/favicon-192x192.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(description)}">
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}{PAGER_CSS}</style>"""


def _breadcrumb_json(crumbs):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(crumbs)
        ],
    })


def render_browse_page(category, cards, variant_counts, page, pages, total_products):
    slug, title = category["slug"], category["title"]
    page_url = f"{SITE_URL}/browse/{_page_slug(slug, page)}.html"
    noun = title.lower()
    page_suffix = f" - page {page}" if page > 1 else ""
    full_title = f"{title}{page_suffix} — Formground"
    description = (
        f"{total_products:,} real {noun} from independent makers, listed in full"
        f"{f' (page {page} of {pages})' if pages > 1 else ''}. "
        "Every result links straight to the maker's own site."
    )
    breadcrumb = _breadcrumb_json([
        ("Formground", f"{SITE_URL}/"),
        ("Browse", f"{SITE_URL}/browse/"),
        (title, f"{SITE_URL}/browse/{slug}.html"),
    ])
    grid = "".join(
        product_card_html(p, show_brand=True, variant_count=variant_counts.get(id(p)))
        for p in cards
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head(full_title, description, page_url)}
<script type="application/ld+json">{breadcrumb}</script>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline"><a href="/browse/">Browse</a></p>
  <h1>{html.escape(title)}</h1>
  <p class="category-intro">{total_products:,} {html.escape(noun)} from independent makers{f" - page {page} of {pages}" if pages > 1 else ""}. Every result links straight to the maker's own site.</p>
  <div class="grid">{grid}</div>
  {_pager_html(slug, page, pages)}
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>
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


def render_hub(entries):
    page_url = f"{SITE_URL}/browse/"
    description = "Every product type on Formground, listed in full - from independent makers, each linking straight to the maker's own site."
    items = "".join(
        f'<li><a href="{e["href"]}"><span class="browse-name">{html.escape(e["title"])}</span>'
        f'<span class="browse-n">{e["n"]:,}</span></a></li>'
        for e in entries
    )
    breadcrumb = _breadcrumb_json([("Formground", f"{SITE_URL}/"), ("Browse", page_url)])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head("Browse by type — Formground", description, page_url)}
<script type="application/ld+json">{breadcrumb}</script>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline">Discover design from makers.</p>
  <h1>Browse by type</h1>
  <p class="category-intro">Every piece, listed in full. For a curated selection, see <a href="/edits.html">Edits</a>.</p>
  <ul class="browse-list">{items}</ul>
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>{CARD_CLICK_TRACKING_JS}</script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def generate():
    BROWSE_DIR.mkdir(exist_ok=True)
    # Drop stale pages first: a category that shrinks to fewer pages
    # must not leave an orphaned {slug}-4.html behind.
    for old in BROWSE_DIR.glob("*.html"):
        old.unlink()

    sitemap_slugs = []
    hub_entries = []
    for category in BROWSE_CATEGORIES:
        products = qe.filter_products(category["intent"])
        cards, variant_counts = _group_color_variants(products)
        cards = _interleave_by_brand(cards)
        pages = max(1, math.ceil(len(cards) / CARDS_PER_PAGE))
        for page in range(1, pages + 1):
            chunk = cards[(page - 1) * CARDS_PER_PAGE: page * CARDS_PER_PAGE]
            out = BROWSE_DIR / f"{_page_slug(category['slug'], page)}.html"
            out.write_text(render_browse_page(category, chunk, variant_counts, page, pages, len(products)))
            sitemap_slugs.append(f"browse/{_page_slug(category['slug'], page)}")
        hub_entries.append({"href": f"/browse/{category['slug']}.html", "title": category["title"], "n": len(products)})
        print(f"browse/{category['slug']}: {len(products)} products -> {len(cards)} cards, {pages} page(s)")

    # Floor Lamps predates /browse/ and stays at the site root
    # (generate_theme_landing_pages.py) - listed here so the hub is the
    # one complete index of types.
    hub_entries.append({
        "href": "/floor-lamps.html", "title": "Floor Lamps",
        "n": len(qe.filter_products({"category": "floor lamp"})),
    })
    hub_entries.sort(key=lambda e: e["title"].lower())
    (BROWSE_DIR / "index.html").write_text(render_hub(hub_entries))
    append_to_sitemap([s for s in sitemap_slugs if s != "browse/index"])
    _append_hub_to_sitemap()


def _append_hub_to_sitemap():
    """The hub's canonical is /browse/ (not /browse/index.html), which
    append_to_sitemap()'s {slug}.html formatting can't express."""
    import datetime
    from generate_theme_landing_pages import SITEMAP_PATH
    if not SITEMAP_PATH.exists():
        return
    loc = f"{SITE_URL}/browse/"
    text = SITEMAP_PATH.read_text()
    if f"<loc>{loc}</loc>" in text:
        return
    entry = (f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{datetime.date.today().isoformat()}</lastmod>\n"
             "    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>")
    SITEMAP_PATH.write_text(text.replace("</urlset>", entry + "\n</urlset>"))


if __name__ == "__main__":
    generate()
