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
import creator_texts  # noqa: E402
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

# Hub-tile crop override per hero photo (object-position). The default is a centred crop; Sizar Alexis' Lahmu
# vase stands in the lower half of a portrait photo, so a centred square cut off its base (2026-10-06).
# A different photo for an Edit's hub tile than the one its own page uses (2026-10-11, user: better crop): the IO lamp
# close-up is cut off in a square, so the tile shows the whole lamp in its room, with the crop moved onto it.
HUB_TILE_IMAGE = {
    "table-lamps": "https://images.squarespace-cdn.com/content/v1/57b3208aff7c50dc3b5aef6a/1701278906295-AT1K9TVXW1EH3QRN2K4H/HannahBigeleisen_Lamp_1022_LizClayman_05.jpg?format=1000w",
}

TILE_OBJECT_POSITION = {
    "https://images.squarespace-cdn.com/content/v1/57b3208aff7c50dc3b5aef6a/1701278906295-AT1K9TVXW1EH3QRN2K4H/HannahBigeleisen_Lamp_1022_LizClayman_05.jpg?format=1000w": "50% 20%",
    "https://sizaralexis.se/wp-content/uploads/2023/06/G6A2148-scaled.jpg": "50% 100%",
    # Kalon's Bough Table Round stands left of centre in a wide photo: the square tile's window is moved onto it (2026-10-19)
    "https://images.kalonstudios.com/cb:EU5d~4b753/w:900/h:900/q:90/f:best/ig:avif/https://kalonstudios.com/wp-content/uploads/2022/06/Bough-Table-Round-Hero-1.jpg": "8% 50%",
}

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
  .edits-section-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin: 34px 0 14px; }
  /* Edit tiles (2026-10-11, user: the grey shading behind the title was not as crisp as the rest of the site): the
     home page's own row pattern - the title above (14px / 600) with the kind on the right in muted grey, then a clean
     photo with no text or shading on it. On desktop, hovering the photo shows a small light credit pill (the pictured
     item, linked to its maker); on touch screens and phones it is not shown (the item is credited inside the Edit). */
  .maker-grid { row-gap: 30px; }
  .edit-feature { grid-column: span 2; position: relative; margin: 0; }
  .edit-feature .edit-link { display: block; color: inherit; text-decoration: none; }
  .edit-feature .edit-row { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin: 0 0 12px; }
  .edit-feature .edit-title { font-size: 14px; font-weight: 600; color: var(--text-primary); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .edit-feature .edit-kind { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
  .edit-feature .edit-link:hover .edit-title { text-decoration: underline; }
  .edit-feature .edit-photo { display: block; aspect-ratio: 1 / 1; position: relative; overflow: hidden;
    border: 0.5px solid var(--border); background: var(--surface-1); }
  .edit-feature .edit-photo img.contain-fit { object-fit: contain; }
  .edit-feature .edit-photo img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.4s ease; }
  .edit-feature:hover .edit-photo img { transform: scale(1.03); }
  .edit-feature .visit-source {
    position: absolute; bottom: 12px; right: 12px; z-index: 2; max-width: calc(100% - 24px);
    display: flex; align-items: center; gap: 5px; overflow: hidden; white-space: nowrap;
    font-size: 12px; font-weight: 600; color: var(--text-primary); background: rgba(255,255,255,0.94);
    padding: 6px 11px; border-radius: 999px; text-decoration: none; border: 0.5px solid var(--border);
    opacity: 0; transform: translateY(4px); pointer-events: none;
    transition: opacity 0.2s ease, transform 0.2s ease;
  }
  .edit-feature .visit-source span { overflow: hidden; text-overflow: ellipsis; }
  .edit-feature:hover .visit-source { opacity: 1; transform: translateY(0); pointer-events: auto; }
  .edit-feature .visit-source i { font-size: 13px; flex: none; }
  @media (max-width: 959px) {
    .maker-grid { grid-template-columns: repeat(4, 1fr); }
    .edit-feature { grid-column: span 2; }  /* 2 across on the 4-column tier */
  }
  @media (max-width: 639px) {
    .maker-grid { grid-template-columns: repeat(2, 1fr); gap: 24px 16px; }
    .edit-feature { grid-column: span 2; }
    .edit-feature .edit-photo { aspect-ratio: 4 / 3; }
  }
  /* no hover on touch: the credit pill is not shown there (nothing is laid over the photo on a phone) */
  @media (max-width: 760px), (hover: none) {
    .edit-feature .visit-source { display: none; }
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
        "Editorial profiles of architects, designers and makers,<br>and curated Edits of their work.",
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


HUB_ORDER = "chronological"    # "chronological" = one stream, newest first | "sections" = Products, then In profile
EDIT_DATES_PATH = Path(__file__).parent.parent / "data" / "edit_dates.json"


def edit_date(slug):
    """The date an Edit was first published (data/edit_dates.json). An Edit not in the file yet is dated today and
    the file is updated, so the date is fixed from the first build that shows it."""
    import datetime
    import json
    dates = json.loads(EDIT_DATES_PATH.read_text()) if EDIT_DATES_PATH.exists() else {}
    if slug not in dates:
        dates[slug] = datetime.date.today().isoformat()
        EDIT_DATES_PATH.write_text(json.dumps(dates, indent=1, sort_keys=True) + "\n")
    return dates[slug]


def theme_category(theme):
    """The site's own umbrella category for a themed Edit's product type (Furniture, Lighting, Ceramics or Objects),
    from the same keyword rules that sort makers' pieces on the Makers page."""
    from generate_brand_pages import _umbrellas_for_product
    umbrellas = _umbrellas_for_product({"category": theme["title"], "product_name": theme["title"]})
    return sorted(umbrellas, key=lambda u: (u != "Furniture", u != "Lighting", u))[0]


def render_edits_index(themes_data, order=None):
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
    order = order or HUB_ORDER
    ordered = sorted(themes_data, key=_edits_sort_key)
    # featured edit first, the rest keep their alphabetical order
    ordered.sort(key=lambda entry: entry[0]["slug"] != FEATURED_EDIT_SLUG)

    themed_tiles = []     # (date, sort title, html) - one tile per themed (product) Edit
    for theme, count, brand_count, image, hero_product in ordered:
        image = HUB_TILE_IMAGE.get(theme["slug"], image)
        # every edit is the same tile: 2 columns wide, 2 rows tall of the 6-column grid (a 373px square at
        # full width), photo filling it, the Edit's title on it, the pictured product on hover
        image_alt = (f"{hero_product['product_name']} by {hero_product['brand']}" if hero_product is not None
                     else theme["title"])
        # a hero whose subject sits low in a portrait photo is cropped from the bottom, not the middle
        pos = TILE_OBJECT_POSITION.get(image)
        pos_attr = f' style="object-position:{pos}"' if pos else ""
        image_tag = (
            f'<img src="{html.escape(sized(image, TILE))}" alt="{html.escape(image_alt)}"{pos_attr} loading="lazy">'
            if image else ""
        )
        details = ""
        if hero_product is not None:
            # the real product pictured, credited and linked to its maker (a small pill, on hover)
            src = hero_product["brand_url"] if hero_product.get("link_dead") else hero_product["product_url"]
            details = f"""
        <a class="visit-source" href="{html.escape(src)}" target="_blank" rel="noopener noreferrer"><span>{html.escape(hero_product['product_name'])} &middot; {html.escape(hero_product['brand'])}</span> <i class="ti ti-arrow-up-right" aria-hidden="true"></i></a>"""
        themed_tiles.append((edit_date(theme["slug"]), theme["title"], f"""
      <figure class="edit-feature">
        <a class="edit-link" href="/edits/{theme['slug']}.html" aria-label="Browse {html.escape(theme['title'])}">
          <span class="edit-row"><span class="edit-title">{html.escape(theme['title'])}</span><span class="edit-kind">{theme_category(theme)}</span></span>
          <span class="edit-photo">{image_tag}</span>
        </a>{details}
      </figure>"""))
    # Profile Edits ("In profile: <name>", see generate_profile_edits.py). Every tile in the hub has the same two lines:
    # the title (what the Edit is about) and a small label under it - the site's own category for a themed Edit
    # (Furniture / Lighting / Ceramics / Objects), "Maker" / "Designer" / "Architect" for a profile - and the same hover
    # caption: the pictured item, credited and linked to its maker.
    import json as _json
    import sqlite3 as _sqlite3
    import generate_profile_edits as gpe
    houses = _json.loads((Path(__file__).parent.parent / "data" / "houses.json").read_text())
    houses_by_image = {h["image"]: h for h in houses if h.get("image")}
    conn = _sqlite3.connect(gpe.DB_PATH)
    conn.row_factory = _sqlite3.Row
    profile_tiles = []
    for entry in creator_texts.load().values():
        edit = entry["edit"]
        item = gpe.hero_item(entry, houses_by_image, conn)
        # a photo that would be cropped badly is shown whole on its own background (edit.card_bg, see check_image_fit.py)
        bg = edit.get("card_bg")
        photo_style = f' style="background:{html.escape(bg)}"' if bg else ""
        img_class = ' class="contain-fit"' if bg else ""
        details = ""
        if item:
            name, credit, link = item
            details = f"""
        <a class="visit-source" href="{html.escape(link)}" target="_blank" rel="noopener noreferrer"><span>{html.escape(name)} &middot; {html.escape(credit)}</span> <i class="ti ti-arrow-up-right" aria-hidden="true"></i></a>"""
        profile_tiles.append((entry.get("publish") or edit_date(edit["slug"]), entry["name"], f"""
      <figure class="edit-feature">
        <a class="edit-link" href="/edits/{edit['slug']}.html" aria-label="In profile: {html.escape(entry['name'])}">
          <span class="edit-row"><span class="edit-title">{html.escape(entry['name'])}</span><span class="edit-kind">{creator_texts.KIND[entry['group']]}</span></span>
          <span class="edit-photo"{photo_style}><img{img_class} src="{html.escape(sized(edit['hero'], TILE))}" alt="{html.escape(entry['name'])}" loading="lazy"></span>
        </a>{details}
      </figure>"""))
    conn.close()

    # Look Edits ("Warm minimal living room", see generate_look_pages.py): one clean photo of one piece on the tile, the
    # piece credited and linked to its maker on hover, like every other tile; the label is the kind of room.
    import generate_look_pages as glp
    lconn = _sqlite3.connect(gpe.DB_PATH)
    lconn.row_factory = _sqlite3.Row
    for look in glp.load():
        item = glp.hub_item(look, lconn)
        if not item or len(glp.resolve(look, lconn)) < glp.MIN_PIECES:
            continue
        image, pos, (pname, pbrand, plink) = item
        pos_attr = f' style="object-position:{pos}"' if pos else ""
        themed_tiles.append((edit_date(look["slug"]), look["title"], f"""
      <figure class="edit-feature">
        <a class="edit-link" href="/edits/{look['slug']}.html" aria-label="{html.escape(look['title'])}">
          <span class="edit-row"><span class="edit-title">{html.escape(look['title'])}</span><span class="edit-kind">{html.escape(look['kind'])}</span></span>
          <span class="edit-photo"><img src="{html.escape(sized(image, TILE))}" alt="{html.escape(pname)} by {html.escape(pbrand)}"{pos_attr} loading="lazy"></span>
        </a>
        <a class="visit-source" href="{html.escape(plink)}" target="_blank" rel="noopener noreferrer"><span>{html.escape(pname)} &middot; {html.escape(pbrand)}</span> <i class="ti ti-arrow-up-right" aria-hidden="true"></i></a>
      </figure>"""))
    lconn.close()

    def grid(tiles):
        return f'<div class="maker-grid">{"".join(t[2] for t in tiles)}\n  </div>' if tiles else ""

    if order == "sections":
        # two headed sections: the themed Edits (featured first, then alphabetical) and the profiles, newest first
        profile_tiles.sort(key=lambda t: (t[0], t[1].lower()), reverse=False)
        profile_tiles.sort(key=lambda t: t[0], reverse=True)
        tile_grid_html = (f'<h2 class="edits-section-title">Products</h2>\n  {grid(themed_tiles)}\n'
                          f'  <h2 class="edits-section-title">In profile</h2>\n  {grid(profile_tiles)}')
    else:
        # one stream, newest first (ties alphabetical by title)
        every = sorted(themed_tiles + profile_tiles, key=lambda t: t[1].lower())
        every.sort(key=lambda t: t[0], reverse=True)
        tile_grid_html = grid(every)

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
    <p class="edits-preamble">{html.escape("Editorial profiles of architects, designers and makers,")}<br>{html.escape("and curated Edits of their work.")}</p>
  </div>
"""

    description = "Editorial profiles of architects, designers and makers, and curated Edits of their work."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Edits: curated picks from makers — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{SITE_URL}/edits.html">
<meta property="og:type" content="website">
<meta property="og:title" content="Edits: curated picks from makers — Formground">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{SITE_URL}/edits.html">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Edits: curated picks from makers — Formground">
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
