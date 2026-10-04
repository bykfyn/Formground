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
editorial" - a banner, a strong header, a centered preamble). The banner
was first built on the Promotions carousel (text laid over the photo); on
2026-10-04 it became the same shape as every other banner on the site -
title row above, clean photo, product + maker below (.edits-banner-*) -
so navigating between the homepage, this hub and each Edit page reads as
one pattern.

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
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_URL,
    directory_filter_html,
    site_nav_html,
)
from generate_theme_landing_pages import append_to_sitemap  # noqa: E402
import generate_themed_edit_pages as gte  # noqa: E402
from image_sizes import CARD, HERO, TILE, sized  # noqa: E402
import image_fit  # noqa: E402
from site_assets import ICONS_CSS  # noqa: E402

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

# Layout of the hub's top block (2026-10-04, a trial the user asked for):
#   "masthead" - the banner photo IS the page header: "EDITS" and the preamble
#                sit on the photo, no title row above and no caption below; the
#                pictured product is credited by a small link on the photo.
#   "classic"  - "EDITS" + preamble above, then the banner as the other pages
#                have it (title row above the photo, product + maker below).
# Flip this one value to switch; nothing else changes.
HUB_LAYOUT = "masthead"
# Text colour on the masthead photo: "dark" for a light photo, "light" for a dark one.
HUB_MASTHEAD_TEXT = "dark"

EDITS_PAGE_CSS = (
    """
  /* The hub banner, in the shape of the homepage groups and each Edit page's
     banner: title row above, clean 2:1 photo (4:3 on phones), product and
     maker below. The edit's title is the header; the product is secondary. */
"""
    + gte.EDIT_MASTHEAD_CSS
    + """
  .edits-banner { margin: 0 0 28px; }
  .edits-banner-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin: 0 0 12px; }
  .edits-banner-head h2 { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 26px; line-height: 1.15; margin: 0; }
  .edits-banner-head h2 a { color: inherit; text-decoration: none; }
  .edits-banner-head h2 a:hover { text-decoration: underline; }
  .edits-banner-link { font-size: 12px; color: var(--text-accent); text-decoration: none; white-space: nowrap; }
  .edits-banner-link:hover { text-decoration: underline; }
  .edits-banner-frame { display: block; position: relative; aspect-ratio: 2/1; overflow: hidden; border: 0.5px solid var(--border); }
  .edits-banner-frame img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.4s ease; }
  .edits-banner-frame img.fit-contain { object-fit: contain; }
  .edits-banner-frame:hover img { transform: scale(1.02); }
  .edits-banner-caption { display: block; margin-top: 12px; text-decoration: none; color: inherit; }
  .edits-banner-product { display: block; font-size: 15px; font-weight: 600; }
  .edits-banner-brand { display: block; font-size: 13px; color: var(--text-secondary); margin-top: 2px; }
  .edits-banner-caption:hover .edits-banner-product { text-decoration: underline; }
  @media (max-width: 640px) {
    .edits-banner-head h2 { font-size: 22px; }
    .edits-banner-frame { aspect-ratio: 4/3; }
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
    grid-column: span 2; aspect-ratio: 1 / 1;
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
    .edit-feature { grid-column: span 2; }  /* 2 across on the 4-column tier */
  }
  @media (max-width: 639px) {
    .maker-grid { grid-template-columns: repeat(2, 1fr); gap: 16px; }
    .edit-feature { grid-column: span 2; aspect-ratio: 4 / 3; }
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


def _edit_banner_html(theme, product):
    """
    The hub's banner in the same shape as every other banner on the site
    (2026-10-04, user: "want the format to be consistent for the user when
    navigating"): a header row ABOVE the photo (the edit's title, with "See the
    edit" on the right - as the homepage's groups do), a clean photo, and the
    pictured product and its maker BELOW it (as the homepage banners and each
    Edit page's own banner do). It was the one banner with text laid over the
    photo, a leftover of the Promotions style.

    The photo and caption link straight to the real product's own source (the
    brand's homepage if check_links.py flagged the product page dead) - the
    same "link back to the maker" rule every other card follows - while the
    title and "See the edit" lead to the edit itself.
    """
    url = product["brand_url"] if product.get("link_dead") else product["product_url"]
    fit_class, fit_style = image_fit.fit_for_banner(product["image_url"])
    style = f' style="{fit_style}"' if fit_style else ""
    img_class = f' class="{fit_class}"' if fit_class else ""
    edit_url = f"/edits/{theme['slug']}.html"
    return f"""    <section class="edits-banner">
      <div class="edits-banner-head">
        <h2><a href="{edit_url}">{html.escape(theme["title"])}</a></h2>
        <a class="edits-banner-link" href="{edit_url}">See the edit &rarr;</a>
      </div>
      <a class="edits-banner-frame" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer"{style}>
        <img{img_class} src="{html.escape(sized(product["image_url"], HERO))}" alt="{html.escape(product["product_name"])} by {html.escape(product["brand"])}">
      </a>
      <a class="edits-banner-caption" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">
        <span class="edits-banner-product">{html.escape(product["product_name"])}</span>
        <span class="edits-banner-brand">{html.escape(product["brand"])}</span>
      </a>
    </section>"""


def _edits_masthead_html(product):
    """The hub header: the banner photo carries the page title ("Edits", the page's h1) and the preamble
    (shared with every Edit page: gte.masthead_html)."""
    return gte.masthead_html(
        "Edits",
        "Curated, editorial groupings of real work <br>from Formground's makers - browse every Edit, gathered in one place.",
        product, HUB_MASTHEAD_TEXT)


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
FEATURED_EDIT_SLUG = "portable-lamps"


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
        # every edit is the same tile: 2 columns wide, 2 rows tall of the 6-column grid (a 373px square at
        # full width), photo filling it, the Edit's title on it, the pictured product on hover
        image_alt = (f"{hero_product['product_name']} by {hero_product['brand']}" if hero_product is not None
                     else theme["title"])
        image_tag = (
            f'<img src="{html.escape(sized(image, TILE))}" alt="{html.escape(image_alt)}" loading="lazy">'
            if image else ""
        )
        details = ""
        if hero_product is not None:
            # the real product pictured, credited and linked to its maker
            src = hero_product["brand_url"] if hero_product.get("link_dead") else hero_product["product_url"]
            details = f"""
        <div class="cat-details">
          <span class="product-name">{html.escape(hero_product['product_name'])}</span>
          <span class="product-maker">{html.escape(hero_product['brand'])}</span>
        </div>
        <a class="visit-source" href="{html.escape(src)}" target="_blank" rel="noopener noreferrer">Visit site <i class="ti ti-arrow-up-right" aria-hidden="true"></i></a>"""
        tile_items += f"""
      <figure class="edit-feature">
        <a class="cat-link" href="/edits/{theme['slug']}.html" aria-label="Browse {html.escape(theme['title'])}"></a>
        {image_tag}
        <p class="cat-label">{html.escape(theme['title'])}</p>{details}
      </figure>"""
    tile_grid_html = f'<div class="maker-grid">{tile_items}\n  </div>' if tile_items else ""

    by_slug = {
        theme["slug"]: (theme, hero_product)
        for theme, _count, _brand_count, _image, hero_product in themes_data
    }
    # one banner (BANNER_SLUGS has a single hand-picked edit today); the first
    # listed edit that has a real hero product is shown
    banner_pick = next(
        (by_slug[slug] for slug in BANNER_SLUGS if slug in by_slug and by_slug[slug][1] is not None),
        None,
    )
    masthead = HUB_LAYOUT == "masthead" and banner_pick is not None
    banner_html = (
        _edits_masthead_html(banner_pick[1]) if masthead
        else (_edit_banner_html(*banner_pick) if banner_pick else "")
    )
    classic_header = "" if masthead else f"""  <div class="edits-hero">
    <h1>Edits</h1>
    <p class="edits-preamble">{html.escape("Curated, editorial groupings of real work")}<br>{html.escape("from Formground's makers - browse every Edit, gathered in one place.")}</p>
  </div>
"""

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
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}</style>
<style>{EDITS_PAGE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("edits")}
</header>
<main style="max-width:1160px;">
{classic_header}{banner_html}
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
        piece_count, brand_count = gte.edit_totals(theme, cards_to_render)
        hero_product = _edit_hero_product(theme, cards_to_render)
        image = hero_product.get("image_url", "") if hero_product else ""
        themes_data.append((theme, piece_count, brand_count, image, hero_product))

    (DOCS_DIR / "edits.html").write_text(render_edits_index(themes_data))
    append_to_sitemap(["edits"])
    print(f"Generated edits.html ({len(themes_data)} edits).")


if __name__ == "__main__":
    generate()
