"""
Formground Designers page generator.

WHAT THIS DOES:
  Generates one static, crawlable HTML page per independent product
  designer (docs/designers/{slug}.html), plus docs/designers.html (the
  index, same visual pattern as makers.html/architects.html), from the
  real "designer" field already captured by several brands' extractors
  in data/formground.db - no separate JSON source file, since the
  underlying data already lives in the products table.

WHO QUALIFIES: only designers credited on 2+ real products (across any
number of brands) get a page - see independent_product_designers_concept
in project memory for the full reasoning. This intentionally excludes
single-credit names for now: a one-product page reads as thin next to a
real multi-work profile, and the bar can be lowered later once more
brands' extractors reliably capture a "designer" field. This is the
same "don't build ahead of real data" bar already applied to Architects
(only firms with a real per-house model got a page) and Craftspeople.

WHY NORMALIZE FIRST: different brands' own sites credit the same person
differently (Källemo's all-caps house style vs. Gärsnäs's mixed case) -
scrape.py's _normalize_designer_name() runs on every future scrape, but
existing rows needed a one-time cleanup pass (run once, 2026-09-23) so
e.g. Källemo's "PIERRE SINDRE" and Gärsnäs's "Pierre Sindre" merge into
one real cross-brand profile instead of splitting into two.

RUN (after generate_brand_pages.py so sitemap.xml already exists to
append to):
    python3 generate_designers_pages.py
"""

import html
import sqlite3
from collections import defaultdict
from pathlib import Path

from designer_credits import split_credit  # noqa: E402
from site_assets import LISTING_JS, SHARE_JS  # noqa: E402
from generate_brand_pages import (
    fit_title, list_phrase,
    BRAND_CARDS_PER_PAGE,
    brand_page_slug,
    listing_controls_html,
    CARD_CLICK_TRACKING_JS,
    product_card_html,
    CLOUDFLARE_ANALYTICS,
    DIRECTORY_FILTER_JS,
    FAVICON_TAGS,
    HERO_SEARCH_POSITION_CSS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_NAV_HTML,
    SITE_URL,
    directory_filter_html,
    site_nav_html,
    slugify,
    unique_slug,
)
from image_sizes import CARD, HERO, TILE, sized  # noqa: E402
from site_assets import ICONS_CSS  # noqa: E402

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
DOCS_DIR = SCRAPER_DIR.parent / "docs"
DESIGNERS_DIR = DOCS_DIR / "designers"
DB_PATH = DATA_DIR / "formground.db"
SITEMAP_PATH = DOCS_DIR / "sitemap.xml"

MIN_PRODUCTS = 2  # see module docstring - a one-credit page reads as thin


def designer_card_html(designer_name, slug, products):
    # Named a real brand rather than a bare "N brands" count - and the
    # SAME brand the hero photo comes from, so the card's image and its
    # label never point at two different brands.
    hero_product = next((p for p in products if p.get("image_url")), None)
    hero = hero_product["image_url"] if hero_product else ""
    image = f'<img src="{html.escape(sized(hero, CARD))}" alt="{html.escape(designer_name)}" loading="lazy">' if hero else ""
    brands = sorted({p["brand"] for p in products})
    primary_brand = hero_product["brand"] if hero_product else brands[0]
    other_count = len(brands) - 1
    brand_line = primary_brand if other_count == 0 else f"{primary_brand} +{other_count}"
    count = f"{len(products)} product{'' if len(products) == 1 else 's'}"
    return f"""
      <a class="maker-card" href="/designers/{slug}.html">
        <div class="maker-card-hero">{image}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(designer_name)}</span>
          <span class="maker-country">{html.escape(brand_line)}</span>
          <span class="maker-categories">{count}</span>
        </div>
      </a>"""


BRAND_FILTER_JS = """
(function () {
  var bar = document.getElementById("brand-filters");
  if (!bar) return;
  var chips = bar.querySelectorAll(".filter-chip");
  var cards = document.querySelectorAll("[data-listing-grid] .card");
  var count = document.getElementById("shown-count"), noun = document.getElementById("shown-noun");
  var known = {};
  chips.forEach(function (c) { known[c.getAttribute("data-slug")] = true; });
  function apply(slug) {
    var shown = 0;
    chips.forEach(function (c) { c.classList.toggle("active", c.getAttribute("data-slug") === slug); });
    cards.forEach(function (card) {
      var hide = slug !== "" && card.getAttribute("data-slug") !== slug;
      card.hidden = hide;
      if (!hide) shown++;
    });
    if (count) count.textContent = shown;
    if (noun) noun.textContent = shown === 1 ? "product" : "products";
    try {
      var u = new URL(location.href);
      if (slug) u.searchParams.set("brand", slug); else u.searchParams.delete("brand");
      history.replaceState(null, "", u);
    } catch (e) {}
  }
  chips.forEach(function (c) { c.addEventListener("click", function () { apply(c.getAttribute("data-slug")); }); });
  var wanted = "";
  try { wanted = new URLSearchParams(location.search).get("brand") || ""; } catch (e) {}
  apply(known[wanted] ? wanted : "");
})();
"""


BRAND_CHIP_CSS = """
  .tier-filters { margin-top: 4px; }
  .filter-chip .chip-count { color: var(--text-muted); margin-left: 4px; font-variant-numeric: tabular-nums; }
  .filter-chip.active .chip-count { color: inherit; opacity: 0.7; }
"""


def brand_filter_html(products):
    """Brand chips for a designer credited across 2+ makers: All, then each brand with its piece count (most first).
    The ?brand=<slug> in a link from a maker's page selects that chip on load (BRAND_FILTER_JS)."""
    counts = {}
    for p in products:
        counts.setdefault(p["brand"], 0)
        counts[p["brand"]] += 1
    chips = [f'<button type="button" class="filter-chip active" data-slug="">All <span class="chip-count">{len(products)}</span></button>']
    for brand, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        chips.append(f'<button type="button" class="filter-chip" data-slug="{slugify(brand)}">{html.escape(brand)} '
                     f'<span class="chip-count">{n}</span></button>')
    return '\n  <div class="tier-filters" id="brand-filters">' + "".join(chips) + "</div>"


def render_designer_page(designer_name, slug, products, page=1):
    page_url = f"{SITE_URL}/designers/{brand_page_slug(slug, page)}.html"
    brands = sorted({p["brand"] for p in products})
    brand_line = brands[0] if len(brands) == 1 else f"{len(brands)} brands: {', '.join(brands)}"
    multi = len(brands) >= 2          # credited across 2+ makers: one page with brand chips, not numbered pages
    pages = 1 if multi else max(1, -(-len(products) // BRAND_CARDS_PER_PAGE))
    page_note = f" (page {page} of {pages})" if pages > 1 else ""
    pg = f", page {page}" if page > 1 else ""
    seo_title = fit_title(f"{designer_name}: designs and products{pg}", f"{designer_name}{pg}")
    if len(brands) == 1:
        across = brands[0]
    elif len(brands) == 2:
        across = f"{brands[0]} and {brands[1]}"
    else:
        across = f"{len(brands)} makers, including {brands[0]} and {brands[1]}"
    description = (
        f"{html.escape(designer_name)}'s work on Formground: {len(products)} product{'' if len(products) == 1 else 's'}"
        f"{page_note}, credited across {across}."
    )
    if len(description) + 45 <= 160:
        description += " Each links straight to the maker's own site."
    products_sorted = sorted(products, key=lambda p: (p["brand"], p["product_name"]))
    url_for = lambda n: f"/designers/{brand_page_slug(slug, n)}.html"
    earlier_html, see_more_html, pager_html = listing_controls_html(url_for, page, pages, len(products), "pieces")
    if not multi:
        products_sorted = products_sorted[(page - 1) * BRAND_CARDS_PER_PAGE: page * BRAND_CARDS_PER_PAGE]
    # the standard product card (square photo, name, maker, share button) - the same as the Work page and every other page
    products_html = "".join(
        product_card_html(p, show_brand=True, share=True).replace(
            'data-brand="', f'data-slug="{slugify(p["brand"])}" data-brand="', 1)
        for p in products_sorted)
    brand_chips = brand_filter_html(products) if multi else ""

    breadcrumb_json = f"""{{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{"@type": "ListItem", "position": 1, "name": "Formground", "item": "{SITE_URL}/"}},
        {{"@type": "ListItem", "position": 2, "name": "Designers", "item": "{SITE_URL}/designers.html"}},
        {{"@type": "ListItem", "position": 3, "name": "{html.escape(designer_name)}", "item": "{SITE_URL}/designers/{slug}.html"}}
      ]
    }}"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(seo_title)}</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(seo_title)}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{breadcrumb_json}</script>
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}</style>
{('<style>' + BRAND_CHIP_CSS + '</style>') if brand_chips else ''}
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("creators")}
</header>
<main>
  <div class="maker-header">
    <p class="eyebrow">Designer</p>
    <h1 class="maker-name">{html.escape(designer_name)}</h1>
  </div>
  <p class="category-intro" style="text-align:center;margin-left:auto;margin-right:auto;"><span id="shown-count">{len(products)}</span> <span id="shown-noun">product{'' if len(products) == 1 else 's'}</span> credited to {html.escape(designer_name)}, each linked straight to its maker's own page.</p>{brand_chips}
  {earlier_html}
  <div class="grid" data-listing-grid>{products_html}
  </div>
  {see_more_html}
  {pager_html}
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
<script src="{SHARE_JS}" defer></script>
<script src="{LISTING_JS}" defer></script>
{('<script>' + BRAND_FILTER_JS + '</script>') if brand_chips else ''}
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def render_designers_index(designers_with_slugs, products_by_designer):
    items = "".join(
        designer_card_html(name, slug, products_by_designer[name])
        for name, slug in sorted(designers_with_slugs, key=lambda p: p[0].lower())
    )
    total_products = sum(len(v) for v in products_by_designer.values())
    page_url = f"{SITE_URL}/designers.html"
    description = (
        f"{len(designers_with_slugs)} independent product designers on Formground, {total_products} credited "
        "products total - browse the work, credited to the person who designed it."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Designers and their products — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="Designers and their products — Formground">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}</style>
<style>{HERO_SEARCH_POSITION_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("creators")}
</header>
<main style="max-width:1160px;">{directory_filter_html("Filter by designer or brand…", "Designers")}
  <h1 class="sr-only">Designers</h1>
  <div class="maker-grid">{items}
  </div>
  <p class="footer-description">Formground promotes a curated selection of designers, new and established, to be discovered. If you'd like to be featured, <a href="/contact.html">get in touch here</a>.</p>
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>
  document.querySelectorAll(".maker-card-hero img").forEach(function (img) {{
    img.addEventListener("load", function () {{
      var ratio = img.naturalWidth / img.naturalHeight;
      if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
    }});
  }});
{DIRECTORY_FILTER_JS}</script>
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
    if f"{SITE_URL}/designers.html" in text:
        print("Sitemap already has designers entries - regenerate docs/sitemap.xml from scratch to refresh dates.")
        return
    new_entries = [
        f"  <url>\n    <loc>{SITE_URL}/designers.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>"
    ]
    for slug in slugs:
        new_entries.append(
            f"  <url>\n    <loc>{SITE_URL}/designers/{slug}.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.5</priority>\n  </url>"
        )
    updated = text.replace("</urlset>", "\n".join(new_entries) + "\n</urlset>")
    SITEMAP_PATH.write_text(updated)
    print(f"Appended {len(new_entries)} URLs to {SITEMAP_PATH}.")


def generate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT designer, brand, brand_url, product_name, product_url, image_url, link_dead
        FROM products
        WHERE designer IS NOT NULL AND TRIM(designer) != '' AND image_url != ''
    """).fetchall()
    conn.close()

    products_by_designer = defaultdict(list)
    for row in rows:
        # a credit can name several designers (or none: "Aa.Vv."): the piece shows on each named designer's page
        for name in split_credit(row["designer"]):
            products_by_designer[name].append(dict(row))

    DESIGNERS_DIR.mkdir(parents=True, exist_ok=True)

    slugs_seen = {}
    designers_with_slugs = []
    extra_page_slugs = []
    for designer_name, products in sorted(products_by_designer.items(), key=lambda kv: kv[0]):
        if len(products) < MIN_PRODUCTS:
            continue
        slug = unique_slug(slugify(designer_name), designer_name, slugs_seen)
        slugs_seen[slug] = designer_name

        (DESIGNERS_DIR / f"{slug}.html").write_text(render_designer_page(designer_name, slug, products))
        designers_with_slugs.append((designer_name, slug))
        multi_brand = len({p["brand"] for p in products}) >= 2
        for extra in range(2, 1 if multi_brand else -(-len(products) // BRAND_CARDS_PER_PAGE) + 1):      # numbered pages, 60 products each (a multi-brand designer has one page)
            page_slug = brand_page_slug(slug, extra)
            assert page_slug not in slugs_seen, f"numbered page {page_slug} collides with a designer's own page"
            (DESIGNERS_DIR / f"{page_slug}.html").write_text(render_designer_page(designer_name, slug, products, page=extra))
            extra_page_slugs.append(page_slug)

    # A designer who drops below MIN_PRODUCTS since the last run (a
    # brand's catalog shrank, a re-scrape lost a credit) shouldn't leave
    # a stale page reachable - same self-healing pattern
    # generate_architects_pages.py uses for firms that lose their last
    # real house.
    for existing in DESIGNERS_DIR.glob("*.html"):
        if existing.stem not in slugs_seen and existing.stem not in extra_page_slugs:
            existing.unlink()

    index_html = render_designers_index(designers_with_slugs, products_by_designer)
    # Written to frontend/ as well (like the Marketplace and For Creators pages): frontend/designers.html used to be
    # the old "coming soon" placeholder, and copying it over docs/ replaced this real index with it (2026-10-04).
    for folder in (DOCS_DIR, SCRAPER_DIR.parent / "frontend"):
        (folder / "designers.html").write_text(index_html)
    append_to_sitemap(sorted(s for _, s in designers_with_slugs))

    total_products = sum(len(products_by_designer[n]) for n, _ in designers_with_slugs)
    print(f"Generated {len(designers_with_slugs)} designer pages ({total_products} credited products) + designers.html.")


if __name__ == "__main__":
    generate()
