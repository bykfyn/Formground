"""
Formground craftspeople page generator.

WHAT THIS DOES:
  Generates one static, crawlable HTML page per craftsperson/workshop
  (docs/craftspeople/{slug}.html), plus docs/craftspeople.html (the
  index, same visual pattern as makers.html), from data/craftspeople.json
  (see scrape_craftspeople.py). Also appends these new pages to the
  existing docs/sitemap.xml rather than regenerating it from scratch,
  so this can run as its own step without needing to re-derive brand
  data.

WHY THIS EXISTS:
  Craftspeople is the first real category of Formground's
  new Professionals & Services section (see project memory on the
  2026-09-17 ecosystem pivot) - production partners/fabricators,
  sourced from real Swedish craft associations (Interior Cluster
  Sweden, Föreningen Skråhantverkarna), not finished-good makers.
  Deliberately built as static pages reusing generate_brand_pages.py's
  exact pattern (PAGE_CSS, FAVICON_TAGS, slugify, CLOUDFLARE_ANALYTICS)
  rather than touching the backend/query_engine - this data doesn't
  fit that product-shaped schema (no material/style), and the site's
  whole browse layer (makers.html, category pages) is already static
  generation with no search box, so this slots into the same layer at
  no risk to the live Makers search.

RUN (after scrape_craftspeople.py, and after generate_brand_pages.py
so sitemap.xml already exists to append to):
    python3 generate_craftspeople_pages.py
"""

import html
import json
from pathlib import Path

from generate_brand_pages import (
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_NAV_HTML,
    SITE_URL,
    slugify,
)

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
DOCS_DIR = SCRAPER_DIR.parent / "docs"
CRAFTSPEOPLE_DIR = DOCS_DIR / "craftspeople"
CRAFTSPEOPLE_PATH = DATA_DIR / "craftspeople.json"
ASSOCIATIONS_PATH = DATA_DIR / "associations.json"
SITEMAP_PATH = DOCS_DIR / "sitemap.xml"


def load_associations():
    associations = json.loads(ASSOCIATIONS_PATH.read_text())
    return {a["id"]: a for a in associations}


def craftsperson_card_html(person, slug):
    image = (
        f'<img src="{html.escape(person["image_url"])}" alt="{html.escape(person["name"])}" loading="lazy">'
        if person.get("image_url") else ""
    )
    country_html = html.escape(person["country"]) if person.get("country") else "&nbsp;"
    areas = " · ".join(person.get("areas", []))
    return f"""
      <a class="maker-card" href="/craftspeople/{slug}.html">
        <div class="maker-card-hero">{image}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(person["name"])}</span>
          <span class="maker-country">{country_html}</span>
          <span class="maker-categories">{html.escape(areas)}</span>
        </div>
      </a>"""


def render_craftsperson_page(person, slug, associations):
    tags = "".join(f'<span class="tag">{html.escape(a)}</span>' for a in person.get("areas", []))
    page_url = f"{SITE_URL}/craftspeople/{slug}.html"
    location = person.get("city") or person.get("country") or ""
    description = (
        f"{html.escape(person['name'])} - {html.escape(', '.join(person.get('areas', [])))}"
        f"{f', {html.escape(location)}' if location else ''}. "
        "Sourced from a real Swedish craft association, not a Formground listing."
    )

    credit_links = []
    for aid in person.get("associations", []):
        assoc = associations.get(aid)
        if assoc:
            credit_links.append(
                f'<a href="{html.escape(assoc["website"])}" target="_blank" rel="noopener noreferrer">{html.escape(assoc["name"])}</a>'
            )
    credit_html = (
        f'<p class="page-tagline">Found via {" and ".join(credit_links)}.</p>' if credit_links else ""
    )

    site_link = (
        f'<a class="brand-site-link" href="{html.escape(person["website"])}" target="_blank" rel="noopener noreferrer">Visit site &rarr;</a>'
        if person.get("website") else ""
    )

    breadcrumb_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Formground", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Craftspeople", "item": f"{SITE_URL}/craftspeople.html"},
            {"@type": "ListItem", "position": 3, "name": person["name"], "item": page_url},
        ],
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(person["name"])} — Craftspeople — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(person['name'])} — Formground">
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
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline">Craftspeople — production and fabrication partners.</p>
  <div class="maker-header">
    <p class="eyebrow">Craftsperson</p>
    <h1 class="maker-name">{html.escape(person["name"])}</h1>
    <div class="tags">{tags}</div>
    {site_link}
  </div>
  {credit_html}
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/privacy.html">Privacy</a> &middot; <a href="/about.html">About</a>
  </p>
</main>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def render_craftspeople_index(people_with_slugs):
    items = "".join(
        craftsperson_card_html(person, slug)
        for person, slug in sorted(people_with_slugs, key=lambda p: p[0]["name"].lower())
    )
    page_url = f"{SITE_URL}/craftspeople.html"
    description = (
        f"{len(people_with_slugs)} craftspeople on Formground - real production and "
        "fabrication partners sourced from Swedish craft associations, linked straight to their own sites."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Craftspeople — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="Craftspeople — Formground">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main style="max-width:1160px;">
  <h1>Craftspeople</h1>
  <p class="category-intro">
    Production and fabrication partners - real workshops and craftspeople sourced from Swedish
    craft associations, for makers, architects, and homeowners realizing their own designs.
    Not products for sale; every card links to that craftsperson's own site.
  </p>
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
</script>
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
    if f"{SITE_URL}/craftspeople.html" in text:
        print("Sitemap already has craftspeople entries - regenerate docs/sitemap.xml from scratch to refresh dates.")
        return
    new_entries = [
        f"  <url>\n    <loc>{SITE_URL}/craftspeople.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>"
    ]
    for slug in slugs:
        new_entries.append(
            f"  <url>\n    <loc>{SITE_URL}/craftspeople/{slug}.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.5</priority>\n  </url>"
        )
    updated = text.replace("</urlset>", "\n".join(new_entries) + "\n</urlset>")
    SITEMAP_PATH.write_text(updated)
    print(f"Appended {len(new_entries)} URLs to {SITEMAP_PATH}.")


def generate():
    people = json.loads(CRAFTSPEOPLE_PATH.read_text())
    associations = load_associations()
    CRAFTSPEOPLE_DIR.mkdir(parents=True, exist_ok=True)

    slugs_seen = {}
    people_with_slugs = []
    for person in people:
        slug = slugify(person["name"])
        if slug in slugs_seen and slugs_seen[slug] != person["name"]:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = person["name"]
        (CRAFTSPEOPLE_DIR / f"{slug}.html").write_text(render_craftsperson_page(person, slug, associations))
        people_with_slugs.append((person, slug))

    (DOCS_DIR / "craftspeople.html").write_text(render_craftspeople_index(people_with_slugs))
    append_to_sitemap(sorted(s for _, s in people_with_slugs))

    print(f"Generated {len(people_with_slugs)} craftsperson pages + craftspeople.html.")


if __name__ == "__main__":
    generate()
