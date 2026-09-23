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

from generate_brand_pages import (
    CLOUDFLARE_ANALYTICS,
    DIRECTORY_FILTER_JS,
    FAVICON_TAGS,
    HERO_SEARCH_POSITION_CSS,
    PAGE_CSS,
    SITE_NAV_HTML,
    SITE_URL,
    directory_filter_html,
    site_nav_html,
    slugify,
)

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
DOCS_DIR = SCRAPER_DIR.parent / "docs"
DESIGNERS_DIR = DOCS_DIR / "designers"
DB_PATH = DATA_DIR / "formground.db"
SITEMAP_PATH = DOCS_DIR / "sitemap.xml"

MIN_PRODUCTS = 2  # see module docstring - a one-credit page reads as thin


def product_card_html(product):
    image = (
        f'<img src="{html.escape(product["image_url"])}" alt="{html.escape(product["product_name"])}" loading="lazy">'
        if product.get("image_url") else ""
    )
    return f"""
      <a class="maker-card" href="{html.escape(product["product_url"])}" target="_blank" rel="noopener noreferrer">
        <div class="maker-card-hero">{image}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(product["product_name"])}</span>
          <span class="maker-country">{html.escape(product["brand"])}</span>
        </div>
      </a>"""


def designer_card_html(designer_name, slug, products):
    hero = next((p["image_url"] for p in products if p.get("image_url")), "")
    image = f'<img src="{html.escape(hero)}" alt="{html.escape(designer_name)}" loading="lazy">' if hero else ""
    brands = sorted({p["brand"] for p in products})
    brand_line = brands[0] if len(brands) == 1 else f"{len(brands)} brands"
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


def render_designer_page(designer_name, slug, products):
    page_url = f"{SITE_URL}/designers/{slug}.html"
    brands = sorted({p["brand"] for p in products})
    brand_line = brands[0] if len(brands) == 1 else f"{len(brands)} brands: {', '.join(brands)}"
    description = (
        f"{html.escape(designer_name)} - {len(products)} real product{'' if len(products) == 1 else 's'} "
        f"credited across {brand_line if len(brands) > 1 else brands[0]}."
    )
    products_sorted = sorted(products, key=lambda p: (p["brand"], p["product_name"]))
    products_html = "".join(product_card_html(p) for p in products_sorted)

    breadcrumb_json = f"""{{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{"@type": "ListItem", "position": 1, "name": "Formground", "item": "{SITE_URL}/"}},
        {{"@type": "ListItem", "position": 2, "name": "Designers", "item": "{SITE_URL}/designers.html"}},
        {{"@type": "ListItem", "position": 3, "name": "{html.escape(designer_name)}", "item": "{page_url}"}}
      ]
    }}"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(designer_name)} — Designers — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(designer_name)} — Formground">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{breadcrumb_json}</script>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
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
  <p class="category-intro" style="text-align:center;margin-left:auto;margin-right:auto;">{len(products)} real product{'' if len(products) == 1 else 's'} credited to {html.escape(designer_name)}, each linked straight to its maker's own page.</p>
  <div class="maker-grid">{products_html}
  </div>
  <p class="page-tagline">Looking for who made it? <a href="/makers.html">Browse Makers &rarr;</a></p>
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/privacy.html">Privacy</a> &middot; <a href="/about.html">About</a>
  </p>
</main>
<script>
  document.querySelectorAll(".maker-card-hero img").forEach(function (img) {{
    img.addEventListener("load", function () {{
      var ratio = img.naturalWidth / img.naturalHeight;
      if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
    }});
  }});
</script>
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
        f"{len(designers_with_slugs)} independent product designers on Formground, {total_products} real credited "
        "products total - browse the work, credited to the person who designed it."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Designers — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="Designers — Formground">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="/site.css">
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
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/privacy.html">Privacy</a> &middot; <a href="/about.html">About</a>
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
        SELECT designer, brand, product_name, product_url, image_url
        FROM products
        WHERE designer IS NOT NULL AND TRIM(designer) != '' AND image_url != ''
    """).fetchall()
    conn.close()

    products_by_designer = defaultdict(list)
    for row in rows:
        products_by_designer[row["designer"]].append(dict(row))

    DESIGNERS_DIR.mkdir(parents=True, exist_ok=True)

    slugs_seen = {}
    designers_with_slugs = []
    for designer_name, products in products_by_designer.items():
        if len(products) < MIN_PRODUCTS:
            continue
        slug = slugify(designer_name)
        if slug in slugs_seen and slugs_seen[slug] != designer_name:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = designer_name

        (DESIGNERS_DIR / f"{slug}.html").write_text(render_designer_page(designer_name, slug, products))
        designers_with_slugs.append((designer_name, slug))

    # A designer who drops below MIN_PRODUCTS since the last run (a
    # brand's catalog shrank, a re-scrape lost a credit) shouldn't leave
    # a stale page reachable - same self-healing pattern
    # generate_architects_pages.py uses for firms that lose their last
    # real house.
    for existing in DESIGNERS_DIR.glob("*.html"):
        if existing.stem not in slugs_seen:
            existing.unlink()

    (DOCS_DIR / "designers.html").write_text(
        render_designers_index(designers_with_slugs, products_by_designer)
    )
    append_to_sitemap(sorted(s for _, s in designers_with_slugs))

    total_products = sum(len(products_by_designer[n]) for n, _ in designers_with_slugs)
    print(f"Generated {len(designers_with_slugs)} designer pages ({total_products} real credited products) + designers.html.")


if __name__ == "__main__":
    generate()
