"""
Profile Edits: one editorial page per creator in data/creator_texts.json (docs/edits/<slug>.html), "In profile: <name>".
The text, facts and sources are the same as on the creator's own page on Formground (see creator_texts.py); the page
adds a selection of eight of their real pieces or houses, each linked to its own page on the creator's site, and links
to the full listing and to the creator's website. Run after generate_edits_page.py (it appends to the sitemap).
"""

import html
import json
import sqlite3
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
sys.path.insert(0, str(SCRAPER_DIR))
sys.path.insert(0, str(SCRAPER_DIR.parent / "backend"))

import creator_texts  # noqa: E402
from generate_architects_pages import house_card_html  # noqa: E402
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
from site_assets import ICONS_CSS, SHARE_JS  # noqa: E402

LISTING_PAGE = {"architects": "architects", "makers": "brands", "designers": "designers"}
SEE_ALL_NOUN = {"architects": "houses", "makers": "pieces", "designers": "pieces"}
PROFILE_CSS = """
  .profile-links { font-size: 13px; text-align: center; margin: 4px 0 26px; }
  .profile-links a { color: var(--text-accent); text-decoration: none; white-space: nowrap; }
  .profile-links a:hover { text-decoration: underline; }
  .profile-links .sep { color: var(--text-muted); margin: 0 8px; }
  .grid { grid-template-columns: repeat(4, 1fr); gap: 16px; }
  @media (max-width: 640px) { .grid { grid-template-columns: repeat(2, 1fr); } }
  .profile-picks-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--text-muted); margin: 8px 0 16px; }
"""


def _find_cards(entry, houses_by_image, conn):
    """Card HTML for each of the Edit's picks, in order; a pick that no longer exists is skipped."""
    cards = []
    for image in entry["edit"]["picks"]:
        if entry["group"] == "architects":
            house = houses_by_image.get(image)
            if house:
                cards.append(house_card_html(house))
        else:
            row = conn.execute("SELECT * FROM products WHERE image_url = ? AND link_dead = 0 LIMIT 1", (image,)).fetchone()
            if row:
                cards.append(product_card_html(dict(row), show_brand=entry["group"] == "designers", share=True))
    return cards


def _count(entry, houses, conn):
    group = entry["group"]
    if group == "architects":
        return sum(1 for h in houses if h["firm"] == entry["name"] and h.get("image"))
    if group == "makers":
        return conn.execute("SELECT COUNT(*) FROM products WHERE brand = ? AND link_dead = 0", (entry["name"],)).fetchone()[0]
    from designer_credits import split_credit
    return sum(1 for (raw,) in conn.execute("SELECT designer FROM products WHERE designer LIKE ? AND image_url != ''",
                                            (f"%{entry['name'].split()[-1]}%",)) if entry["name"] in split_credit(raw))


def render(entry, count, cards):
    edit = entry["edit"]
    group, name = entry["group"], entry["name"]
    url = f"{SITE_URL}/edits/{edit['slug']}.html"
    title = fit_title(f"In profile: {name}", name)
    description = edit["standfirst"]
    page_slug = entry["page_slug"]
    listing = f"/{group}/{page_slug}.html" if group != "makers" else f"/brands/{page_slug}.html"
    breadcrumb = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Formground", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Edits", "item": f"{SITE_URL}/edits.html"},
            {"@type": "ListItem", "position": 3, "name": f"In profile: {name}", "item": url},
        ]}, ensure_ascii=False, separators=(",", ":"))
    grid_class = "maker-grid" if group == "architects" else "grid"
    links = (f'<a href="{listing}">See all {count:,} {SEE_ALL_NOUN[group]} &rarr;</a><span class="sep">&middot;</span>'
             f'<a href="{html.escape(entry["website"])}" target="_blank" rel="noopener noreferrer">Visit their site &rarr;</a>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)}">
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
<style>{PAGE_CSS}</style>
<style>{creator_texts.CREATOR_TEXT_CSS}{PROFILE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("edits")}
</header>
<main>
  <div class="maker-header">
    <p class="eyebrow">In profile &middot; {creator_texts.KIND[group]}</p>
    <h1 class="maker-name">{html.escape(name)}</h1>
  </div>
  <p class="profile-links">{links}</p>{creator_texts.text_block_html(group, page_slug, count)}
  <p class="profile-picks-title">A selection</p>
  <div class="{grid_class}">{"".join(cards)}
  </div>
  <p class="profile-links" style="margin-top:26px">{links}</p>
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>
  document.querySelectorAll(".card-image img, .maker-card-hero img").forEach(function (img) {{
    img.addEventListener("load", function () {{
      var ratio = img.naturalWidth / img.naturalHeight;
      if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
    }});
  }});
</script>
<script>{CARD_CLICK_TRACKING_JS}</script>
<script src="{SHARE_JS}" defer></script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def generate():
    entries = creator_texts.load()
    if not entries:
        return
    houses = json.loads((SCRAPER_DIR.parent / "data" / "houses.json").read_text())
    houses_by_image = {h["image"]: h for h in houses if h.get("image")}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    (DOCS_DIR / "edits").mkdir(exist_ok=True)
    slugs = []
    for entry in entries.values():
        cards = _find_cards(entry, houses_by_image, conn)
        if len(cards) < 6:
            print(f"Skipped {entry['name']}: only {len(cards)} of its picks still exist.")
            continue
        count = _count(entry, houses, conn)
        (DOCS_DIR / "edits" / f"{entry['edit']['slug']}.html").write_text(render(entry, count, cards))
        slugs.append(f"edits/{entry['edit']['slug']}")
    conn.close()
    append_to_sitemap(slugs)
    print(f"Generated {len(slugs)} profile Edits.")


if __name__ == "__main__":
    generate()
