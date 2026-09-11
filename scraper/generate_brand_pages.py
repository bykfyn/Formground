"""
Formground brand page generator.

WHAT THIS DOES:
  Generates one static, crawlable HTML page per brand (docs/brands/
  {slug}.html) listing every one of that brand's products currently on
  Formground, plus a "docs/makers.html" index linking to all of them,
  plus a regenerated docs/sitemap.xml covering every page. Unlike the
  search page itself (client-rendered, nothing for Google to index),
  these are plain static files - real text and links a search engine
  can read directly.

WHY THIS EXISTS:
  Two goals: (1) SEO - real, indexable content per brand, internally
  linked from makers.html (not from search result cards - every
  result card's only action stays "go to the source", per the
  fair-use/legal grounding this whole project relies on); (2) lets
  someone who likes one piece from a maker see everything else they
  have on Formground, from a page reached via makers.html or a search
  engine, not from the search results themselves.

WHO RUNS THIS:
  The GitHub Action (.github/workflows/scrape.yml), right after
  scrape.py, so brand pages regenerate every time the underlying data
  does. Run it yourself with:

    python scraper/generate_brand_pages.py
"""

import datetime
import html
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
DB_PATH = DATA_DIR / "formground.db"
BRANDS_PATH = SCRAPER_DIR / "brands.json"
DOCS_DIR = SCRAPER_DIR.parent / "docs"
BRANDS_DIR = DOCS_DIR / "brands"
SITE_URL = "https://formground.com"

# Same snippet added by hand to index.html/about.html/contact.html -
# kept here as one constant so both places it's used in this file
# can't drift from each other or from those hand-maintained pages.
CLOUDFLARE_ANALYTICS = (
    "<!-- Cloudflare Web Analytics -->"
    "<script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' "
    "data-cf-beacon='{\"token\": \"87e51fd2f5894326b3c6e883edc75a6d\"}'></script>"
    "<!-- End Cloudflare Web Analytics -->"
)

# Same tags added by hand to index.html/about.html/contact.html - kept
# here as one constant for the same reason as CLOUDFLARE_ANALYTICS above.
FAVICON_TAGS = (
    '<link rel="icon" href="/favicon.ico" sizes="any">\n'
    '<link rel="icon" href="/favicon-32x32.png" type="image/png" sizes="32x32">\n'
    '<link rel="icon" href="/favicon-16x16.png" type="image/png" sizes="16x16">\n'
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
)


def load_countries():
    """
    Country is only ever present in brands.json when genuinely
    confirmed (an explicit note, or a country-code domain like .it/
    .se) - never guessed. Brands without it just don't get a country
    tag, rather than showing something unverified.
    """
    brands = json.loads(BRANDS_PATH.read_text())
    return {b["name"]: b["country"] for b in brands if b.get("country")}


def load_hidden_brands():
    """
    A brand marked "hidden": true keeps its data and keeps being
    scraped, but gets no brand page, no makers.html entry, and no
    sitemap entry - for pausing a brand from showing up (e.g. a design
    direction that no longer fits well next to the others) without
    losing its data or its scrape schedule. See query_engine.py's
    HIDDEN_BRANDS for the matching backend-side exclusion (search/
    discover). Any previously-generated page for a brand that's since
    been hidden is deleted here too, rather than left as a stale,
    still-reachable file.
    """
    brands = json.loads(BRANDS_PATH.read_text())
    return {b["name"] for b in brands if b.get("hidden")}

# A brand can have products across more than one of these - the page
# shows every umbrella that any of its products match. Kept as a
# plain, extendable dict (not a fixed enum) since the user has flagged
# these four will likely grow over time (e.g. textiles, glassware as
# their own umbrella) - adding a new one later is a one-line change
# here, not a rework. Word lists reused from query_engine.py's proven
# HYPERNYM_WORDS/category-inference logic for consistency, not
# reinvented.
UMBRELLA_KEYWORDS = {
    "Furniture": (
        "chair", "table", "stool", "bench", "sofa", "armchair", "ottoman",
        "console", "bookcase", "desk", "storage", "shelving", "shelf",
        "cabinet", "sideboard", "daybed", "modular unit", "seat", "seating",
        "screen", "rocker",
    ),
    "Lighting": (
        "lamp", "light", "sconce", "pendant", "chandelier", "surface mount",
        "flush mount", "wall mount", "suspension",
    ),
    "Ceramics": (
        "ceramic", "vase", "bowl", "plate", "cup", "mug", "pottery",
        "vessel", "carafe", "pitcher",
    ),
}
# Anything matching none of the above falls into this catch-all, by
# design - Formground's stated scope is furniture/lighting/ceramics/
# objects, so "doesn't match the first three" already means "objects".
DEFAULT_UMBRELLA = "Objects"


def slugify(name):
    """
    A URL slug needs to be stable once a brand page is indexed -
    changing it later loses accumulated SEO value - so this needs to
    handle every real case in brands.json up front: accented
    characters ("Löwenhielm"), periods ("A. Petersen"), ampersands,
    multiple spaces.
    """
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "brand"


def umbrella_categories_for(products):
    """Union of umbrella categories across every product a brand has,
    checked against both category and product_name (some brands, like
    Bitossi, only have a real object-type signal in the name)."""
    found = set()
    for p in products:
        text = f"{p['category']} {p['product_name']}".lower()
        matched_any = False
        for umbrella, keywords in UMBRELLA_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(k)}s?\b", text) for k in keywords):
                found.add(umbrella)
                matched_any = True
        if not matched_any:
            found.add(DEFAULT_UMBRELLA)
    return sorted(found, key=lambda u: (u != "Furniture", u != "Lighting", u))


def product_card_html(p):
    url = p["brand_url"] if p["link_dead"] else p["product_url"]
    image = (
        f'<img src="{html.escape(p["image_url"])}" alt="" loading="lazy">'
        if p["image_url"] else ""
    )
    return f"""
      <a class="card" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">
        <div class="card-image">{image}</div>
        <div class="card-body">
          <p class="card-title">{html.escape(p["product_name"])}</p>
        </div>
      </a>"""


# Only page-specific rules here - shared rules (:root, body, home-link,
# h1, .tag, .foot-note) live in /site.css, linked with an absolute path
# below since these pages are nested under /brands/.
PAGE_CSS = """
  main { max-width: 1100px; margin: 0 auto; padding: 48px 20px 60px; }
  .maker-header { text-align: center; margin-bottom: 32px; }
  .eyebrow { font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--text-muted); margin: 0 0 6px; }
  .maker-name { font-size: 18px; font-weight: 500; color: var(--text-secondary); margin: 0 0 12px; }
  .brand-site-link { font-size: 13px; color: var(--text-accent); text-decoration: none; }
  .brand-site-link:hover { text-decoration: underline; }
  .tags { margin-bottom: 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
  .card { background: var(--surface-2); border: 0.5px solid var(--border);
    border-radius: 12px; overflow: hidden; text-decoration: none; color: inherit; display: block; }
  .card-image { aspect-ratio: 1/1; background: var(--surface-1); overflow: hidden; }
  .card-image img { width: 100%; height: 100%; object-fit: cover; }
  .card-body { padding: 10px 12px; }
  .card-title { font-size: 13px; font-weight: 500; margin: 0; }
  .maker-list { list-style: none; padding: 0; margin: 0; }
  .maker-list li { padding: 16px 0; border-bottom: 0.5px solid var(--border); text-align: center; }
  .maker-list a.maker-name { display: block; font-size: 18px; font-weight: 500;
    color: var(--text-secondary); text-decoration: none; margin-bottom: 8px; }
  .maker-list a.maker-name:hover { text-decoration: underline; }
  .maker-tags { line-height: 1.8; }
  /* Tagline sits directly under the (left-aligned) logo rather than
     centered with the page's own heading - a quick "what is this site"
     for a cold visitor without competing with the page's actual
     subject (the maker's own name, on brand pages). Overrides
     site.css's a.home-link margin (40px) since the tagline needs to
     sit close to the logo, not the next section. */
  a.home-link { margin-bottom: 6px; }
  .page-tagline { font-size: 13px; color: var(--text-secondary); margin: 0 0 32px; }
"""


def render_brand_page(brand, slug, brand_url, products, umbrellas, country=None):
    tag_list = list(umbrellas) + ([country] if country else [])
    tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tag_list)
    cards = "".join(product_card_html(p) for p in products)
    page_url = f"{SITE_URL}/brands/{slug}.html"
    # BreadcrumbList (Home -> Makers -> this brand) - cheap, accurate
    # structured data with a real shot at a rich-result breadcrumb in
    # search results. Deliberately no Product/price schema here: we
    # don't have reliable real-time price/availability data, and
    # claiming it would overstate what's really just a thumbnail-and-
    # link-back model (see the project's own fair-use grounding).
    breadcrumb_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Formground", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Makers", "item": f"{SITE_URL}/makers.html"},
            {"@type": "ListItem", "position": 3, "name": brand, "item": page_url},
        ],
    })
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(brand)} on Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(brand)}'s work on Formground - {len(products)} pieces, linked straight to their own site.">
<link rel="canonical" href="{page_url}">
<script type="application/ld+json">{breadcrumb_json}</script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css">
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
</head>
<body>
<main>
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
  <p class="page-tagline">Discover design from independent makers.</p>
  <div class="maker-header">
    <p class="eyebrow">Maker</p>
    <h1 class="maker-name">{html.escape(brand)}</h1>
    <div class="tags">{tags}</div>
    <a class="brand-site-link" href="{html.escape(brand_url)}" target="_blank" rel="noopener noreferrer">Visit site &rarr;</a>
  </div>
  <div class="grid">{cards}</div>
  <p class="foot-note">
    <a href="/">&larr; Back to Formground</a> &middot; <a href="/makers.html">Makers</a>
  </p>
</main>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def render_makers_index(brands_data):
    # Deliberately no product count here - "brand is the minimum unit
    # of inclusion", equal weight regardless of catalog size, is a
    # core principle elsewhere on the site (dashed-border cards, no
    # ranking by data richness) - showing "(1 piece)" next to
    # "(261 pieces)" on the one page listing every maker side by side
    # would visually undercut that.
    items = ""
    for brand, slug, umbrellas, _count, country in sorted(brands_data, key=lambda b: b[0].lower()):
        tag_list = list(umbrellas) + ([country] if country else [])
        tags = " ".join(f'<span class="tag">{html.escape(t)}</span>' for t in tag_list)
        items += f"""
      <li>
        <a class="maker-name" href="/brands/{slug}.html">{html.escape(brand)}</a>
        <div class="maker-tags">{tags}</div>
      </li>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Makers — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="Every independent maker currently on Formground, browsable by name.">
<link rel="canonical" href="https://formground.com/makers.html">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css">
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
</head>
<body>
<main style="max-width:640px;">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
  <p class="page-tagline">Discover design from independent makers.</p>
  <ul class="maker-list">{items}
  </ul>
  <p class="foot-note">
    <a href="/">&larr; Back to Formground</a> &middot; <a href="/about.html">About Formground</a> &middot; <a href="/contact.html">Get in touch</a>
  </p>
</main>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def render_sitemap(brand_slugs):
    # lastmod is only set on the pages this script itself regenerates
    # every run (makers.html, brand pages) - their content can genuinely
    # change on any given run, so "today" is a real signal, not a gamed
    # one. The hand-maintained pages (homepage, about, contact) aren't
    # touched by this script, so they're left without lastmod rather
    # than given a date that doesn't reflect when they actually changed
    # - a wrong lastmod is worse than none, since search engines
    # discount sitemaps whose freshness signal turns out to be fake.
    today = datetime.date.today().isoformat()
    urls = [
        ("https://formground.com/", "weekly", "1.0", None),
        ("https://formground.com/about.html", "monthly", "0.6", None),
        ("https://formground.com/contact.html", "monthly", "0.5", None),
        ("https://formground.com/resources.html", "monthly", "0.4", None),
        ("https://formground.com/makers.html", "weekly", "0.7", today),
    ]
    urls += [(f"https://formground.com/brands/{slug}.html", "weekly", "0.5", today) for slug in brand_slugs]
    entries = []
    for loc, freq, pri, lastmod in urls:
        lastmod_tag = f"\n    <lastmod>{lastmod}</lastmod>" if lastmod else ""
        entries.append(
            f"  <url>\n    <loc>{loc}</loc>{lastmod_tag}\n    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>"
        )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{chr(10).join(entries)}\n</urlset>\n'


def generate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM products WHERE image_url != '' ORDER BY product_name"
    ).fetchall()
    conn.close()

    by_brand = {}
    for row in rows:
        by_brand.setdefault(row["brand"], []).append(dict(row))

    countries = load_countries()
    hidden_brands = load_hidden_brands()
    BRANDS_DIR.mkdir(parents=True, exist_ok=True)

    slugs_seen = {}
    makers_data = []
    for brand, products in by_brand.items():
        slug = slugify(brand)
        # Extremely unlikely at current scale, but two brands could
        # theoretically slugify to the same string - keep pages from
        # silently overwriting each other rather than assume it can't happen.
        if slug in slugs_seen and slugs_seen[slug] != brand:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = brand

        if brand in hidden_brands:
            # No page, no makers.html entry, no sitemap entry - and
            # delete any page generated before this brand was hidden,
            # rather than leave a stale file still reachable by anyone
            # with the old URL.
            (BRANDS_DIR / f"{slug}.html").unlink(missing_ok=True)
            continue

        brand_url = products[0]["brand_url"]
        umbrellas = umbrella_categories_for(products)
        country = countries.get(brand)
        page = render_brand_page(brand, slug, brand_url, products, umbrellas, country)
        (BRANDS_DIR / f"{slug}.html").write_text(page)
        makers_data.append((brand, slug, umbrellas, len(products), country))

    (DOCS_DIR / "makers.html").write_text(render_makers_index(makers_data))
    (DOCS_DIR / "sitemap.xml").write_text(render_sitemap(sorted(m[1] for m in makers_data)))

    print(f"Generated {len(makers_data)} brand pages, makers.html, and sitemap.xml "
          f"({sum(m[3] for m in makers_data)} products total).")


if __name__ == "__main__":
    generate()
