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

WORK / MAKERS CHIPS: every THEMES entry has an implicit "type" - "work"
(a product/category grouping - every real Edit today) unless a THEMES
entry explicitly sets "type": "makers" (a maker-focused editorial
grouping - none exist yet, per the user's own sequencing: "build the
page and then we add Makers edits afterwards"). Selecting "Makers"
today correctly shows nothing but a real, honest empty-state message
rather than a blank grid - the empty state is expected, not a bug,
until a real first Makers-type entry exists (same "genuinely empty is
not a bug" convention as new.html/for-creators.html's own empty
states). Written as its own small script rather than reusing
DIRECTORY_FILTER_JS's tier-filter logic (see generate_brand_pages.py) -
that mechanism is named/shaped around brand tier specifically; this
page's search box still reuses that module's directory_filter_html for
the input markup, just not its paired filtering JS.

Same shared search box as makers.html/architects.html/designers.html
(directory_filter_html) - "the edits page itself could use the same
search box as we have across the site" (user's own words) - filtering
here is a plain client-side text match against each card's own title/
meta line, combined with the active Work/Makers chip.

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
from generate_theme_landing_pages import _group_color_variants, append_to_sitemap  # noqa: E402
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
  .edits-hero { text-align: center; margin: 0 0 32px; }
  .edits-hero h1 {
    font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 44px;
    letter-spacing: 0.01em; margin: 0 0 16px;
  }
  .edits-preamble {
    font-size: 15px; color: var(--text-secondary);
    max-width: 580px; margin: 0 auto; line-height: 1.6;
  }
  @media (max-width: 640px) {
    .edits-hero h1 { font-size: 30px; }
  }

  #edits-empty-state {
    display: none; text-align: center; font-size: 14px; color: var(--text-muted);
    padding: 60px 20px;
  }

  /* Magazine-cover hero grid (2026-09-30, user: "apply some of the
     homepage layout and style... so it reads more like a magazine" -
     "results page is what it is, Edits is different") - the exact same
     asymmetric 4-tile proportions as the homepage's own
     .category-grid/.tile-houses etc (one tall lead tile, two smaller
     top-right, one wide bottom-right), which happens to fit today's
     real count of 4 edits exactly. Renamed rather than reusing those
     class names directly since this page has its own stylesheet, not
     index.html's. Only the first 4 (biggest by real product count) go
     in the fixed grid; any beyond that render in the plain overflow
     grid below (see render_edits_index) rather than forcing a 5th slot
     into a layout tuned for exactly four. */
  .edits-tile-grid {
    display: grid; grid-template-columns: 1.4fr 1fr 1fr; grid-template-rows: 1fr 1fr;
    gap: 20px; height: 560px; margin: 0 0 40px;
  }
  .edits-tile-1 { grid-column: 1; grid-row: 1 / 3; }
  .edits-tile-2 { grid-column: 2; grid-row: 1; }
  .edits-tile-3 { grid-column: 3; grid-row: 1; }
  .edits-tile-4 { grid-column: 2 / 4; grid-row: 2; }

  /* Same image-fills-tile, hover-reveal-details treatment as the
     homepage's own .cat-tile/.cat-label/.cat-details - simpler here
     since an Edit tile only ever needs the one internal link (no
     competing external "visit source" link the way a maker's own
     homepage teaser does), so the whole tile is just one <a>, no
     invisible full-bleed overlay link needed. */
  .edit-tile {
    position: relative; display: block; overflow: hidden; text-decoration: none; color: inherit;
    border: 0.5px solid var(--border); background: var(--surface-1); height: 100%;
  }
  .edit-tile img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.4s ease; }
  .edit-tile:hover img { transform: scale(1.03); }
  .edit-tile-label {
    position: absolute; top: 16px; left: 16px; z-index: 2;
    font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 18px;
    color: #fff; letter-spacing: -0.005em; margin: 0; pointer-events: none;
  }
  .edit-tile-details {
    position: absolute; left: 0; right: 0; bottom: 0; z-index: 2;
    padding: 28px 16px 14px;
    background: linear-gradient(to top, rgba(0,0,0,0.68), rgba(0,0,0,0));
    color: #fff; font-size: 12px;
    opacity: 0; transform: translateY(6px);
    transition: opacity 0.25s ease, transform 0.25s ease;
    pointer-events: none;
  }
  .edit-tile:hover .edit-tile-details { opacity: 1; transform: translateY(0); }

  .edits-overflow-heading {
    font-size: 13px; font-weight: 600; color: var(--text-secondary);
    text-align: center; margin: 0 0 20px;
  }

  @media (max-width: 760px) {
    .edits-tile-grid { display: flex; flex-direction: column; height: auto; gap: 16px; }
    .edit-tile { aspect-ratio: 4 / 3; }
    .edit-tile-details { opacity: 1; transform: none; }
  }
"""
)

# Only the leading N real edits (by product count, biggest first) get a
# slot in the fixed 4-position magazine grid - see .edits-tile-grid's
# own comment for why 4 specifically. Any beyond this render in a plain
# overflow grid underneath instead of forcing a 5th tile into a layout
# tuned for four.
FEATURED_TILE_COUNT = 4


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


def _edit_banner_slide_html(theme, image):
    return (
        f'<a href="/{theme["slug"]}.html">'
        f'<img src="{html.escape(image)}" alt="{html.escape(theme["title"])}" loading="lazy">'
        '<div class="banner-slide-content">'
        '<span class="edit-banner-eyebrow">Themed Edit</span>'
        f'<span class="edit-banner-title">{html.escape(theme["title"])}</span>'
        "</div>"
        "</a>"
    )


EDITS_FILTER_JS = """
  (function () {
    var filterInput = document.getElementById("directory-filter");
    var typeButtons = document.querySelectorAll(".filter-chip[data-edit-type]");
    var emptyState = document.getElementById("edits-empty-state");
    var activeType = null;
    function applyFilter(q) {
      q = q.trim().toLowerCase();
      var visibleCount = 0;
      // Covers both the featured magazine-grid tiles and any overflow
      // .maker-card entries beyond it - same [data-edit-type] attribute
      // either way, so one selector filters both without caring which
      // shape a given edit's card happens to be.
      document.querySelectorAll("[data-edit-type]").forEach(function (card) {
        var textMatch = !q || card.textContent.toLowerCase().includes(q);
        var typeMatch = !activeType || card.dataset.editType === activeType;
        var visible = textMatch && typeMatch;
        card.hidden = !visible;
        if (visible) visibleCount++;
      });
      // Only worth a dedicated empty-state message for the Makers
      // chip's real "nothing here yet" case (see this file's own
      // docstring) - a text search that happens to match nothing
      // already has no separate message here, same as makers.html.
      emptyState.style.display = (visibleCount === 0 && activeType === "makers") ? "block" : "none";
    }
    filterInput.addEventListener("input", function (e) { applyFilter(e.target.value); });
    typeButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var type = btn.dataset.editType;
        if (activeType === type) {
          activeType = null;
          btn.classList.remove("active");
        } else {
          activeType = type;
          typeButtons.forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
        }
        applyFilter(filterInput.value);
      });
    });
  })();
"""


def _edit_meta_text(count, brand_count):
    return (
        f"{count:,} piece{'' if count == 1 else 's'} "
        f"&middot; {brand_count} maker{'' if brand_count == 1 else 's'}"
    )


def _edit_tile_html(theme, count, brand_count, image, position_class):
    edit_type = theme.get("type", "work")
    image_tag = (
        f'<img src="{html.escape(image)}" alt="{html.escape(theme["title"])}" loading="lazy">'
        if image else ""
    )
    return f"""
    <a class="edit-tile {position_class}" href="/{theme['slug']}.html" data-edit-type="{edit_type}">
      {image_tag}
      <p class="edit-tile-label">{html.escape(theme['title'])}</p>
      <div class="edit-tile-details">{_edit_meta_text(count, brand_count)}</div>
    </a>"""


def render_edits_index(themes_data):
    """
    themes_data is a list of (theme, product_count, brand_count, image)
    tuples, one per THEMES entry, already computed by generate() below.

    The FEATURED_TILE_COUNT biggest real edits (by product count) lead
    in the fixed magazine-style bento grid (see .edits-tile-grid) - any
    beyond that render in a plain overflow grid underneath, reusing the
    same .maker-card/.maker-grid markup makers.html already defines in
    PAGE_CSS (same card shape, a real editorial count in place of a
    maker's country/category tags - an Edit isn't a "brand is the
    minimum unit of inclusion" listing the way makers.html is, so
    showing real depth here doesn't undercut that principle the way it
    would there). Today there are only 4 real edits total, so the
    overflow section is empty and simply doesn't render.
    """
    by_count_desc = sorted(themes_data, key=lambda t: t[1], reverse=True)
    featured = by_count_desc[:FEATURED_TILE_COUNT]
    overflow = sorted(by_count_desc[FEATURED_TILE_COUNT:], key=lambda t: t[0]["title"].lower())

    tile_html = "".join(
        _edit_tile_html(theme, count, brand_count, image, f"edits-tile-{i + 1}")
        for i, (theme, count, brand_count, image) in enumerate(featured)
    )
    tile_grid_html = f'<div class="edits-tile-grid">{tile_html}\n    </div>' if tile_html else ""

    overflow_items = ""
    for theme, count, brand_count, image in overflow:
        edit_type = theme.get("type", "work")
        image_tag = (
            f'<img src="{html.escape(image)}" alt="{html.escape(theme["title"])}" loading="lazy">'
            if image else ""
        )
        overflow_items += f"""
      <a class="maker-card" href="/{theme['slug']}.html" data-edit-type="{edit_type}">
        <div class="maker-card-hero">{image_tag}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(theme['title'])}</span>
          <span class="maker-country">{_edit_meta_text(count, brand_count)}</span>
        </div>
      </a>"""
    overflow_html = (
        f'<p class="edits-overflow-heading">More Edits</p>\n  <div class="maker-grid">{overflow_items}\n  </div>'
        if overflow_items else ""
    )

    by_slug = {theme["slug"]: (theme, image) for theme, _count, _brand_count, image in themes_data}
    banner_slides = [
        _edit_banner_slide_html(*by_slug[slug])
        for slug in BANNER_SLUGS
        if slug in by_slug and by_slug[slug][1]
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
{site_nav_html()}
</header>
<main style="max-width:1160px;">
  <div class="edits-hero">
    <h1>Edits</h1>
    <p class="edits-preamble">{html.escape("Curated, editorial groupings of real work")}<br>{html.escape("from Formground's makers - browse every Edit, gathered in one place.")}</p>
  </div>
{banner_html}
  {directory_filter_html("Filter edits by name…", "Edits")}
  <div class="tier-filters">
    <button type="button" class="filter-chip" data-edit-type="work">Work</button>
    <button type="button" class="filter-chip" data-edit-type="makers">Makers</button>
  </div>
  {tile_grid_html}
  {overflow_html}
  <p id="edits-empty-state">No maker-focused edits yet - check back soon.</p>
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
        cards_to_render, _ = _group_color_variants(products)
        brand_count = len({p["brand"] for p in cards_to_render})
        image = _edit_card_image(theme, cards_to_render)
        themes_data.append((theme, len(cards_to_render), brand_count, image))

    (DOCS_DIR / "edits.html").write_text(render_edits_index(themes_data))
    append_to_sitemap(["edits"])
    print(f"Generated edits.html ({len(themes_data)} edits).")


if __name__ == "__main__":
    generate()
