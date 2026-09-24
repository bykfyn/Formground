"""
Formground Architects page generator.

WHAT THIS DOES:
  Generates one static, crawlable HTML page per architecture firm
  (docs/architects/{slug}.html), plus docs/architects.html (the index,
  same visual pattern as makers.html/craftspeople.html), from
  data/houses.json (see scrape_architect_projects.py) grouped by firm,
  cross-referenced against data/architects.json for firm metadata
  (site URL, city, contact). Appends these pages to docs/sitemap.xml.

WHY HOUSES, NOT A GENERIC PHOTO GRID: this replaced an earlier model
(a firm page showing ~6 representative photos, no named projects) once
real per-project house data became feasible to extract - see
architects_craftspeople_search_gap.md in project memory for the full
"house is a product, like a chair" reasoning. Only firms with real,
individually-named house projects (data/houses.json) get a page now;
a firm curated in architects.json but never scraped at the per-house
level, or scraped with zero houses passing the contemporary/modern
bar, doesn't get a page here - narrower than the old model, but every
page shown is now backed by real named work, not just representative
photos.

RUN (after generate_brand_pages.py so sitemap.xml already exists to
append to):
    python3 generate_architects_pages.py
"""

import html
import json
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
ARCHITECTS_DIR = DOCS_DIR / "architects"
ARCHITECTS_PATH = DATA_DIR / "architects.json"
HOUSES_PATH = DATA_DIR / "houses.json"
SITEMAP_PATH = DOCS_DIR / "sitemap.xml"


def house_card_html(house):
    image = f'<img src="{html.escape(house["image"])}" alt="{html.escape(house["name"] or "House")}" loading="lazy">' if house.get("image") else ""
    # A literal "·" here, not the &middot; entity - this string gets
    # html.escape()'d below (location text could contain special
    # chars), which would otherwise double-escape the entity's "&" into
    # "&amp;middot;" and print the literal text on the page.
    meta = " · ".join(x for x in [house.get("location"), str(house["year"]) if house.get("year") else None] if x)
    link = house.get("url") or "#"
    return f"""
      <a class="maker-card" href="{html.escape(link)}" target="_blank" rel="noopener noreferrer">
        <div class="maker-card-hero">{image}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(house["name"] or "Untitled house")}</span>
          <span class="maker-country">{html.escape(meta) if meta else "&nbsp;"}</span>
        </div>
      </a>"""


def architect_card_html(firm_name, slug, meta, houses):
    hero = houses[0]["image"] if houses and houses[0].get("image") else ""
    image = f'<img src="{html.escape(hero)}" alt="{html.escape(firm_name)}" loading="lazy">' if hero else ""
    # City AND country, not just city - the existing directory filter
    # (generate_brand_pages.py's DIRECTORY_FILTER_JS) matches on a
    # card's own visible text, so a visitor typing "Norway" only finds
    # anything once the country is actually part of what's shown here,
    # even though architects.json has always carried a real country
    # field (2026-09-24, prompted by a user question about country
    # search - the data existed, it just wasn't surfaced).
    location_bits = [b for b in [meta.get("city") if meta else None, meta.get("country") if meta else None] if b]
    location_html = html.escape(", ".join(location_bits)) if location_bits else "&nbsp;"
    count = f"{len(houses)} house{'' if len(houses) == 1 else 's'}"
    return f"""
      <a class="maker-card" href="/architects/{slug}.html">
        <div class="maker-card-hero">{image}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(firm_name)}</span>
          <span class="maker-country">{location_html}</span>
          <span class="maker-categories">{count}</span>
        </div>
      </a>"""


def render_architect_page(firm_name, slug, meta, houses):
    page_url = f"{SITE_URL}/architects/{slug}.html"
    location = (meta.get("city") or meta.get("country")) if meta else None
    description = (
        f"{html.escape(firm_name)} - {len(houses)} real house{'' if len(houses) == 1 else 's'}"
        f"{f', {html.escape(location)}' if location else ''}. Each linked to its own real project page."
    )
    houses_sorted = sorted(houses, key=lambda h: h["name"] or "")
    houses_html = "".join(house_card_html(h) for h in houses_sorted)
    site_link = (
        f'<a class="brand-site-link" href="{html.escape(meta["url"])}" target="_blank" rel="noopener noreferrer">Visit site &rarr;</a>'
        if meta and meta.get("url") else ""
    )
    contact_bits = []
    if meta and meta.get("email"):
        contact_bits.append(f'<a href="mailto:{html.escape(meta["email"])}">{html.escape(meta["email"])}</a>')
    if meta and meta.get("phone"):
        contact_bits.append(html.escape(meta["phone"]))
    contact_html = f'<p class="page-tagline">{" &middot; ".join(contact_bits)}</p>' if contact_bits else ""

    breadcrumb_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Formground", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Architects", "item": f"{SITE_URL}/architects.html"},
            {"@type": "ListItem", "position": 3, "name": firm_name, "item": page_url},
        ],
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(firm_name)} — Architects — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(firm_name)} — Formground">
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
  <p class="page-tagline">Architects.</p>
  <div class="maker-header">
    <p class="eyebrow">Architect</p>
    <h1 class="maker-name">{html.escape(firm_name)}</h1>
    {site_link}
  </div>
  {contact_html}
  <p class="category-intro">{len(houses)} real house{'' if len(houses) == 1 else 's'} designed by {html.escape(firm_name)}, each pulled from their own project page.</p>
  <div class="maker-grid">{houses_html}
  </div>
  <p class="page-tagline">Looking for someone to help build it? <a href="/craftspeople.html">Browse Craftspeople &rarr;</a> &middot; <a href="/work.html?q=house">Browse every house on Work &rarr;</a></p>
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


def render_architects_index(firms_with_slugs, meta_by_name, houses_by_firm):
    items = "".join(
        architect_card_html(firm_name, slug, meta_by_name.get(firm_name), houses_by_firm[firm_name])
        for firm_name, slug in sorted(firms_with_slugs, key=lambda p: p[0].lower())
    )
    total_houses = sum(len(hs) for hs in houses_by_firm.values())
    page_url = f"{SITE_URL}/architects.html"
    description = (
        f"{len(firms_with_slugs)} architecture firms on Formground, {total_houses} real houses total - "
        "each linked straight to its own project page."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Architects — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="Architects — Formground">
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
<main style="max-width:1160px;">{directory_filter_html("Filter by firm or city…", "Architects")}
  <h1 class="sr-only">Architects</h1>
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
    if f"{SITE_URL}/architects.html" in text:
        print("Sitemap already has architects entries - regenerate docs/sitemap.xml from scratch to refresh dates.")
        return
    new_entries = [
        f"  <url>\n    <loc>{SITE_URL}/architects.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>"
    ]
    for slug in slugs:
        new_entries.append(
            f"  <url>\n    <loc>{SITE_URL}/architects/{slug}.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.5</priority>\n  </url>"
        )
    updated = text.replace("</urlset>", "\n".join(new_entries) + "\n</urlset>")
    SITEMAP_PATH.write_text(updated)
    print(f"Appended {len(new_entries)} URLs to {SITEMAP_PATH}.")


def generate():
    firms = json.loads(ARCHITECTS_PATH.read_text())
    meta_by_name = {f["name"]: f for f in firms}
    houses = json.loads(HOUSES_PATH.read_text())

    houses_by_firm = defaultdict(list)
    for h in houses:
        houses_by_firm[h["firm"]].append(h)

    ARCHITECTS_DIR.mkdir(parents=True, exist_ok=True)

    slugs_seen = {}
    firms_with_slugs = []
    all_known_names = set(meta_by_name) | set(houses_by_firm)
    for firm_name in all_known_names:
        slug = slugify(firm_name)
        if slug in slugs_seen and slugs_seen[slug] != firm_name:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = firm_name

        firm_houses = houses_by_firm.get(firm_name, [])
        if not firm_houses:
            # A firm curated in architects.json but never scraped at the
            # per-house level (or with zero houses passing the real-house
            # + contemporary/modern bar) doesn't get a page - narrower
            # than the old "any representative photo" bar. Delete any
            # stale page from the old model rather than leave it
            # reachable with content that no longer matches the site's
            # real inclusion criteria - same pattern generate_brand_pages.py
            # uses for hidden brands.
            (ARCHITECTS_DIR / f"{slug}.html").unlink(missing_ok=True)
            continue

        (ARCHITECTS_DIR / f"{slug}.html").write_text(render_architect_page(firm_name, slug, meta_by_name.get(firm_name), firm_houses))
        firms_with_slugs.append((firm_name, slug))

    (DOCS_DIR / "architects.html").write_text(
        render_architects_index(firms_with_slugs, meta_by_name, houses_by_firm)
    )
    append_to_sitemap(sorted(s for _, s in firms_with_slugs))

    total_houses = sum(len(houses_by_firm[n]) for n, _ in firms_with_slugs)
    print(f"Generated {len(firms_with_slugs)} architect firm pages ({total_houses} real houses total) + architects.html.")


if __name__ == "__main__":
    generate()
