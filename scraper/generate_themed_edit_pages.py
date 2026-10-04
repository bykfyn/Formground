"""
Formground Themed Edit page generator.

WHAT THIS DOES: generates richer, editorial static pages (docs/edits/{slug}.html)
for "Themed Edits" - the curated, compound long-tail groupings shown
under the homepage's "Themed Edits" header (Wood Sofas, Round Dining
Tables, Round Coffee Tables, Scandinavian Dining Tables) - as distinct
from generate_theme_landing_pages.py's plain-grid pages for the
straightforward single-keyword categories (Floor Lamps, Table Lamps,
Vases, Ceramics, Chairs, Sofas, Coffee Tables).

WHY A SEPARATE GENERATOR: a Themed Edit is framed as "our pick," not
"here's everything" - it deserves real editorial treatment: a genuine
intro paragraph, not a one-line description, and a varied-size grid
(some tiles large, most normal) rather than a uniform card grid - "more
editorial and rich," per the user's own framing. One shared render
function (render_themed_edit_page) means adding a new theme later is
just a new THEMES entry, not a new template.

Every theme is fully query-driven from backend/query_engine.py, same
as generate_theme_landing_pages.py's pages - no theme is a hand-typed
fixed list of products. But the real match count is then capped down to
a small, consistent size (see MAX_PRODUCTS_PER_EDIT) - "it is not a
filter, it is an edit" (user, 2026-09-30): showing all 906 real
Pendant Lamps matches read as a search result, not a curated pick, and
made every edit a different length. Reuses generate_theme_landing_pages'
_group_color_variants()/COLOR_FINISH_WORDS directly rather than
duplicating the variant-grouping logic.

RUN (after generate_brand_pages.py, since it needs sitemap.xml and
appends to it):
    python3 generate_themed_edit_pages.py
"""

import html
import re
import sqlite3
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
EDITS_DIR = DOCS_DIR / "edits"     # Edit pages live under /edits/ (moved from the site root 2026-10-04)
SITEMAP_PATH = DOCS_DIR / "sitemap.xml"
BACKEND_DIR = SCRAPER_DIR.parent / "backend"

sys.path.insert(0, str(BACKEND_DIR))
import query_engine as qe  # noqa: E402
import image_fit  # noqa: E402
from redirects import write_redirect  # noqa: E402

from generate_brand_pages import (  # noqa: E402
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_NAV_HTML_EDITS,
    SITE_URL,
)
from generate_theme_landing_pages import (  # noqa: E402
    COLOR_FINISH_WORDS,
    _group_color_variants,
    append_to_sitemap,
)
from image_sizes import CARD, HERO, TILE, sized  # noqa: E402
from site_assets import ICONS_CSS, SHARE_JS, WORK_RESULTS_CSS  # noqa: E402

# "hero_image" fairness policy (2026-09-30) - the first pass at these
# only checked each theme's own top-3 auto-picked candidates, which
# skewed heavily toward whichever brand happened to have the deepest
# catalog (Pinch, then New Works DK) - the opposite of what a feature
# meant to help visibility across makers should do. Every hero_image
# below was chosen only after checking that no other real edit already
# uses that same brand, and after specifically looking past the first
# few auto-picks for a genuinely independent maker's own photo -
# "plain product photos are fine, they just need to look good" (user's
# own bar, loosened from "must be in-situ" once real independent-maker
# candidates that weren't full room scenes turned up). Each one links
# straight to its own real source (see generate_edits_page.py's
# _edit_banner_slide_html for the same rule on the hub's own banner) -
# credit and traffic go to the actual maker, not just their photo.
THEMES = [
    {
        # Replaces the old "Wood Sofas" theme (2026-09-29) - "two seater
        # sofa" is one of the locked ad keywords (see
        # project-docs/FORMGROUND_STRATEGY_28.md, kept local/private),
        # ties directly to the real seat_count search fix, and needs no
        # ad-hoc word-matching heuristic the way "wood sofa" did (no
        # clean existing definition existed for that one - see project
        # memory, themed_edit_pages_built.md). Real count: 54 products,
        # 11 brands (56 minus 2 Serax "protection cover" items excluded
        # by _is_protective_cover, added 2026-09-29).
        "slug": "two-seater-sofas",
        "title": "Two Seater Sofas",
        "fetch": lambda: qe.filter_products({"category": "sofa", "seat_count": 2}),
        "intro": (
            "A two-seater doesn't try to fill a room - it fits a reading "
            "corner, a hallway, a space a three-seater never would. The "
            "smaller scale doesn't mean smaller craft: the same joinery, "
            "the same attention to an arm or a leg, just sized for more "
            "homes. Every result links straight to the maker's own site."
        ),
        # Superseded the old hand-picked 3-product carousel (2026-09-29:
        # Boxlike/Rydal/Fly SC2) once every edit banner went static
        # (2026-09-30, user: "the edit banners can be static, no
        # carousel - looks more editorial anyway"). De La Espada was
        # picked specifically over Pinch's own excellent "Rydal sofa"
        # shot to avoid Pinch anchoring this AND Round Coffee Tables -
        # see the fairness policy comment above THEMES.
        "hero_image": ("De La Espada", "HEPBURN MODULAR 2-SEATER ARMLESS SOFA"),
    },
    {
        "slug": "round-dining-tables",
        "title": "Round Dining Tables",
        "fetch": lambda: qe.filter_products({"category": "dining table", "style_descriptors": ["round"]}),
        "intro": (
            "A round table has no head - everyone sits equally close to "
            "everyone else. What varies is the base: a single pedestal, a "
            "tripod, a cross-frame, each one a real structural answer to "
            "holding up a circular top. Every result links straight to the "
            "maker's own site."
        ),
        "exclude": {("Vaarnii", "001 Dining Table Round Files"), ("Fogia", "Supper Round Table")},
        # A real workshop shot, not a styled room - Galvin Brothers' own
        # Titan photographed in their actual UK workshop, sawdust and
        # tools included. Picked over Pinch's own "Tove dining table
        # circular" (also excellent) for the same fairness reason.
        "hero_image": ("Galvin Brothers", "Titan (Round) Dining Table"),
        "hero_label": "Titan Dining Table",
    },
    {
        "slug": "round-coffee-tables",
        "title": "Round Coffee Tables",
        "fetch": lambda: qe.filter_products({"category": "coffee table", "style_descriptors": ["round"]}),
        "intro": (
            "No corners to work around - a round coffee table sits equally "
            "well against a sofa, an armchair, or a walking path through the "
            "room. Every result links straight to the maker's own site."
        ),
        "exclude": {("Pinch", "Landry coffee table circular bronze")},
        # Testing a new standard layout (2026-09-30, user: "a strong
        # main in situ image that serves as the attraction... to see if
        # the idea works") - ONE real in-situ room photo instead of the
        # usual 3-product rotating carousel, same real Pinch piece
        # already proven to read far better than a studio shot on the
        # Edits hub banner. "exclude" above still keeps this exact item
        # out of the homepage's own separate teaser pick - unrelated to
        # this override, which bypasses the auto-pick entirely.
        "hero_image": ("Pinch", "Landry coffee table circular bronze"),
    },
    {
        "slug": "scandinavian-dining-tables",
        "title": "Scandinavian Dining Tables",
        "fetch": lambda: qe.filter_products({"category": "dining table", "countries": ["Sweden", "Denmark", "Norway"]}),
        "intro": (
            "Dining tables from Swedish, Danish, and Norwegian makers - new "
            "work by independent, living designers, not a vintage or "
            "antiques listing. Every result links straight to the maker's "
            "own site."
        ),
        "exclude": {("Audo", "Puffin Dining Table")},
        "hero_image": ("Mass Productions", "Draft Dining Table Ø700"),
    },
    # Lighting cluster (2026-09-30, user: "use lighting as the category
    # and build from that") - the locked ad-keyword research flagged
    # lighting as the strongest cluster with the deepest confirmed
    # catalog, but only Floor Lamps had a dedicated page before this.
    # Each of these four is a real, single-keyword category filter with
    # its own real depth (906/672/267/111 products respectively,
    # confirmed live) - same "no ad-hoc heuristic needed" cleanliness as
    # the seat-count-based Two Seater Sofas theme. "exclude" on Pendant/
    # Table Lamps keeps this page's own auto-picked carousel from just
    # repeating the exact same three pieces the homepage's own duo-
    # carousel teasers already show for these two categories.
    {
        "slug": "pendant-lamps",
        "title": "Pendant Lamps",
        "fetch": lambda: qe.filter_products({"category": "pendant"}),
        "intro": (
            "A pendant hangs low enough to matter - over a dining table, "
            "an island, a reading chair - doing the one thing a light "
            "recessed flush into the ceiling never can: becoming part of "
            "the room's own composition. Every result links straight to "
            "the maker's own site."
        ),
        "exclude": {
            ("In Common With", "Disc Pendant"),
            ("Danny Kaplan Studio", "Augustus Orb Pendant"),
            ("AY Illuminate", "Hyo"),
        },
        # A dramatic studio shot, not in-situ - fine per the loosened bar
        # ("plain product photos are fine, they just need to look good"),
        # and Apparatus is independent, unlike Pinch's own excellent
        # "Remu pendant light whiskey" (already ruled out - Pinch
        # anchors Round Coffee Tables).
        "hero_image": ("Apparatus", "LANTERN : 1 PENDANT"),
    },
    {
        "slug": "table-lamps",
        "title": "Table Lamps",
        "fetch": lambda: qe.filter_products({"category": "table lamp"}),
        "intro": (
            "No wiring, no ceiling box, no commitment - a table lamp asks "
            "only for a surface and a socket, then does the rest: real "
            "presence on a nightstand, a console, or a desk. Every result "
            "links straight to the maker's own site."
        ),
        "exclude": {
            ("Motarasu", "Cho Table Lamp Matcha"),
            ("In Common With", "Helena Table Lamp"),
            ("Tala", "Knuckle Table Lamp in Walnut + Sphere IV"),
        },
        # A real, moody in-situ shot (an antique desk, a folding chair,
        # real books) - H. Bigeleisen is a genuinely independent studio.
        "hero_image": ("H. Bigeleisen", "IO Brushed Brass Table Lamp"),
    },
    {
        "slug": "wall-lamps",
        "title": "Wall Lamps",
        "fetch": lambda: qe.filter_products({"category": "wall lamp"}),
        "intro": (
            "Fixed to the wall, a wall lamp gives up nothing in design for "
            "the surface it frees underneath - a nightstand with no lamp "
            "base to work around, a hallway with no room for anything "
            "else. Every result links straight to the maker's own site."
        ),
        # Louise Roe's real "Moon Lantern" (1667x2500, portrait) was tried
        # here first, but a portrait source is the wrong shape for a wide
        # banner slot no matter what aspect-ratio the box itself uses -
        # "the images are the wrong size for a banner so they are being
        # forced to do something they cannot" (user, 2026-09-30). Pinch's
        # own "Remu wall light whiskey" (2000x1430, genuinely landscape)
        # is a placeholder the user's fine with for now ("use the pinch
        # images as placeholders where relevant... they seem to work well
        # as banners") while they manually source a permanent replacement.
        "hero_image": ("Pinch", "Remu wall light whiskey"),
    },
    {
        "slug": "ceiling-lamps",
        "title": "Ceiling Lamps",
        "fetch": lambda: qe.filter_products({"category": "ceiling lamp"}),
        "intro": (
            "Not a pendant on a long drop, not a chandelier - a ceiling "
            "lamp sits close and flush, built for a room where headroom "
            "is real and every inch of it counts. Every result links "
            "straight to the maker's own site."
        ),
        # New Works DK's "Kantarell Wall & Ceiling Lamp" (595x800,
        # portrait) had the same wrong-shape-for-a-banner problem as Wall
        # Lamps' own original pick, and Pinch has no real ceiling lamp to
        # stand in here (its lighting is all Wall Lamp/Pendant/table
        # Light). Left pending rather than forcing another mismatched
        # photo in - the empty list is the documented "no banner yet"
        # state (see _resolve_carousel_picks), not an oversight.
        "carousel_picks": [],
    },
    {
        # Real, distinct filter (see _wants_portable/_product_is_portable
        # in query_engine.py, built 2026-09-29 for the cordless/
        # rechargeable lamp keyword work) - not scoped to table lamps
        # only, since the real 84-product set spans table lamps, floor-
        # adjacent "Lamp"/"Light" categories, and outdoor pieces alike;
        # the real, shared thing they have in common is no cord to plan
        # around, not which room they sit in.
        "slug": "portable-lamps",
        "title": "Portable Lamps",
        "fetch": lambda: qe.filter_products({"portable_only": True}),
        "intro": (
            "No outlet to plan around, no cord to route - a portable lamp "
            "goes wherever the evening does: a dinner table, a bath, a "
            "porch step. Every result links straight to the maker's own "
            "site."
        ),
        # Shot inside Maison Louis Carré, Alvar Aalto's real house in
        # France - In Common With is independent.
        "hero_image": ("In Common With", "Dune Portable Table Lamp"),
    },
]

CAROUSEL_SIZE = 3


# ---------------------------------------------------------------------------
# Masthead header (2026-10-04): the banner photo IS the page header - the Edit's title and intro sit on
# the photo, over the plain area at its top, with no overlay; a small pill credits and links the maker.
# Shared by the Edits hub (generate_edits_page.py) and every Edit page. See Site_Patterns.md "Page masthead".
# ---------------------------------------------------------------------------
EDIT_MASTHEAD_CSS = """
  /* Trial layout "masthead": the banner photo is the page header. */
  .edits-masthead { position: relative; aspect-ratio: 2/1; overflow: hidden; margin: 0 0 28px; border: 0.5px solid var(--border); background: var(--surface-1); }
  .edits-masthead img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }
  .edits-masthead img.fit-contain { object-fit: contain; }
  /* No overlay on the photo (2026-10-04, user: "keep the banner image natural
     without the grey shading"): legibility comes from the text colour and from
     placing it over the plain wall at the top of THIS photo. Dark text suits a
     light photo; if the banner image changes to a dark one, set
     HUB_MASTHEAD_TEXT = "light". */
  .edits-masthead-copy { position: absolute; left: 0; right: 0; top: 0; z-index: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; text-align: center; padding: 4.5% 28px 0; color: var(--text-primary); }
  .edits-masthead--light .edits-masthead-copy { color: #fff; }
  .edits-masthead-copy h1 { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 60px; line-height: 1.05; letter-spacing: 0.01em; text-transform: uppercase; margin: 0 0 14px; }
  .edits-masthead-copy p { font-size: 17px; line-height: 1.55; max-width: 620px; margin: 0; color: var(--text-primary); font-weight: 500; }
  .edits-masthead--light .edits-masthead-copy p { color: rgba(255,255,255,0.94); }
  /* an Edit's intro is longer than the hub's two lines: a wider measure keeps it to three */
  .edits-masthead--wide .edits-masthead-copy p { max-width: 780px; font-size: 16px; }
  .edits-masthead--wide .edits-masthead-copy h1 { font-size: 52px; margin-bottom: 12px; }
  /* "Edits" sits inside the photo as a small label above the title, linking back to the hub */
  .edits-masthead-kicker { font-size: 12px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: inherit; text-decoration: none; margin: 0 0 10px; opacity: 0.8; }
  .edits-masthead-kicker:hover { opacity: 1; text-decoration: underline; }
  @media (max-width: 640px) { .edits-masthead--wide .edits-masthead-copy h1 { font-size: 32px; } .edits-masthead--wide .edits-masthead-copy p { font-size: 14px; } }
  .edits-masthead-credit { position: absolute; right: 12px; bottom: 12px; z-index: 2; display: inline-flex; align-items: center; gap: 5px;
    font-size: 11px; font-weight: 600; color: var(--text-primary); text-decoration: none; padding: 6px 10px; border-radius: 999px;
    background: rgba(255,255,255,0.78); border: 0.5px solid rgba(0,0,0,0.12); backdrop-filter: blur(4px); }
  .edits-masthead-credit:hover { background: rgba(255,255,255,0.95); }
  .edits-masthead-credit i { font-size: 13px; }
  @media (max-width: 640px) {
    .edits-masthead { aspect-ratio: 4/5; }
    .edits-masthead-copy { padding-top: 8%; }
    .edits-masthead-copy h1 { font-size: 38px; margin-bottom: 10px; }
    .edits-masthead-copy p { font-size: 14px; }
    .edits-masthead-copy p br { display: none; }
  }
"""


def masthead_html(title, intro_html, product, text="dark", wide=False, kicker=None):
    """`text` is "dark" for a light photo, "light" for a dark one. `intro_html` is trusted HTML."""
    import image_fit
    url = product["brand_url"] if product.get("link_dead") else product["product_url"]
    fit_class, fit_style = image_fit.fit_for_banner(product["image_url"])
    style = f' style="{fit_style}"' if fit_style else ""
    img_class = f' class="{fit_class}"' if fit_class else ""
    credit = f'{html.escape(product["product_name"])} &middot; {html.escape(product["brand"])}'
    kicker_html = (f'<a class="edits-masthead-kicker" href="/edits.html">{html.escape(kicker)}</a>' if kicker else "")
    tone = ("" if text == "dark" else " edits-masthead--light") + (" edits-masthead--wide" if wide else "")
    return f"""    <section class="edits-masthead{tone}"{style}>
      <img{img_class} src="{html.escape(sized(product["image_url"], HERO))}" alt="{html.escape(product["product_name"])} by {html.escape(product["brand"])}">
      <div class="edits-masthead-copy">
        {kicker_html}<h1>{html.escape(title)}</h1>
        <p>{intro_html}</p>
      </div>
      <a class="edits-masthead-credit" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{credit} <i class="ti ti-arrow-up-right" aria-hidden="true"></i></a>
    </section>"""



def _resolve_carousel_picks(theme, products):
    """
    A theme with a "carousel_picks" key (a list of (brand, product_name)
    tuples) is being hand-picked by a real person - looks each one up
    first in the real fetched product list, then falls back to a direct
    DB lookup by exact (brand, product_name) for anything not found
    there (so a typo or a since-delisted product just quietly drops
    instead of crashing the build), and uses exactly that set, in that
    order, instead of auto-picking. The DB fallback matters because a
    theme's own "fetch" filter can be stricter than what a human
    correctly recognizes as belonging - confirmed live 2026-09-29:
    Two Seater Sofas' fetch requires a product's NAME to literally say
    "2 seater" (see _product_matches_seat_count), which two of three
    user-picked products don't (Pinch's "Rydal sofa", &Tradition's "Fly
    SC2" - the latter's own category field is literally "2-seater
    Sofa"), even though both are real two-seaters. A hand pick has
    already been visually verified by a person, so it doesn't need to
    also pass the same automated heuristic used to build the grid. An
    empty list (the pending-picks state) means no carousel renders at
    all (see _render_carousel) rather than falling back to a default
    that would only need replacing once real picks arrive. A theme with
    no "carousel_picks" key at all keeps the original deterministic
    auto-pick behavior.

    "hero_image" (2026-09-30) takes priority over all of the above when
    present - a single hand-picked (brand, product_name), rendered as
    one static image with no rotation (see _render_carousel's own
    len(picks) <= 1 case) instead of the usual 3-product carousel. This
    is the "strong main in situ image as the attraction" layout being
    tried out - same lookup-then-DB-fallback resolution as a manual
    carousel_picks entry, just capped at exactly one result.

    An optional "hero_label" overrides just the displayed name for this
    one hero slide (e.g. "Titan (Round) Dining Table" reading as plain
    "Titan Dining Table" here, since "(Round)" is already redundant with
    the whole page being called Round Dining Tables) - a shallow copy,
    never mutating the real dict, since that exact same product also
    appears again in the grid below and must keep showing its real,
    unabbreviated name there.
    """
    hero = theme.get("hero_image")
    if hero is not None:
        lookup = {(p["brand"], p["product_name"]): p for p in products}
        product = lookup.get(hero) or _lookup_product_by_identity(*hero)
        if product is not None and theme.get("hero_label"):
            product = {**product, "product_name": theme["hero_label"]}
        return [_with_image_override(product)] if product is not None else []
    manual = theme.get("carousel_picks")
    if manual is None:
        return _carousel_picks(products, theme.get("exclude", set()))
    lookup = {(p["brand"], p["product_name"]): p for p in products}
    resolved = []
    for key in manual:
        if key in lookup:
            resolved.append(_with_image_override(lookup[key]))
            continue
        product = _lookup_product_by_identity(*key)
        if product is not None:
            resolved.append(_with_image_override(product))
    return resolved


def _lookup_product_by_identity(brand, product_name):
    """Direct DB lookup by exact (brand, product_name) - used only as
    the fallback above for a manual carousel pick the theme's own
    fetch filter excluded."""
    conn = sqlite3.connect(qe.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM products WHERE brand = ? AND product_name = ?",
        (brand, product_name),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _carousel_picks(products, exclude):
    """
    First CAROUSEL_SIZE real, distinct-brand products not already shown
    on the homepage's own teaser for this theme (see each theme's
    "exclude" set) - deterministic, no per-theme hand-picking needed.
    """
    picks = []
    seen_brands = set()
    for p in products:
        if (p["brand"], p["product_name"]) in exclude:
            continue
        if p["brand"] in seen_brands:
            continue
        seen_brands.add(p["brand"])
        picks.append(p)
        if len(picks) >= CAROUSEL_SIZE:
            break
    return picks


def _carousel_frame_html(p, index):
    """
    The image half of a banner slide - just the photo, no overlay text
    at all. A theme-name badge was tried here (2026-09-30, "we can have
    the theme in text on the image"), then dropped the same day once
    live: "it duplicates the work done by the title of the edit" - the
    page's own H1 already says the theme name right above this banner.
    Product name/brand live in _carousel_caption_html instead, below
    the image (same "clean image, caption below" principle the
    homepage's own .feature-banner-frame/.feature-banner-caption pair
    already uses).
    """
    url = p["brand_url"] if p["link_dead"] else p["product_url"]
    alt_text = html.escape(f'{p["product_name"]} by {p["brand"]}')
    active = " active" if index == 0 else ""
    fit_class, fit_style = image_fit.fit_for_banner(p["image_url"])
    style = f' style="{fit_style}"' if fit_style else ""
    img_class = f' class="{fit_class}"' if fit_class else ""
    return f"""
        <a class="banner-slide-frame{active}" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer"{style}>
          <img{img_class} src="{html.escape(sized(p["image_url"], HERO))}" alt="{alt_text}">
        </a>"""


def _carousel_caption_html(p, index):
    """
    The product name/brand half of a banner slide, in normal flow below
    the image box rather than overlaid on it (2026-09-30, user: "the
    product information should sit below... so that clicking the link
    or image takes you to the site") - a second real link to the same
    source URL, kept in sync with its frame via the shared "active"
    class/index (see CAROUSEL_JS's show()).
    """
    url = p["brand_url"] if p["link_dead"] else p["product_url"]
    active = " active" if index == 0 else ""
    return f"""
        <a class="banner-caption{active}" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">
          <p class="banner-caption-title">{html.escape(p["product_name"])}</p>
          <p class="banner-caption-brand">{html.escape(p["brand"])}</p>
        </a>"""


def _render_carousel(picks):
    if not picks:
        return ""
    frames = "".join(_carousel_frame_html(p, i) for i, p in enumerate(picks))
    captions = "".join(_carousel_caption_html(p, i) for i, p in enumerate(picks))
    dots = "".join(
        f'<button type="button" class="banner-dot{" active" if i == 0 else ""}" data-index="{i}" aria-label="Slide {i + 1}"></button>'
        for i in range(len(picks))
    ) if len(picks) > 1 else ""
    dots_html = f'<div class="banner-dots">{dots}</div>' if dots else ""
    # .banner-frames is its own position:relative box (image frames +
    # dots only) so the dots' absolute bottom/right anchors to the image
    # itself, not to the whole carousel's height once a caption is added
    # below it in normal flow - the exact bug already documented on the
    # homepage's own .duo-carousel-caption (see its own comment there).
    return f'<div class="banner-carousel"><div class="banner-frames">{frames}{dots_html}</div>{captions}</div>'


CAROUSEL_JS = """
  document.querySelectorAll(".banner-carousel").forEach(function (carousel) {
    var slides = carousel.querySelectorAll(".banner-slide-frame");
    var captions = carousel.querySelectorAll(".banner-caption");
    var dots = carousel.querySelectorAll(".banner-dot");
    if (slides.length <= 1) return;
    var current = 0;
    var timer;
    function show(i) {
      current = i;
      slides.forEach(function (s, idx) { s.classList.toggle("active", idx === i); });
      captions.forEach(function (c, idx) { c.classList.toggle("active", idx === i); });
      dots.forEach(function (d, idx) { d.classList.toggle("active", idx === i); });
    }
    function next() { show((current + 1) % slides.length); }
    function prev() { show((current - 1 + slides.length) % slides.length); }
    function start() { timer = setInterval(next, 6000); }
    function stop() { clearInterval(timer); }
    dots.forEach(function (d, i) {
      d.addEventListener("click", function () { show(i); stop(); start(); });
    });
    carousel.addEventListener("mouseenter", stop);
    carousel.addEventListener("mouseleave", start);
    // Touch swipe (2026-09-29) - mouseenter/mouseleave above never fire
    // on a touch device, so mobile previously only had dot-tapping and
    // auto-rotation. touchmove decides real swipe intent (horizontal
    // movement clearly exceeding vertical) before preventDefault, so a
    // vertical page scroll starting inside the carousel is untouched.
    var touchStartX = 0, touchStartY = 0, isSwiping = false;
    carousel.addEventListener("touchstart", function (e) {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      isSwiping = false;
      stop();
    }, { passive: true });
    carousel.addEventListener("touchmove", function (e) {
      var dx = e.touches[0].clientX - touchStartX;
      var dy = e.touches[0].clientY - touchStartY;
      if (!isSwiping && Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) isSwiping = true;
      if (isSwiping) e.preventDefault();
    }, { passive: false });
    carousel.addEventListener("touchend", function (e) {
      if (isSwiping) {
        var dx = e.changedTouches[0].clientX - touchStartX;
        if (dx > 30) prev();
        else if (dx < -30) next();
      }
      start();
    });
    start();
  });
"""


# "It is not a filter, it is an edit" (user, 2026-09-30) - real edits
# were showing their whole raw match count (906 for Pendant Lamps),
# which reads as a search result, not a curated pick, and made every
# page a different length. Capped every edit down to the same small,
# genuinely curated size instead - originally landed on 16 (talking
# through 6/9/12/16 live) so it would divide cleanly into a 7-card
# feature row plus a 9-card Mini Bento interlude. Once the Mini Bento
# was dropped (see _render_feature_grid's own comment), the feature
# grid's own real column count - 6 per row at its max page width -
# became the constraint instead: 16 left 2 empty slots dangling in a
# third row. Lowered to 12 (two full, clean rows of 6) rather than
# rounding up to 18, since a tighter cap reads more like "our pick"
# than a looser one.
MAX_PRODUCTS_PER_EDIT = 12


def _cap_products_fairly(cards, max_count=MAX_PRODUCTS_PER_EDIT):
    """
    Round-robins one product per brand per pass - same fairness
    principle as query_engine.cap_per_brand/round_robin_order - so
    capping down to a small, fixed size doesn't just keep whichever
    brand happens to have the deepest catalog for this theme. Stable,
    not random: dict insertion order here follows `cards`' own order
    (whatever _group_color_variants/the DB query already produced), so
    the same real data always caps down to the same real edit - a
    curated page shouldn't look different on every rebuild for no
    curatorial reason.
    """
    if len(cards) <= max_count:
        return cards
    by_brand = {}
    for p in cards:
        by_brand.setdefault(p["brand"], []).append(p)
    capped = []
    while len(capped) < max_count:
        added_this_pass = False
        for brand_products in by_brand.values():
            if not brand_products:
                continue
            capped.append(brand_products.pop(0))
            added_this_pass = True
            if len(capped) >= max_count:
                break
        if not added_this_pass:
            break
    return capped


def _hero_identities(theme):
    """The (brand, product_name) identities a theme shows in its banner."""
    if not EDIT_PAGE_BANNER:
        return []  # no banner, so nothing is held out of the grid
    hero = theme.get("hero_image")
    return ([hero] if hero else []) + list(theme.get("carousel_picks") or [])


def _variant_key(p):
    """Same key _group_color_variants collapses finishes by (brand + the name
    with colour/finish words removed), so a hero's other finishes match it."""
    words = re.findall(r"[A-Za-z\u00c0-\u00ff]+|[0-9]+|\u00d8|/", p["product_name"])
    kept = [w for w in words if w.lower() not in COLOR_FINISH_WORDS]
    return (p["brand"], " ".join(kept).lower())


def capped_edit_cards(theme, products):
    """
    The one real product list every surface showing this edit's content
    or count should use - color-variant-grouped, then fairly capped to
    MAX_PRODUCTS_PER_EDIT. Shared between this file's own
    render_themed_edit_page and generate_edits_page.py's hub (both the
    "X pieces" count shown there and the individual edit page's own
    grid need to agree on the same real number - see MAX_PRODUCTS_PER_
    EDIT's own comment for why that now matters). Returns (cards,
    variant_counts) - the same shape _group_color_variants itself
    returns, so callers don't need to know capping happened at all.
    """
    # The hero/banner product is NOT repeated among the cards (2026-10-03,
    # user: "remove it from the grid"): its whole colour/finish family is left
    # out before grouping and capping, so the grid backfills with the next
    # pieces and stays a full MAX_PRODUCTS_PER_EDIT. The hero is shown (and
    # counted - see edit_totals) as its own piece above the grid.
    hero_keys = {_variant_key({"brand": b, "product_name": n}) for b, n in _hero_identities(theme)}
    if hero_keys:
        products = [p for p in products if _variant_key(p) not in hero_keys]
    cards_to_render, variant_counts = _group_color_variants(products)
    capped = _cap_products_fairly(cards_to_render)
    # swap in hand-chosen photos; variant_counts is keyed by id(card), so re-key it
    swapped = [_with_image_override(p) for p in capped]
    variant_counts = {id(new): variant_counts[id(old)] for old, new in zip(capped, swapped) if id(old) in variant_counts}
    return swapped, variant_counts


def edit_totals(theme, cards_to_render):
    """(pieces, makers) an edit really shows: its capped grid PLUS any
    hand-picked hero/carousel product that the cap left out of the grid
    (2026-10-03, user: "if the banner has a unique product it maybe should be
    included in the count" - Pendant Lamps' Apparatus hero is not among its
    12 grid pieces, so the page showed 13 while the hub said 12). Compared by
    product_url, since a hero_label copy renames the product."""
    in_grid = {p["product_url"] for p in cards_to_render}
    extra = ([p for p in _resolve_carousel_picks(theme, cards_to_render) if p["product_url"] not in in_grid]
             if EDIT_PAGE_BANNER else [])
    brands = {p["brand"] for p in cards_to_render} | {p["brand"] for p in extra}
    return len(cards_to_render) + len(extra), len(brands)


# Larger-image feature row (2026-09-30, user: "we can also use larger
# images such as for Chairs on the home page and have the same placing
# of the product name and brand... with a max of 16 then I think we can
# look at using different layout combinations to make the edit pages
# interesting to peruse") - reuses the exact image/name/brand placement
# the homepage's own "New" shelf cards (.recent-card) already use, just
# laid out as a wrapping grid here (not a horizontal scroll-snap shelf)
# so every feature card stays visible without needing a swipe - an
# edit's whole point is a small, fully-visible curated set, not a
# "peek and scroll for more" teaser the way the homepage's own shelf is.
# Carries the whole MAX_PRODUCTS_PER_EDIT-capped set alone (a Mini Bento
# interlude was tried between this and the grid, 2026-09-30, then
# dropped: "not worth the hassle this is causing").


# Photos that the square card crop damages (2026-10-03, user: "see if we can
# get the lamp to fit better in the space"): shown whole instead of cropped.
# Keyed by product_url. Kantarell Pendant O60 is a 3:2 shot whose disc shade
# spans 78% of the width, so a centred square crop cut both rims.
# A better photo than the one the scrape picked (2026-10-03, user: "is there a
# close up image of this?"), taken from the product's own page. Display only:
# the database keeps the scraped image. Keyed by product_url.
EDIT_IMAGE_OVERRIDES = {
    # the scraped photo is a room with a tiny red lamp; this is the lamp itself
    "https://www.incommonwith.com/products/dune-portable-table-lamp":
        "https://www.incommonwith.com/cdn/shop/files/InCommonWith_DuneTableLamp_Pool_VillaCaffetto_17.jpg?v=1787171332&width=1500",
    # the scraped photo is Mercoeur's grey close-up thumbnail (lamp cut off at the edges); this is the
    # product's main shot - the whole lamp on white
    "https://www.mercoeur-edition.com/products/table-lamp":
        "https://cdn.prod.website-files.com/65f8e4972094d2411f63ed1d/6a4e099512b16700964973bd_ARCY%20LAP%20Light.webp",
    # the scraped photo is a wide room with a tiny lamp; this is a landscape close-up of its brass ball and base
    "https://hbigeleisen.com/in-stock/io-brushed-copper-table-lamp":
        "https://images.squarespace-cdn.com/content/v1/57b3208aff7c50dc3b5aef6a/1701278909340-GBM23PQ69EQS6XQMETU5/HannahBigeleisen_Lamp_1022_LizClayman_09.jpg",
}


def _with_image_override(p):
    alt = EDIT_IMAGE_OVERRIDES.get(p["product_url"])
    return {**p, "image_url": alt} if alt else p


EDIT_IMAGE_FIT_CONTAIN = {"https://newworks.dk/en/product/kantarell-pendant-lamp-o60"}

_TRAILING_SIZE_RE = re.compile(r"\s*[\u00d8\u2300]\s?\d+(?:[.,]\d+)?\s*(?:cm|mm)?\s*$", re.I)


def _display_names(cards):
    """{id(card): name} for an edit grid. A trailing diameter ("Kantarell
    Pendant Lamp O60") is dropped from the DISPLAYED name - on an editorial
    card the size is not the identity, the buyer picks it on the maker's own
    page - but only when no other card in the same grid would then carry the
    same name (New Works lists Margin O50/O70/O90 as three products; stripping
    all three would show three identical cards). Search and the database keep
    the full names."""
    # spec-style names ("... | H 71.6 cm | O 100 cm") are left whole: dropping only the
    # diameter would leave a dangling, half-stated spec line
    stripped = {id(p): p["product_name"] if "|" in p["product_name"]
                else (_TRAILING_SIZE_RE.sub("", p["product_name"]).strip() or p["product_name"]) for p in cards}
    counts = {}
    for p in cards:
        counts[stripped[id(p)].lower()] = counts.get(stripped[id(p)].lower(), 0) + 1
    return {id(p): (stripped[id(p)] if counts[stripped[id(p)].lower()] == 1 else p["product_name"]) for p in cards}


def _render_feature_grid(cards, variant_counts=None):
    """The Edit's grid: the very same card as the Work page and every type page (photo with the share button,
    name, maker; `_listing_card_html`), in the Work page's own `results-grid` - one card design site-wide."""
    if not cards:
        return ""
    from generate_browse_pages import _listing_card_html  # lazy: that module imports this one
    variant_counts = variant_counts or {}
    names = _display_names(cards)
    items = []
    for p in cards:
        card = _listing_card_html({**p, "product_name": names[id(p)]}, variant_counts.get(id(p)))
        if p["product_url"] in EDIT_IMAGE_FIT_CONTAIN:
            card = card.replace("<img ", '<img class="contain-fit" ', 1)
        items.append(card)
    return f'<div class="results-grid">{"".join(items)}</div>'


EDIT_PAGE_CSS = """
  main { max-width: 1160px; margin: 0 auto; padding: 48px 20px 60px; }
  .edit-header { max-width: 640px; margin: 0 auto 40px; text-align: center; }
  .edit-header h1 { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 36px; margin: 0 0 14px; }
  .edit-intro { font-size: 15px; line-height: 1.65; color: var(--text-secondary); margin: 0; }
  .page-tagline { font-size: 13px; color: var(--text-secondary); text-align: center; margin: 0 0 8px; }

  /* "Edits" as a recurring masthead across every individual edit page
     (2026-09-30, user's own framing: "Edits... stays on all edits
     pages as the equivalent of a magazine brand name" - Round Coffee
     Tables etc. are then "one of many themes/sections" under it) - a
     real link back to the hub, not just a plain caption the way "A
     themed edit" was. Bold + letter-spaced so it reads as a mark, but
     still visually secondary to the page's own h1 below it - the
     visitor came for "Round Coffee Tables," not for "Edits" again.
     Nested inside .page-tagline for the same centering, not duplicated. */
  .edits-kicker {
    font-weight: 700; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.08em; text-decoration: none;
  }
  .edits-kicker:hover { color: var(--text-primary); text-decoration: underline; }

  /* Larger-image feature row (see _render_feature_grid) - same image/
     name/brand placement as the homepage's own .recent-card (bigger
     square photo, bold name, muted brand directly below), just a
     wrapping grid instead of a horizontal scroll-snap shelf - every
     card stays visible at once, nothing hidden behind a swipe the way
     the homepage's own "peek and scroll" shelf intentionally hides
     more. Carries the whole capped edit alone (a Mini Bento interlude
     was tried and dropped, 2026-09-30 - "not worth the hassle this is
     causing"). */
  .edit-see-all { text-align: center; margin: -8px 0 40px; font-size: 14px; }
  .edit-see-all a { color: var(--text-accent); text-decoration: none; }
  .edit-see-all a:hover { text-decoration: underline; }
  @media (max-width: 760px) {
    .edit-header h1 { font-size: 28px; }
  }

  /* Same Banner Carousel primitive used for the homepage's Sofas edit
     (2026-09-29) - carries the homepage's own "themed edit" feel onto
     this dedicated page, with different real pieces than the homepage
     teaser shows (see each theme's "exclude" list). Auto-rotates every
     6s, dot navigation, pauses on hover.
     Image and caption were split into two real elements, not one
     gradient-scrim-over-photo block (2026-09-30, user: "the product
     information should sit below... so that clicking the link or image
     takes you to the site") - same "clean image, caption below"
     principle the homepage's own .feature-banner-frame/
     .feature-banner-caption pair already settled on. A theme-name badge
     was tried on the image itself too, same day, then dropped just as
     quickly once live - "it duplicates the work done by the title of
     the edit" (the page's own H1, right above this banner). Sized 2/1
     (desktop) / 4/3 (mobile) to match that same primitive exactly - an
     earlier attempt to widen this box for portrait-shaped
     hero photos (first 4/5, then a "square" 1/1) never actually fixed
     anything, since the real problem was the SOURCE PHOTO's own shape,
     not the box: "the images are the wrong size for a banner so they
     are being forced to do something they cannot" (user, 2026-09-30).
     See each theme's own "hero_image" comment for how that's handled
     now (a landscape placeholder, or left pending). */
  .banner-carousel { margin-bottom: 40px; }
  /* Own position:relative box for just the image frames + dots, kept
     separate from the caption below - otherwise the dots' absolute
     bottom/right would anchor to the bottom of the WHOLE carousel
     (frame + caption combined) instead of to the image itself, the
     same bug already documented on the homepage's own
     .duo-carousel-caption. */
  .banner-frames { position: relative; }
  .banner-slide-frame {
    display: none; position: relative; aspect-ratio: 2/1;
    border: 0.5px solid var(--border); overflow: hidden;
    text-decoration: none; color: inherit;
  }
  .banner-slide-frame.active { display: block; }
  .banner-slide-frame img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.4s ease; }
  .banner-slide-frame:hover img { transform: scale(1.02); }
  .banner-slide-frame img.fit-contain { object-fit: contain; }
  .banner-dots { position: absolute; bottom: 18px; right: 24px; z-index: 2; display: flex; gap: 6px; }
  .banner-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.5); border: none; cursor: pointer; padding: 0; }
  .banner-dot.active { background: #fff; }
  .banner-caption { display: none; text-decoration: none; color: inherit; margin-top: 14px; }
  .banner-caption.active { display: block; }
  .banner-caption-title { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 22px; margin: 0 0 4px; }
  .banner-caption-brand { font-size: 13px; color: var(--text-secondary); margin: 0; }
  .banner-caption:hover .banner-caption-title { text-decoration: underline; }
  @media (max-width: 760px) {
    .banner-slide-frame { aspect-ratio: 4/3; }
  }
"""


# Each Edit shows a curated MAX_PRODUCTS_PER_EDIT; the uncapped category
# it was picked from lives under /work/ (generate_browse_pages.py,
# 2026-10-02) - linked from here so a visitor or crawler can get from
# the pick to the full set. Portable Lamps is a filtered subset of
# table lamps with no category page of its own, so it points there too.
EDIT_BROWSE_LINKS = {
    "table-lamps": ("table-lamps", "table lamps"),
    "portable-lamps": ("portable-lamps", "portable lamps"),
    "pendant-lamps": ("pendant-lamps", "pendant lamps"),
    "wall-lamps": ("wall-lamps", "wall lamps"),
    "ceiling-lamps": ("ceiling-lamps", "ceiling lamps"),
    "round-dining-tables": ("dining-tables", "dining tables"),
    "scandinavian-dining-tables": ("dining-tables", "dining tables"),
    "round-coffee-tables": ("coffee-tables", "coffee tables"),
    "two-seater-sofas": ("sofas", "sofas"),
}


# Edit pages are kept simple for now (2026-10-04, user: "simplify it and use this layout" = the Ceiling Lamps
# page): the Edit's kicker, title and intro, then the grid - no banner photo, carousel or masthead. Set True
# to bring the banner (or, via MASTHEAD_SLUGS, the masthead) back; the hero picks in THEMES are kept.
EDIT_PAGE_BANNER = False

# Edit pages that use the masthead header (title + intro on the hero photo). TRIAL: one page first
# (2026-10-04), the rest follow once approved - then this becomes "every Edit with a hero photo".
MASTHEAD_SLUGS = {"two-seater-sofas"}


def render_themed_edit_page(theme, products):
    slug = theme["slug"]
    title = theme["title"]
    page_url = f"{SITE_URL}/edits/{slug}.html"

    # The real, capped count (see capped_edit_cards/MAX_PRODUCTS_PER_EDIT) -
    # not the raw pre-cap match count. "It is not a filter, it is an
    # edit" (user, 2026-09-30): the description should promise exactly
    # what the page actually shows, the same number the Edits hub's own
    # card already advertises for this theme.
    cards_to_render, variant_counts = capped_edit_cards(theme, products)
    n, _makers = edit_totals(theme, cards_to_render)
    description = f"{n} real {title.lower()}{'' if title.lower().endswith('s') else 's'}, from independent makers. {theme['intro']}"

    picks = _resolve_carousel_picks(theme, cards_to_render) if EDIT_PAGE_BANNER else []
    use_masthead = EDIT_PAGE_BANNER and slug in MASTHEAD_SLUGS and len(picks) == 1
    carousel_html = _render_carousel(picks)
    tagline_html = "" if use_masthead else '<p class="page-tagline"><a class="edits-kicker" href="/edits.html">Edits</a></p>'
    if use_masthead:
        # the photo is the header: title + intro sit on it, so no separate header or banner below
        header_html = masthead_html(title, html.escape(theme["intro"]), picks[0], theme.get("masthead_text", "dark"), wide=True, kicker="Edits")
        carousel_html = ""
    else:
        header_html = f'''<div class="edit-header">
    <h1>{html.escape(title)}</h1>
    <p class="edit-intro">{html.escape(theme["intro"])}</p>
  </div>'''

    if cards_to_render:
        # One layout treatment for the whole capped set (2026-09-30,
        # user: "let's just skip the mini bento, not worth the hassle
        # this is causing") - a Mini Bento interlude was tried between
        # this and the feature grid, but dropped before shipping; the
        # larger-image feature grid alone (see _render_feature_grid,
        # same placement as the homepage's own "New" shelf cards) now
        # carries every capped card.
        body = _render_feature_grid(cards_to_render, variant_counts)
        if slug in EDIT_BROWSE_LINKS:
            browse_slug, noun = EDIT_BROWSE_LINKS[slug]
            body += f'\n  <p class="edit-see-all"><a href="/work/{browse_slug}.html">See all {noun} &rarr;</a></p>'
    else:
        body = '<p class="empty-state">Check back soon - new pieces are added here as they are found.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)} — Formground">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/favicon-192x192.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{html.escape(title)} — Formground">
<meta name="twitter:description" content="{html.escape(description)}">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<link rel="stylesheet" href="{WORK_RESULTS_CSS}">
<style>{PAGE_CSS}{EDIT_PAGE_CSS}{EDIT_MASTHEAD_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML_EDITS}
</header>
<main>
  {tagline_html}
  {header_html}
  {carousel_html}
  {body}
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>
  document.querySelectorAll(".card-image img").forEach(function (img) {{
    img.addEventListener("load", function () {{
      var ratio = img.naturalWidth / img.naturalHeight;
      if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
    }});
  }});
</script>
<script>{CAROUSEL_JS}</script>
<script>{CARD_CLICK_TRACKING_JS}</script>
<script src="{SHARE_JS}" defer></script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def generate():
    EDITS_DIR.mkdir(exist_ok=True)
    slugs = []
    for theme in THEMES:
        products = theme["fetch"]()
        (EDITS_DIR / f"{theme['slug']}.html").write_text(render_themed_edit_page(theme, products))
        slugs.append(f"edits/{theme['slug']}")
        # the page used to live at the site root: leave a redirect stub there
        write_redirect(DOCS_DIR / f"{theme['slug']}.html", f"/edits/{theme['slug']}.html")
        shown, _ = capped_edit_cards(theme, products)
        print(f"edits/{theme['slug']}.html: {len(shown)} shown (of {len(products)} real matches)")
    append_to_sitemap(slugs)


if __name__ == "__main__":
    generate()
