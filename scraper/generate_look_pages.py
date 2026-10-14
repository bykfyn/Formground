"""
Look Edits: a room put together from pieces by different makers (docs/edits/<slug>.html), e.g. "Warm minimal living room".
Data: data/looks.json (a hand-picked list per look). Unlike the themed Edits (one product type, found by a query) and the
profile Edits (one creator), a look is a hand-picked set across categories: a board of the pieces on one grid (large sofa,
equal-height tiles beneath), then each piece as the standard product card with its role above it.

The board is a 12-column grid with 8px gaps and every piece in its own box (see project-docs/Site_Patterns.md, "Look boards").
Each look sets its own tile areas, so it can vary; the gaps, the box style and the card row beneath stay the same.
A pick that no longer exists (a maker removed the page) is skipped; a look with fewer than six pieces left is not built.

Run after generate_edits_page.py (it appends to the sitemap):
    python3 generate_look_pages.py
"""

import html
import json
import sqlite3
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
DATA_PATH = SCRAPER_DIR.parent / "data" / "looks.json"
sys.path.insert(0, str(SCRAPER_DIR))
sys.path.insert(0, str(SCRAPER_DIR.parent / "backend"))

from generate_brand_pages import (  # noqa: E402
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    DB_PATH,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_URL,
    fit_title,
    product_card_html,
    site_nav_html,
)
from generate_theme_landing_pages import append_to_sitemap  # noqa: E402
from image_sizes import TILE, sized  # noqa: E402
from site_assets import ICONS_CSS, SHARE_JS  # noqa: E402

MIN_PIECES = 6

LOOK_CSS = """
  .look-intro { max-width: 640px; margin: 0 auto 28px; font-size: 15px; line-height: 1.65; color: var(--text-secondary); text-align: center; }
  .look-board { display: grid; grid-template-columns: repeat(12, 1fr); gap: 8px; padding: 8px; box-sizing: border-box;
    aspect-ratio: 996 / 608; max-width: 996px; margin: 0 auto 32px; border-radius: 6px; }
  .look-tile { display: block; position: relative; overflow: hidden; min-height: 0; border-radius: 3px; }
  .look-tile img { width: 100%; height: 100%; object-fit: cover; display: block; transition: opacity 0.15s ease; }
  .look-tile.contain img { object-fit: contain; }
  .look-tile:hover img { opacity: 0.92; }
  .look-tile:focus-visible { outline: 2px solid var(--text-primary); outline-offset: 2px; }
  .look-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  .look-role { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin: 0 0 8px; }
  @media (max-width: 640px) { .look-grid { grid-template-columns: repeat(2, 1fr); } }
"""


def load():
    return json.loads(DATA_PATH.read_text()) if DATA_PATH.exists() else []


def _row(conn, brand, name):
    return conn.execute("SELECT * FROM products WHERE brand = ? AND product_name = ? AND link_dead = 0 AND image_url != '' LIMIT 1",
                        (brand, name)).fetchone()


def resolve(look, conn):
    """[(pick, product row dict)] for the picks that still exist."""
    out = []
    for pick in look["picks"]:
        row = _row(conn, pick["brand"], pick["name"])
        if row:
            out.append((pick, dict(row)))
        else:
            print(f"  {look['slug']}: skipped {pick['brand']} / {pick['name']} (no longer in the data)")
    return out


def hub_item(look, conn):
    """(image url, object-position, (name, brand, link)) for the look's tile on the Edits hub: one clean photo of one piece."""
    row = _row(conn, look["hub"]["brand"], look["hub"]["name"])
    if not row:
        return None
    return row["image_url"], look["hub"].get("position"), (row["product_name"], row["brand"], row["product_url"])


def _tile_html(pick, row, area):
    c0, c1, r0, r1 = area
    contain = pick.get("fit") == "contain"
    bg = pick.get("bg") or "#fff"
    pos = f' style="object-position:{pick["position"]}"' if pick.get("position") else ""
    alt = f'{row["product_name"]} by {row["brand"]}'
    return (f'<a class="look-tile{" contain" if contain else ""}" href="{html.escape(row["product_url"])}" target="_blank" '
            f'rel="noopener noreferrer" data-product="{html.escape(row["product_name"])}" data-brand="{html.escape(row["brand"])}" '
            f'style="grid-column:{c0} / {c1};grid-row:{r0} / {r1};background:{html.escape(bg)}" aria-label="{html.escape(alt)}">'
            f'<img src="{html.escape(sized(row["image_url"], TILE))}" alt="{html.escape(alt)}"{pos} loading="lazy"></a>')


def render(look, pieces):
    slug, title = look["slug"], look["title"]
    url = f"{SITE_URL}/edits/{slug}.html"
    seo_title = fit_title(f"{title}: an Edit", title)
    description = look["description"]
    tiles = "".join(_tile_html(p, r, look["areas"][p["slot"]]) for p, r in pieces)
    cards = "".join(f'<div class="look-item"><p class="look-role">{html.escape(p["label"])}</p>'
                    f'{product_card_html(r, show_brand=True, share=True)}</div>' for p, r in pieces)
    breadcrumb = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Formground", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Edits", "item": f"{SITE_URL}/edits.html"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url},
        ]}, ensure_ascii=False, separators=(",", ":"))
    board_style = f"background:{look['board']};grid-template-rows:{look['rows']};"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(seo_title)}</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(seo_title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{breadcrumb}</script>
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}{LOOK_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("edits")}
</header>
<main>
  <div class="maker-header">
    <p class="eyebrow">Edit &middot; {html.escape(look['kind'])}</p>
    <h1 class="maker-name">{html.escape(title)}</h1>
  </div>
  <p class="look-intro">{html.escape(look['intro'])}</p>
  <div class="look-board" style="{board_style}">{tiles}</div>
  <div class="look-grid">{cards}</div>
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>{CARD_CLICK_TRACKING_JS}</script>
<script src="{SHARE_JS}" defer></script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def generate():
    looks = load()
    if not looks:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    (DOCS_DIR / "edits").mkdir(exist_ok=True)
    slugs = []
    for look in looks:
        pieces = resolve(look, conn)
        if len(pieces) < MIN_PIECES:
            print(f"Skipped {look['title']}: only {len(pieces)} of its pieces still exist.")
            continue
        (DOCS_DIR / "edits" / f"{look['slug']}.html").write_text(render(look, pieces))
        slugs.append(f"edits/{look['slug']}")
    conn.close()
    append_to_sitemap(slugs)
    print(f"Generated {len(slugs)} look Edits.")


if __name__ == "__main__":
    generate()
