"""
Formground Architects & Interior Designers page generator.

WHAT THIS DOES:
  Generates one static, crawlable HTML page per architect/interior-
  design firm (docs/architects/{slug}.html), plus docs/architects.html
  (the index, same visual pattern as makers.html/craftspeople.html),
  from data/architects.json (see scrape_architects.py). Appends these
  new pages to the existing docs/sitemap.xml.

WHY MINIMAL PHOTOS, NOT NAMED PROJECTS: see scrape_architects.py's
docstring - a small real photo grid per firm, not per-project names/
descriptions, based on real coverage testing this session (63-80% vs
~3% for structured per-project extraction).

RUN (after scrape_architects.py, and after generate_brand_pages.py so
sitemap.xml already exists to append to):
    python3 generate_architects_pages.py
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
ARCHITECTS_DIR = DOCS_DIR / "architects"
ARCHITECTS_PATH = DATA_DIR / "architects.json"
SITEMAP_PATH = DOCS_DIR / "sitemap.xml"

# A little extra CSS just for the photo grid on a profile page - the
# shared PAGE_CSS from generate_brand_pages.py already covers the
# per-firm card grid (index) and page tokens.
PROFILE_PHOTO_CSS = """
  .photo-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px; margin: 0 0 28px; }
  .photo-grid img { width: 100%; aspect-ratio: 4/3; object-fit: cover;
    border-radius: 10px; background: var(--surface-1); display: block; }
"""


def architect_card_html(firm, slug):
    hero = firm["photos"][0] if firm.get("photos") else ""
    image = f'<img src="{html.escape(hero)}" alt="{html.escape(firm["name"])}" loading="lazy">' if hero else ""
    country_html = html.escape(firm["city"]) if firm.get("city") else "&nbsp;"
    specialization = " · ".join(firm.get("specialization", []))
    return f"""
      <a class="maker-card" href="/architects/{slug}.html">
        <div class="maker-card-hero">{image}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(firm["name"])}</span>
          <span class="maker-country">{country_html}</span>
          <span class="maker-categories">{html.escape(specialization)}</span>
        </div>
      </a>"""


def render_architect_page(firm, slug):
    tags = "".join(f'<span class="tag">{html.escape(s)}</span>' for s in firm.get("specialization", []))
    page_url = f"{SITE_URL}/architects/{slug}.html"
    location = firm.get("city") or firm.get("country") or ""
    description = (
        f"{html.escape(firm['name'])} - {html.escape(', '.join(firm.get('specialization', [])))}"
        f"{f', {html.escape(location)}' if location else ''}. Real project photos, linked to their own site."
    )
    photos_html = "".join(
        f'<img src="{html.escape(p)}" alt="{html.escape(firm["name"])} project photo" loading="lazy">'
        for p in firm.get("photos", [])
    )
    site_link = (
        f'<a class="brand-site-link" href="{html.escape(firm["url"])}" target="_blank" rel="noopener noreferrer">Visit site &rarr;</a>'
        if firm.get("url") else ""
    )
    contact_bits = []
    if firm.get("email"):
        contact_bits.append(f'<a href="mailto:{html.escape(firm["email"])}">{html.escape(firm["email"])}</a>')
    if firm.get("phone"):
        contact_bits.append(html.escape(firm["phone"]))
    contact_html = f'<p class="page-tagline">{" &middot; ".join(contact_bits)}</p>' if contact_bits else ""

    breadcrumb_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Formground", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Architects & Interior Designers", "item": f"{SITE_URL}/architects.html"},
            {"@type": "ListItem", "position": 3, "name": firm["name"], "item": page_url},
        ],
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(firm["name"])} — Architects &amp; Interior Designers — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(firm['name'])} — Formground">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{breadcrumb_json}</script>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}{PROFILE_PHOTO_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline">Architects &amp; Interior Designers.</p>
  <div class="maker-header">
    <p class="eyebrow">{" / ".join(firm.get("specialization", ["Architect"]))}</p>
    <h1 class="maker-name">{html.escape(firm["name"])}</h1>
    <div class="tags">{tags}</div>
    {site_link}
  </div>
  {contact_html}
  <div class="photo-grid">{photos_html}</div>
  <p class="page-tagline">Looking for someone to help build it? <a href="/craftspeople.html">Browse Craftspeople &rarr;</a></p>
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/privacy.html">Privacy</a>
  </p>
</main>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def render_architects_index(firms_with_slugs):
    items = "".join(
        architect_card_html(firm, slug)
        for firm, slug in sorted(firms_with_slugs, key=lambda p: p[0]["name"].lower())
    )
    page_url = f"{SITE_URL}/architects.html"
    description = (
        f"{len(firms_with_slugs)} architects and interior designers on Formground - real project photos, "
        "linked straight to each firm's own site."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Architects &amp; Interior Designers — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="Architects &amp; Interior Designers — Formground">
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
<main style="max-width:1100px;">
  <h1>Architects &amp; Interior Designers</h1>
  <p class="category-intro">
    Buildings and interiors - real firms curated individually, each with a small set of real project
    photos pulled from their own site. Not an exhaustive directory; every card links to that firm's own site.
  </p>
  <div class="maker-grid">{items}
  </div>
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/privacy.html">Privacy</a>
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
    ARCHITECTS_DIR.mkdir(parents=True, exist_ok=True)

    slugs_seen = {}
    firms_with_slugs = []
    for firm in firms:
        slug = slugify(firm["name"])
        if slug in slugs_seen and slugs_seen[slug] != firm["name"]:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = firm["name"]

        if not firm.get("photos"):
            # Curated-but-currently-photoless firms don't get a page yet
            # rather than shipping an empty-looking profile - same
            # "no image means not a result" principle already applied
            # to Makers. Real bug found and fixed: a firm that HAD real
            # photos on a previous run (before the vision-relevance
            # filter got stricter) but has none now would otherwise keep
            # its old page sitting on disk forever, reachable and
            # carrying stale copy, just silently dropped from the index/
            # sitemap - delete it explicitly instead, same pattern
            # generate_brand_pages.py already uses for hidden brands.
            (ARCHITECTS_DIR / f"{slug}.html").unlink(missing_ok=True)
            continue

        (ARCHITECTS_DIR / f"{slug}.html").write_text(render_architect_page(firm, slug))
        firms_with_slugs.append((firm, slug))

    (DOCS_DIR / "architects.html").write_text(render_architects_index(firms_with_slugs))
    append_to_sitemap(sorted(s for _, s in firms_with_slugs))

    skipped = len(firms) - len(firms_with_slugs)
    print(f"Generated {len(firms_with_slugs)} architect firm pages + architects.html ({skipped} skipped, no photos).")


if __name__ == "__main__":
    generate()
