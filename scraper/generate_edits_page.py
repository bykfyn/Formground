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

EDITORIAL REDESIGN (2026-09-30, user's own framing: "should look more
editorial" - a banner, a strong header, a centered preamble): the
banner reuses generate_brand_pages.py's BANNER_CAROUSEL_CSS/JS rotation
mechanics (the same primitive Promotions uses) but with its own slide
markup/text classes (.edit-banner-*), not the promo-specific
.promo-name/.promo-cta ones - a Themed Edit isn't a paid placement with
a price/CTA, just a real photo and a title linking to the edit itself.

Same shared search box as makers.html/architects.html/designers.html
(directory_filter_html) - "the edits page itself could use the same
search box as we have across the site" (user's own words) - filtering
here is a plain client-side text match against each card's own title/
meta line. A Work/Makers filter-chip pair briefly sat next to it (every
THEMES entry has an implicit "type" - "work" unless a THEMES entry sets
"type": "makers", none of which exist yet), removed 2026-09-30 (user:
"remove the chips with Work and Makers") since there was nothing real
for the Makers chip to ever show. EDITS_FILTER_JS stayed its own small
script rather than switching to DIRECTORY_FILTER_JS's tier-filter logic
(see generate_brand_pages.py) - that mechanism is named/shaped around
brand tier specifically, not what this page is filtering.

Not yet linked from the header nav (deliberately) - the last time a
5th item was added there it wrapped badly at some widths, which is why
About lives in the footer instead (see site_nav_html's own docstring).
Whether Edits earns a nav slot is a separate, still-open decision - for
now this page is reachable via the full site nav already added to
every page's footer, plus wherever a caller (a homepage teaser, a
future promo) points at it.

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
    BANNER_CAROUSEL_CSS,
    BANNER_CAROUSEL_JS,
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_URL,
    directory_filter_html,
    render_banner_carousel,
    site_nav_html,
)
from generate_theme_landing_pages import append_to_sitemap  # noqa: E402
import generate_themed_edit_pages as gte  # noqa: E402

# How many of the real edits lead as rotating banner slides - all of
# them today (only 4 exist); capped so a much larger future edit count
# doesn't turn the hero into an unreasonably long carousel. Sorted by
# real product count (biggest/most substantial edits lead) rather than
# alphabetically, since the banner is a "look how much is here" teaser,
# not a browsable index - the grid below is already alphabetical for
# that.
# Hand-picked, not auto-selected by size (2026-09-30) - an earlier
# "top N by product count" version put three plain grey-studio product
# shots ahead of Round Coffee Tables' own real in-situ Pinch photo
# (Landry Coffee Table, circular bronze, shown in a real room with a
# sofa in frame), which the user called out live as reading far better
# than any of the studio shots - "sets the tone much better with its in
# situ styling." Kept to a real editorial list so it only ever shows
# photos actually confirmed to work, not whichever edit happens to have
# the most products - extend this list as more real in-situ edit photos
# are found (user's own note: more still need sourcing).
BANNER_SLUGS = ["round-coffee-tables"]

EDITS_PAGE_CSS = (
    BANNER_CAROUSEL_CSS
    + """
  /* Edit-specific banner text - the shared BANNER_CAROUSEL_CSS above
     only defines the slide box/gradient/rotation chrome, not any
     particular text treatment (Promotions' own .promo-name/.promo-cta
     are for a priced placement, which a Themed Edit isn't). */
  .edit-banner-eyebrow {
    display: block; font-size: 13px; color: rgba(255,255,255,0.75);
    text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 8px;
  }
  .edit-banner-title {
    display: block; font-family: 'Archivo', sans-serif; font-weight: 700;
    font-size: 34px; line-height: 1.15; color: #fff; max-width: 70%;
  }
  .edit-banner-brand {
    display: block; font-size: 14px; color: rgba(255,255,255,0.85); margin: 8px 0 0;
  }
  @media (max-width: 640px) {
    .edit-banner-title { font-size: 22px; max-width: 85%; }
  }

  /* Strong header + preamble together, above the banner (2026-09-30,
     user: "so that Edits reads more as the name of a magazine" - title
     first, like a masthead, then a two-line dek, then the photo below
     it). The preamble's own manual <br> (in render_edits_index, not
     here) is deliberate - two real sentences broken after "real work"
     so the first line reads narrower than the second, rather than
     however a plain paragraph happens to wrap at the viewport's width. */
  /* Tightened (2026-09-30, real complaint: the banner sat partially
     below the fold on a 13" laptop) - main's own default 48px top
     padding plus .site-header's default 40px bottom margin left ~108px
     of pure whitespace above the masthead before this, on top of the
     hero block's own spacing. Shaving both this block's margins and
     the page-level gaps above it (see the plain CSS rules right below
     this one) gets the banner meaningfully higher without cramming
     anything - there was real slack to cut, not just a squeeze. */
  main { padding-top: 20px; }
  .site-header { margin-bottom: 16px; }
  .edits-hero { text-align: center; margin: 0 0 20px; }
  .edits-hero h1 {
    font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 44px;
    letter-spacing: 0.01em; margin: 0 0 10px; text-transform: uppercase;
  }
  .edits-preamble {
    font-size: 15px; color: var(--text-secondary);
    max-width: 580px; margin: 0 auto; line-height: 1.6;
  }
  @media (max-width: 640px) {
    .edits-hero h1 { font-size: 30px; }
  }

  /* A fixed 2-column grid, not the bento tried earlier and not
     makers.html's own auto-fit one either (2026-09-30, user: "i don't
     want a bento on the page, but it would be good to have a fixed
     structure of columns and rows as the home page to work within") -
     auto-fit's column count depends on viewport width, so "row 1" or
     "under Ceiling Lamps" never meant the same thing twice (confirmed
     live, repeatedly, this same session) - a real, structural problem,
     not a one-off mistake. Every edit is the same size, no spans, no
     exceptions - with a fixed 2 columns and no items spanning more than
     one cell, plain list order alone determines each card's row/column
     (item 1 = row1-col1, item 2 = row1-col2, item 3 = row2-col1, ...) -
     deterministic at every viewport, no per-card position class needed
     the way the homepage's own real bento (.category-grid) requires for
     its own asymmetric tiles. Two columns lands each square almost
     exactly at 552px wide at this page's max content width (1120px
     usable minus one 16px gap, halved) - the same reference size
     "552x552px" has meant throughout this page's work, now built into
     the grid itself rather than capped after the fact. */
  /* SIX fixed columns (2026-10-03, user: "let's go with six so that we have
     consistency across those pages") - the same density as the individual
     Edit pages' product grid and the homepage shelves, instead of two
     ~550px cards. Still a FIXED count per width tier, never auto-fit, so a
     card's row/column stays deterministic: 6 across, then 4, then 2 on
     phones. */
  .maker-grid { margin: 0 0 40px; grid-template-columns: repeat(6, 1fr); gap: 20px; }
  .maker-card-hero { aspect-ratio: 1/1; }
  /* The featured edit is treated like the homepage's bento tiles (2026-10-03,
     user: "treat the banner as we do the home page main bento"): the photo
     fills the tile, the edit's title sits on it as the header, and the real
     product shown (name, maker, a Visit site link to the maker) appears on
     hover - or always, on touch screens. Half the grid at every tier (3x2 of
     6, 2x2 of 4); align-self stretch overrides the grid's align-items: start so
     the tile fills both rows. A sibling link layer, not a wrapping <a>, so the
     edit link and the maker link never nest. */
  .edit-feature {
    grid-column: span 3; grid-row: span 2; align-self: stretch; min-height: 320px;
    position: relative; overflow: hidden; margin: 0;
    border: 0.5px solid var(--border); background: var(--surface-1);
  }
  .edit-feature img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.4s ease; }
  .edit-feature:hover img { transform: scale(1.03); }
  .edit-feature .cat-link { position: absolute; inset: 0; z-index: 1; }
  /* soft top scrim so the white title reads on light photos too */
  .edit-feature::before { content: ''; position: absolute; left: 0; right: 0; top: 0; height: 40%; z-index: 1; pointer-events: none;
    background: linear-gradient(to bottom, rgba(0,0,0,0.5), rgba(0,0,0,0)); }
  .edit-feature .cat-label { position: absolute; top: 16px; left: 16px; right: 16px; z-index: 2; margin: 0; pointer-events: none;
    font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 24px; line-height: 1.15; color: #fff; letter-spacing: -0.005em; }
  .edit-feature .cat-label small { display: block; margin-top: 4px; font-family: inherit; font-weight: 600; font-size: 12px; opacity: 0.85; letter-spacing: 0; }
  .edit-feature .cat-details {
    position: absolute; left: 0; right: 0; bottom: 0; z-index: 2;
    padding: 36px 16px 14px; padding-right: 130px;
    background: linear-gradient(to top, rgba(0,0,0,0.68), rgba(0,0,0,0));
    color: #fff; opacity: 0; transform: translateY(6px);
    transition: opacity 0.25s ease, transform 0.25s ease; pointer-events: none;
  }
  .edit-feature:hover .cat-details { opacity: 1; transform: translateY(0); }
  .edit-feature .product-name { display: block; font-size: 13.5px; font-weight: 600; margin: 0 0 2px; }
  .edit-feature .product-maker { display: block; font-size: 12px; opacity: 0.85; }
  .edit-feature .visit-source {
    position: absolute; bottom: 12px; right: 12px; z-index: 3;
    display: flex; align-items: center; gap: 5px;
    font-size: 11px; font-weight: 600; color: #fff;
    background: rgba(255,255,255,0.16); border: 0.5px solid rgba(255,255,255,0.4);
    backdrop-filter: blur(4px); padding: 6px 10px; border-radius: 999px; text-decoration: none;
    opacity: 0; transform: translateY(6px);
    transition: opacity 0.25s ease, transform 0.25s ease, background 0.15s ease;
  }
  .edit-feature:hover .visit-source { opacity: 1; transform: translateY(0); }
  .edit-feature .visit-source:hover { background: rgba(255,255,255,0.3); }
  .edit-feature .visit-source i { font-size: 13px; }
  @media (max-width: 959px) {
    .maker-grid { grid-template-columns: repeat(4, 1fr); }
    .edit-feature { grid-column: span 2; }
  }
  @media (max-width: 639px) {
    .maker-grid { grid-template-columns: repeat(2, 1fr); gap: 16px; }
    .edit-feature { grid-column: span 2; grid-row: span 1; min-height: 0; aspect-ratio: 4 / 3; }
    .edit-feature .cat-label { font-size: 20px; }
  }
  /* Hover never fires on touch: show the product and the maker link always
     (same breakpoint as the homepage tiles, plus any touch-only device). */
  @media (max-width: 760px), (hover: none) {
    .edit-feature .cat-details, .edit-feature .visit-source { opacity: 1; transform: none; pointer-events: auto; }
  }
"""
)

def _edit_hero_product(theme, cards_to_render):
    """
    The same real product a visitor sees first on the edit's own page -
    its hand-picked carousel's first entry when the theme has one (a
    human already chose it as the best representative shot), otherwise
    the first product in the grid itself, in the same order
    render_themed_edit_page's own grid uses. Returns the full product
    dict (not just its image), so a caller can also credit/link to the
    real source - see _edit_banner_slide_html's own docstring for why
    that matters.
    """
    picks = gte._resolve_carousel_picks(theme, cards_to_render)
    if picks:
        return picks[0]
    return cards_to_render[0] if cards_to_render else None


def _edit_card_image(theme, cards_to_render):
    product = _edit_hero_product(theme, cards_to_render)
    return product.get("image_url", "") if product else ""


def _edit_banner_slide_html(theme, product):
    """
    Links straight to the real product's own source (brand's homepage
    if check_links.py flagged the product page dead, same fallback
    every other card on the site already uses) - not to this Edit's own
    page - and credits the real brand/product by name on the image
    itself, matching the exact "link back to source" convention every
    other carousel/card on Formground already follows (see
    _carousel_slide_html). Displaying a maker's photo without crediting
    and linking to them is exactly the thing this site's whole "every
    result links straight to the maker's own site" promise exists to
    avoid - the hub banner doesn't get an exception just because it's a
    bigger, more prominent placement. The theme itself (title, slug)
    stays reachable via this same edit's own tile in the grid below,
    not lost by pointing the banner elsewhere.
    """
    url = product["brand_url"] if product.get("link_dead") else product["product_url"]
    return (
        f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">'
        f'<img src="{html.escape(product["image_url"])}" alt="{html.escape(product["product_name"])} by {html.escape(product["brand"])}" loading="lazy">'
        '<div class="banner-slide-content">'
        f'<span class="edit-banner-eyebrow">{html.escape(theme["title"])}</span>'
        f'<span class="edit-banner-title">{html.escape(product["product_name"])}</span>'
        f'<span class="edit-banner-brand">{html.escape(product["brand"])}</span>'
        "</div>"
        "</a>"
    )


EDITS_FILTER_JS = """
  (function () {
    var filterInput = document.getElementById("directory-filter");
    function applyFilter(q) {
      q = q.trim().toLowerCase();
      document.querySelectorAll(".maker-card").forEach(function (card) {
        card.hidden = !(!q || card.textContent.toLowerCase().includes(q));
      });
    }
    filterInput.addEventListener("input", function (e) { applyFilter(e.target.value); });
  })();
"""


def _edit_meta_text(count, brand_count):
    return (
        f"{count:,} piece{'' if count == 1 else 's'} "
        f"&middot; {brand_count} maker{'' if brand_count == 1 else 's'}"
    )


# Explicit display order, built up one step at a time per the user's
# own request (2026-09-30: "let's do one step at a time"). Step 1:
# "Place Portable Lamps on the first row, left aligned" - moved it to
# the very front. Step 2: "Move Round Coffee Tables to sit under
# Ceiling Lamps" - landed it in row 2's 3rd column, directly under
# Ceiling Lamps in row 1. Step 3: "Move Round Coffee Tables up one row.
# Don't move anything else" - swaps its list position with Ceiling
# Lamps's (the only way to move it up one row while staying in the same
# column) rather than re-deriving the whole order again; everything
# else keeps the exact same cell it already had - confirmed by hand:
# swapping two same-cell-width entries in this list only ever changes
# where those two land, since every entry between and after them keeps
# the same cumulative cell count either way.
# Display order (2026-09-30) - plain alphabetical by default. With the
# fixed 2-column grid below (no auto-fit, no spans), item N in this
# list always lands at row ceil(N/2), column (N odd ? 1 : 2), at every
# viewport - so moving an edit to a specific row/column later is just
# reordering this list, no cell-math or reflow guessing required.
# One edit can be FEATURED on the hub (2026-10-03, user's idea): it fills half
# the grid (3 columns x 2 rows at six across) and always comes first, the other
# edits follow alphabetically around it. Still a fixed grid with explicit
# spans, so every position stays deterministic. None = no featured edit.
FEATURED_EDIT_SLUG = "round-coffee-tables"


def _edits_sort_key(entry):
    return entry[0]["title"].lower()


def render_edits_index(themes_data):
    """
    themes_data is a list of (theme, product_count, brand_count, image,
    hero_product) tuples, one per THEMES entry, already computed by
    generate() below.

    One plain, FIXED 2-column grid, every edit the same size (2026-09-30,
    user: "i don't want a bento on the page, but it would be good to
    have a fixed structure of columns and rows... to work within") -
    reuses the same .maker-card markup makers.html already defines in
    PAGE_CSS (real editorial count in place of a maker's country/
    category tags - an Edit isn't a "brand is the minimum unit of
    inclusion" listing the way makers.html is, so showing real depth
    here doesn't undercut that principle the way it would there), but
    NOT that file's own auto-fit .maker-grid track sizing - see
    .maker-grid's own CSS comment for why a fixed column count was the
    actual fix needed, not another round of position tweaks.
    """
    ordered = sorted(themes_data, key=_edits_sort_key)
    # featured edit first, the rest keep their alphabetical order
    ordered.sort(key=lambda entry: entry[0]["slug"] != FEATURED_EDIT_SLUG)

    tile_items = ""
    for theme, count, brand_count, image, hero_product in ordered:
        image_tag = (
            f'<img src="{html.escape(image)}" alt="{html.escape(theme["title"])}" loading="lazy">'
            if image else ""
        )
        if theme["slug"] == FEATURED_EDIT_SLUG and hero_product is not None:
            # the real product pictured, credited and linked to its maker
            src = hero_product["brand_url"] if hero_product.get("link_dead") else hero_product["product_url"]
            tile_items += f"""
      <figure class="edit-feature">
        <a class="cat-link" href="/{theme['slug']}.html" aria-label="Browse {html.escape(theme['title'])}"></a>
        {image_tag.replace(html.escape(theme['title']), html.escape(hero_product['product_name']) + ' by ' + html.escape(hero_product['brand']), 1)}
        <p class="cat-label">{html.escape(theme['title'])}<small>{_edit_meta_text(count, brand_count)}</small></p>
        <div class="cat-details">
          <span class="product-name">{html.escape(hero_product['product_name'])}</span>
          <span class="product-maker">{html.escape(hero_product['brand'])}</span>
        </div>
        <a class="visit-source" href="{html.escape(src)}" target="_blank" rel="noopener noreferrer">Visit site <i class="ti ti-arrow-up-right" aria-hidden="true"></i></a>
      </figure>"""
            continue
        tile_items += f"""
      <a class="maker-card" href="/{theme['slug']}.html">
        <div class="maker-card-hero">{image_tag}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(theme['title'])}</span>
          <span class="maker-country">{_edit_meta_text(count, brand_count)}</span>
        </div>
      </a>"""
    tile_grid_html = f'<div class="maker-grid">{tile_items}\n  </div>' if tile_items else ""

    by_slug = {
        theme["slug"]: (theme, hero_product)
        for theme, _count, _brand_count, _image, hero_product in themes_data
    }
    banner_slides = [
        _edit_banner_slide_html(*by_slug[slug])
        for slug in BANNER_SLUGS
        if slug in by_slug and by_slug[slug][1] is not None
    ]
    banner_html = render_banner_carousel(banner_slides)

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
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&display=swap" rel="stylesheet">
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
<style>{EDITS_PAGE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("edits")}
</header>
<main style="max-width:1160px;">
  <div class="edits-hero">
    <h1>Edits</h1>
    <p class="edits-preamble">{html.escape("Curated, editorial groupings of real work")}<br>{html.escape("from Formground's makers - browse every Edit, gathered in one place.")}</p>
  </div>
{banner_html}
  {directory_filter_html("Filter edits by name…", "Edits")}
  {tile_grid_html}
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
{BANNER_CAROUSEL_JS}
{EDITS_FILTER_JS}</script>
<script>{CARD_CLICK_TRACKING_JS}</script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def generate():
    themes_data = []
    for theme in gte.THEMES:
        products = theme["fetch"]()
        cards_to_render, _ = gte.capped_edit_cards(theme, products)
        brand_count = len({p["brand"] for p in cards_to_render})
        hero_product = _edit_hero_product(theme, cards_to_render)
        image = hero_product.get("image_url", "") if hero_product else ""
        themes_data.append((theme, len(cards_to_render), brand_count, image, hero_product))

    (DOCS_DIR / "edits.html").write_text(render_edits_index(themes_data))
    append_to_sitemap(["edits"])
    print(f"Generated edits.html ({len(themes_data)} edits).")


if __name__ == "__main__":
    generate()
