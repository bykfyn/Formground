"""
Generates docs/galleries/<slug>.html: one page for each gallery in data/retailers.json (entries with kind "gallery"). 2026-11-25.

A gallery is not a stockist. It shows and often represents designers (Kolkhoze, Studiotwentyseven) and sells their work to order, so
it gets a page laid out like a maker's page: eyebrow "Gallery", linked tags, a one-line fact line, a profile text, then the designers.
There are no product cards, so no stock is copied (stock in a gallery's shop belongs to the maker: the aggregator rule stands).

  - "On Formground": the gallery's designers we already carry, as maker cards (a maker's page, a designer's page, a portfolio page).
  - "Also at <gallery>": the other designers as pills. A pill links to the designer's own site when we know it (data/designer_sites.json)
    and otherwise to the designer's page at the gallery (retailers.json "designer_pages"), so no designer is left as bare text
    when the gallery has a page for them.
  - Maker and designer pages point back with "Shown at" (generate_brand_pages.render_galleries_section).

The text, facts and sources come from data/creator_texts.json ("retailers:<slug>"). The Marketplace lists the galleries too, apart from
the stockists (generate_marketplace_page.py).

    python3 scraper/generate_gallery_pages.py
"""
import html
import json
import sqlite3
from pathlib import Path

import brand_selection
import creator_texts
from designer_credits import split_credit
from generate_brand_pages import (
    BRAND_SIMILAR_CSS,
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_URL,
    fit_title,
    gallery_slug,
    load_galleries,
    site_nav_html,
    slugify,
    tags_html,
    umbrella_categories_for,
)
from image_sizes import CARD, sized
from site_assets import ICONS_CSS

SCRAPER_DIR = Path(__file__).parent
REPO = SCRAPER_DIR.parent
DOCS = REPO / "docs"
GALLERIES_DIR = DOCS / "galleries"
DB_PATH = REPO / "data" / "formground.db"
SITEMAP_PATH = DOCS / "sitemap.xml"
SITES_PATH = REPO / "data" / "designer_sites.json"
PORTFOLIO_PATH = REPO / "data" / "portfolio_designers.json"


def _lookups():
    """What the gallery pages need to match a gallery's designer names to pages on Formground."""
    raw = json.load(open(SCRAPER_DIR / "brands.json"))
    brands = {b["name"].casefold(): b for b in (raw if isinstance(raw, list) else raw["brands"])}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    by_brand, by_designer = {}, {}
    for row in conn.execute("SELECT * FROM products WHERE image_url != '' AND link_dead IS NOT 1"):
        r = dict(row)
        by_brand.setdefault(r["brand"].casefold(), []).append(r)
        for n in split_credit(r["designer"] or ""):
            by_designer.setdefault(n, []).append(r)
    conn.close()
    portfolio = {d["name"]: d for d in (json.load(open(PORTFOLIO_PATH)) if PORTFOLIO_PATH.exists() else [])}
    sites = json.load(open(SITES_PATH)) if SITES_PATH.exists() else {}
    return brands, by_brand, by_designer, portfolio, sites


def _card(name, href, image, country, caption):
    img = f'<img src="{html.escape(sized(image, CARD))}" alt="{html.escape(name)}" loading="lazy">'
    return (f'\n      <a class="maker-card" href="{href}"><div class="maker-card-hero">{img}</div>'
            f'<div class="maker-card-body"><span class="maker-name">{html.escape(name)}</span>'
            f'<span class="maker-country">{html.escape(country) if country else "&nbsp;"}</span>'
            f'<span class="maker-categories">{html.escape(caption)}</span></div></a>')


def designer_entry(name, lk):
    """How a gallery's designer shows: ("card", html) when we carry them with a photo, else ("pill", name, href, title)."""
    brands, by_brand, by_designer, portfolio, sites = lk
    slug = slugify(name)
    rows = by_brand.get(name.casefold()) or []
    maker = brands.get(name.casefold()) or {}
    if rows and (DOCS / "brands" / f"{slug}.html").exists() and not maker.get("hidden"):
        pick = brand_selection.representative_selection(rows, 1)
        if pick:
            return "card", _card(name, f"/brands/{slug}.html", pick[0]["image_url"], maker.get("country", ""), ", ".join(umbrella_categories_for(rows)))
    if (DOCS / "designers" / f"{slug}.html").exists():
        page = f"/designers/{slug}.html"
        country = creator_texts.country_of("designers", slug) or (portfolio.get(name) or {}).get("country", "")
        rows = by_designer.get(name) or []
        pick = brand_selection.representative_selection(rows, 1) if rows else []
        image = pick[0]["image_url"] if pick else next((w["image"] for w in (portfolio.get(name) or {}).get("works", []) if w.get("image")), "")
        entry = creator_texts.get("designers", slug)
        products = next((v for k, v in (entry or {}).get("facts", []) if k == "Products"), "")
        caption = ", ".join(umbrella_categories_for(rows)) if rows else products
        if image:
            return "card", _card(name, page, image, country, caption)
        return "pill", name, page, "Page on Formground"
    return None


def pill(name, href, title=""):
    inner = f'<span class="stockist-name">{html.escape(name)}</span>'
    if not href:
        return f'<span class="stockist-item">{inner}</span>'
    external = href.startswith("http")
    ext = ' target="_blank" rel="noopener noreferrer"' if external else ""
    t = f' title="{html.escape(title)}"' if title else ""
    return f'<a class="stockist-item" href="{html.escape(href)}"{ext}{t}>{inner}</a>'


def render_gallery_page(g, lk):
    name, slug = g["name"], gallery_slug(g)
    page_url = f"{SITE_URL}/galleries/{slug}.html"
    sites, pages = lk[4], g.get("designer_pages") or {}
    designers = sorted(set(g.get("brands") or []), key=lambda n: slugify(n))
    cards, pills = [], []
    for d in designers:
        got = designer_entry(d, lk)
        if got and got[0] == "card":
            cards.append(got[1])
        elif got:
            pills.append(pill(d, got[2], got[3]))
        elif (sites.get(d) or {}).get("url"):
            pills.append(pill(d, sites[d]["url"], "Own site"))
        elif pages.get(d):
            pills.append(pill(d, pages[d], f"Page at {name}"))
        else:
            pills.append(pill(d, ""))
    count = len(designers)
    country = creator_texts.country_of("retailers", slug) or g.get("country", "")
    tags = tags_html([c for c in (g.get("categories") or [])] + ([country] if country else []), country)
    text = creator_texts.text_block_html("retailers", slug, count, facts_block=False)
    meta = creator_texts.meta_line_html("retailers", slug, with_country=False)
    on_fg = ""
    if cards:
        on_fg = f"""
  <section class="brand-section selection" style="margin-top:8px">
    <p class="brand-section-title">On Formground</p>
    <p class="like-note">{len(cards)} of {name}'s {count} designers are on Formground, each with a page of their own.</p>
    <div class="like-grid">{"".join(cards)}
    </div>
  </section>"""
    also = ""
    if pills:
        also = f"""
  <section class="brand-section">
    <p class="brand-section-title">Also at {html.escape(name)}</p>
    <p class="like-note">The other designers the gallery shows, linked to their own site where we know it and otherwise to their page at the gallery.</p>
    <div class="stockist-row">{"".join(pills)}</div>
  </section>"""
    description = (f"{name}: a design gallery in {g.get('city') or country} showing {count} designers. "
                   f"{len(cards)} of them are on Formground." if cards else
                   f"{name}: a design gallery in {g.get('city') or country} showing {count} designers.")
    seo_title = fit_title(f"{name}: design gallery", name)
    breadcrumb = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Formground", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Marketplace", "item": f"{SITE_URL}/marketplace.html"},
            {"@type": "ListItem", "position": 3, "name": name, "item": page_url},
        ]})
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(seo_title)}</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(seo_title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{breadcrumb}</script>
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}{BRAND_SIMILAR_CSS}</style>
{creator_texts.style_tag("retailers", slug)}
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("creators")}
</header>
<main>
  <div class="maker-header">
    <p class="eyebrow">Gallery</p>
    <h1 class="maker-name">{html.escape(name)}</h1>
    <div class="tags">{tags}</div>{meta}
    <a class="brand-site-link" href="{html.escape(g["website"])}" target="_blank" rel="noopener noreferrer">Visit site &rarr;</a>
  </div>
  {text}{on_fg}{also}
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
    new = [f"  <url>\n    <loc>{SITE_URL}/galleries/{s}.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.5</priority>\n  </url>"
           for s in slugs if f"{SITE_URL}/galleries/{s}.html" not in text]
    if new:
        SITEMAP_PATH.write_text(text.replace("</urlset>", "\n".join(new) + "\n</urlset>"))
    print(f"Appended {len(new)} gallery URLs to {SITEMAP_PATH}.")


def generate():
    GALLERIES_DIR.mkdir(parents=True, exist_ok=True)
    lk = _lookups()
    slugs = []
    for g in load_galleries():
        slug = gallery_slug(g)
        (GALLERIES_DIR / f"{slug}.html").write_text(render_gallery_page(g, lk))
        slugs.append(slug)
    for existing in GALLERIES_DIR.glob("*.html"):       # a gallery taken out of retailers.json leaves no stale page
        if existing.stem not in slugs:
            existing.unlink()
    append_to_sitemap(slugs)
    print(f"Generated {len(slugs)} gallery pages.")


if __name__ == "__main__":
    generate()
