"""
Formground Edits hub page generator.

WHAT THIS DOES: generates docs/edits.html, the one page that gathers
every real Themed Edit (see generate_themed_edit_pages.py's THEMES) in
one place - "so a user can find them all gathered" (user's own framing,
2026-09-30), rather than only discovering one via a homepage teaser or
a Work/Makers search-result promo (both still separate, undecided/
deferred pieces - see project memory, [[edits_hub_page_concept]]).

Reuses generate_themed_edit_pages.py's own THEMES list directly, not a
duplicated one - the next step (adding more Edits) is just a new THEMES
entry there, and it appears here automatically on the next run, with no
second list to keep in sync.

Same shared directory-filter search box as makers.html/architects.html/
designers.html (directory_filter_html/DIRECTORY_FILTER_JS) - "the edits
page itself could use the same search box as we have across the site"
(user's own words) - filtering here is a plain client-side text match
against each card's own title/meta line, same mechanism, no new one.

Not yet linked from the header nav (deliberately) - the last time a
5th item was added there it wrapped badly at some widths, which is why
About lives in the footer instead (see site_nav_html's own docstring).
Whether Edits earns a nav slot is a separate, still-open decision - for
now this page is reachable by direct link/sitemap only, from wherever
a caller (homepage teaser, footer, a future promo) points at it.

RUN (after generate_themed_edit_pages.py, since it needs each theme's
real product/brand counts and image, and appends to the same
sitemap.xml):
    python3 generate_edits_page.py
"""

import html
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
BACKEND_DIR = SCRAPER_DIR.parent / "backend"

sys.path.insert(0, str(BACKEND_DIR))

from generate_brand_pages import (  # noqa: E402
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    DIRECTORY_FILTER_JS,
    FAVICON_TAGS,
    HERO_SEARCH_POSITION_CSS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_URL,
    directory_filter_html,
    site_nav_html,
)
from generate_theme_landing_pages import _group_color_variants, append_to_sitemap  # noqa: E402
import generate_themed_edit_pages as gte  # noqa: E402


def _edit_card_image(theme, cards_to_render):
    """
    The same real photo a visitor sees first on the edit's own page -
    its hand-picked carousel's first entry when the theme has one (a
    human already chose it as the best representative shot), otherwise
    the first product in the grid itself, in the same order
    render_themed_edit_page's own grid uses.
    """
    picks = gte._resolve_carousel_picks(theme, cards_to_render)
    if picks:
        return picks[0].get("image_url", "")
    return cards_to_render[0]["image_url"] if cards_to_render else ""


def render_edits_index(themes_data):
    """
    themes_data is a list of (theme, product_count, brand_count, image)
    tuples, one per THEMES entry, already computed by generate() below.
    Reuses the exact .maker-card/.maker-grid markup makers.html already
    defines in PAGE_CSS - same card shape, a real editorial count in
    place of a maker's country/category tags (an Edit isn't a "brand is
    the minimum unit of inclusion" listing the way makers.html is, so
    showing real depth here doesn't undercut that principle the way it
    would there).
    """
    items = ""
    for theme, count, brand_count, image in sorted(themes_data, key=lambda t: t[0]["title"].lower()):
        image_tag = (
            f'<img src="{html.escape(image)}" alt="{html.escape(theme["title"])}" loading="lazy">'
            if image else ""
        )
        meta = (
            f"{count:,} piece{'' if count == 1 else 's'} "
            f"&middot; {brand_count} maker{'' if brand_count == 1 else 's'}"
        )
        items += f"""
      <a class="maker-card" href="/{theme['slug']}.html">
        <div class="maker-card-hero">{image_tag}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(theme['title'])}</span>
          <span class="maker-country">{meta}</span>
        </div>
      </a>"""

    description = "Curated, editorial groupings of real work from Formground's makers - browse every Edit, gathered in one place."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Edits — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{SITE_URL}/edits.html">
<meta property="og:type" content="website">
<meta property="og:title" content="Edits — Formground">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{SITE_URL}/edits.html">
<meta property="og:image" content="{SITE_URL}/favicon-192x192.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Edits — Formground">
<meta name="twitter:description" content="{html.escape(description)}">
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
<style>{HERO_SEARCH_POSITION_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html()}
</header>
<main style="max-width:1160px;">{directory_filter_html("Filter edits by name…", "Edits")}
  <h1 class="sr-only">Edits</h1>
  <p class="page-tagline">{html.escape(description)}</p>
  <div class="maker-grid">{items}
  </div>
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


def generate():
    themes_data = []
    for theme in gte.THEMES:
        products = theme["fetch"]()
        cards_to_render, _ = _group_color_variants(products)
        brand_count = len({p["brand"] for p in cards_to_render})
        image = _edit_card_image(theme, cards_to_render)
        themes_data.append((theme, len(cards_to_render), brand_count, image))

    (DOCS_DIR / "edits.html").write_text(render_edits_index(themes_data))
    append_to_sitemap(["edits"])
    print(f"Generated edits.html ({len(themes_data)} edits).")


if __name__ == "__main__":
    generate()
