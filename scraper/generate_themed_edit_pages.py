"""
Formground Themed Edit page generator.

WHAT THIS DOES: generates richer, editorial static pages (docs/{slug}.html)
for "Themed Edits" - the curated, compound long-tail groupings shown
under the homepage's "Themed Edits" header (Wood Sofas, Round Dining
Tables, Round Coffee Tables, Scandinavian Dining Tables) - as distinct
from generate_theme_landing_pages.py's plain-grid pages for the
straightforward single-keyword categories (Floor Lamps, Table Lamps,
Vases, Ceramics, Chairs, Sofas, Coffee Tables).

WHY A SEPARATE GENERATOR: a Themed Edit is framed as "our pick," not
"here's everything" - even though (per 2026-09-29 decision) it still
shows every real matching product rather than a hand-curated subset,
it deserves real editorial treatment: a genuine intro paragraph, not a
one-line description, and a varied-size grid (some tiles large, most
normal) rather than a uniform card grid - "more editorial and rich,"
per the user's own framing. One shared render function
(render_themed_edit_page) means adding a new theme later is just a new
THEMES entry, not a new template.

"Show all products unless the theme is '10 wooden tables'" (user's own
example of the one exception) - none of today's four themes are a
fixed-count pick, so all four are fully query-driven from
backend/query_engine.py, same as generate_theme_landing_pages.py's
pages. Reuses that module's _group_color_variants()/COLOR_FINISH_WORDS
directly rather than duplicating the variant-grouping logic.

RUN (after generate_brand_pages.py, since it needs sitemap.xml and
appends to it):
    python3 generate_themed_edit_pages.py
"""

import html
import sqlite3
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
SITEMAP_PATH = DOCS_DIR / "sitemap.xml"
BACKEND_DIR = SCRAPER_DIR.parent / "backend"

sys.path.insert(0, str(BACKEND_DIR))
import query_engine as qe  # noqa: E402

from generate_brand_pages import (  # noqa: E402
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_NAV_HTML,
    SITE_URL,
    product_card_html,
)
from generate_theme_landing_pages import (  # noqa: E402
    _group_color_variants,
    append_to_sitemap,
)

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
        # User's own hand-picked carousel (2026-09-29) - see
        # _resolve_carousel_picks for why "Rydal sofa" and "Fly SC2"
        # need the direct-DB-lookup fallback (neither name literally
        # says "2 seater", so the theme's own fetch filter above
        # excludes them from the grid).
        "carousel_picks": [
            ("Fogia", "Boxlike 2 Seater Sofa"),
            ("Pinch", "Rydal sofa"),
            ("&Tradition", "Fly SC2"),
        ],
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
    },
]

CAROUSEL_SIZE = 3


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
    """
    manual = theme.get("carousel_picks")
    if manual is None:
        return _carousel_picks(products, theme.get("exclude", set()))
    lookup = {(p["brand"], p["product_name"]): p for p in products}
    resolved = []
    for key in manual:
        if key in lookup:
            resolved.append(lookup[key])
            continue
        product = _lookup_product_by_identity(*key)
        if product is not None:
            resolved.append(product)
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


def _carousel_slide_html(p, index):
    url = p["brand_url"] if p["link_dead"] else p["product_url"]
    alt_text = html.escape(f'{p["product_name"]} by {p["brand"]}')
    active = " active" if index == 0 else ""
    return f"""
        <div class="banner-slide{active}">
          <a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">
            <img src="{html.escape(p["image_url"])}" alt="{alt_text}">
            <div class="banner-slide-content">
              <p class="banner-slide-eyebrow">A themed edit</p>
              <p class="banner-slide-title">{html.escape(p["product_name"])}</p>
              <p class="banner-slide-brand">{html.escape(p["brand"])}</p>
            </div>
          </a>
        </div>"""


def _render_carousel(picks):
    if not picks:
        return ""
    slides = "".join(_carousel_slide_html(p, i) for i, p in enumerate(picks))
    dots = "".join(
        f'<button type="button" class="banner-dot{" active" if i == 0 else ""}" data-index="{i}" aria-label="Slide {i + 1}"></button>'
        for i in range(len(picks))
    ) if len(picks) > 1 else ""
    dots_html = f'<div class="banner-dots">{dots}</div>' if dots else ""
    return f'<div class="banner-carousel">{slides}{dots_html}</div>'


CAROUSEL_JS = """
  document.querySelectorAll(".banner-carousel").forEach(function (carousel) {
    var slides = carousel.querySelectorAll(".banner-slide");
    var dots = carousel.querySelectorAll(".banner-dot");
    if (slides.length <= 1) return;
    var current = 0;
    var timer;
    function show(i) {
      current = i;
      slides.forEach(function (s, idx) { s.classList.toggle("active", idx === i); });
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


# A Mini Bento interlude (the same asymmetric 1-tall+4-square module
# built for the homepage), paired with a few regular product cards in
# the SAME row - not a full-width block interrupting the grid, but one
# row that mixes the bento cluster with ordinary cards (2026-09-29,
# user's own call after seeing the full-width version). Only inserted
# when there's enough real content to spare (see _split_for_bento) - a
# thin theme just gets the carousel + a plain grid, no bento pulled out
# of too few results.
MIN_PRODUCTS_FOR_BENTO = 20
BENTO_SIZE = 5
SIDE_CARD_COUNT = 4


def _split_for_bento(cards):
    """
    (before, bento_picks, side_picks, after) - pulled from roughly the
    midpoint of the real, ordered list (not the start, so the carousel
    and the grid's own opening don't repeat the same pieces). Only the
    bento cluster requires distinct brands (it's the visual hero of the
    row); the side cards just take whatever comes next, repeats allowed
    - the real data is scraped and stored brand-by-brand, so a run of
    114 real items can still land on only 8 distinct brands in its back
    half (confirmed live, Scandinavian Dining Tables) - requiring 9
    distinct brands for bento+side together made the interlude silently
    vanish even on the biggest theme. Returns (cards, [], [], [])
    unchanged when there isn't enough content to spare a real interlude.
    """
    if len(cards) < MIN_PRODUCTS_FOR_BENTO:
        return cards, [], [], []
    mid = len(cards) // 2
    seen_brands = set()
    bento_picks = []
    bento_indices = []
    for i in range(mid, len(cards)):
        p = cards[i]
        if p["brand"] in seen_brands:
            continue
        seen_brands.add(p["brand"])
        bento_picks.append(p)
        bento_indices.append(i)
        if len(bento_picks) >= BENTO_SIZE:
            break

    remaining_after_bento = len(cards) - mid - len(bento_indices)
    if len(bento_picks) < BENTO_SIZE or remaining_after_bento < SIDE_CARD_COUNT:
        return cards, [], [], []

    bento_index_set = set(bento_indices)
    side_picks = []
    side_indices = []
    for i in range(mid, len(cards)):
        if i in bento_index_set:
            continue
        side_picks.append(cards[i])
        side_indices.append(i)
        if len(side_picks) >= SIDE_CARD_COUNT:
            break

    pick_index_set = bento_index_set | set(side_indices)
    before = [p for i, p in enumerate(cards) if i < mid]
    after = [p for i, p in enumerate(cards) if i >= mid and i not in pick_index_set]
    return before, bento_picks, side_picks, after


def _render_bento_row(bento_picks, side_picks):
    if len(bento_picks) < BENTO_SIZE or len(side_picks) < SIDE_CARD_COUNT:
        return ""
    tiles = ""
    for i, p in enumerate(bento_picks[:BENTO_SIZE]):
        url = p["brand_url"] if p["link_dead"] else p["product_url"]
        alt_text = html.escape(f'{p["product_name"]} by {p["brand"]}')
        tiles += f"""
      <a class="mini-bento-tile mini-bento-{i + 1}" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">
        <img src="{html.escape(p["image_url"])}" alt="{alt_text}">
        <p class="mini-bento-label">{html.escape(p["product_name"])}</p>
        <div class="mini-bento-caption">{html.escape(p["product_name"])}<span>{html.escape(p["brand"])}</span></div>
      </a>"""
    side_cards = "".join(product_card_html(p, show_brand=True) for p in side_picks[:SIDE_CARD_COUNT])
    return f"""
    <div class="bento-row">
      <div class="mini-bento">{tiles}</div>
      <div class="bento-side-cards">{side_cards}</div>
    </div>"""


EDIT_PAGE_CSS = """
  main { max-width: 1160px; margin: 0 auto; padding: 48px 20px 60px; }
  .edit-header { max-width: 640px; margin: 0 auto 40px; text-align: center; }
  .edit-header h1 { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 36px; margin: 0 0 14px; }
  .edit-intro { font-size: 15px; line-height: 1.65; color: var(--text-secondary); margin: 0; }
  .page-tagline { font-size: 13px; color: var(--text-secondary); text-align: center; margin: 0 0 8px; }

  /* Mini Bento paired with regular product cards in ONE row (2026-09-29,
     user's call: not a full-width block interrupting the grid). The
     bento stays square (matching the homepage's own paired version,
     not its full-width 2.8:1 one), and .bento-side-cards is a matching
     2x2 block of ordinary cards (same product_card_html() markup as the
     rest of the page) sized to align with it. */
  .bento-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 40px 0; align-items: stretch; }
  .bento-side-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .mini-bento {
    display: grid; grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr;
    gap: 10px; width: 100%; aspect-ratio: 1/1;
  }
  .mini-bento-tile { position: relative; display: block; overflow: hidden; border: 0.5px solid var(--border); background: var(--surface-1); }
  .mini-bento-tile img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.3s ease; }
  .mini-bento-tile:hover img { transform: scale(1.03); }
  .mini-bento-1 { grid-column: 1; grid-row: 1 / 3; }
  .mini-bento-2 { grid-column: 2; grid-row: 1; }
  .mini-bento-3 { grid-column: 3; grid-row: 1; }
  .mini-bento-4 { grid-column: 2; grid-row: 2; }
  .mini-bento-5 { grid-column: 3; grid-row: 2; }
  /* Hover-reveal, matching the homepage's own top 4-tile bento's
     .cat-tile/.cat-label/.cat-details split, and now also its own
     Floor Lamps mini-bento/duo-carousel slides (2026-09-29, user's
     call: "should we use the same hover over function as on the home
     page large bento... needs to be consistent across the site") - a
     plain, always-visible name (.mini-bento-label) stands in at rest,
     and this richer name+brand gradient scrim only fades in on hover.
     Replaces an earlier, page-local-only text-shadow treatment (no
     scrim, always visible) that predated the sitewide hover-reveal
     convention. */
  .mini-bento-label {
    position: absolute; top: 10px; left: 10px; z-index: 2;
    font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 13px;
    color: #fff; letter-spacing: -0.005em; margin: 0;
    pointer-events: none;
  }
  .mini-bento-caption {
    position: absolute; left: 0; right: 0; bottom: 0; z-index: 1;
    padding: 10px 12px; background: linear-gradient(to top, rgba(0,0,0,0.65), rgba(0,0,0,0));
    color: #fff; font-size: 12px; font-weight: 500;
    opacity: 0; transform: translateY(6px);
    transition: opacity 0.25s ease, transform 0.25s ease;
    pointer-events: none;
  }
  .mini-bento-caption span { display: block; font-size: 11px; font-weight: 400; opacity: 0.8; }
  .mini-bento-tile:hover .mini-bento-caption { opacity: 1; transform: translateY(0); }
  @media (max-width: 760px) {
    .edit-header h1 { font-size: 28px; }
    .bento-row { grid-template-columns: 1fr; }
    .mini-bento { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr 1fr; aspect-ratio: auto; height: 480px; }
    .mini-bento-1 { grid-column: 1 / 3; grid-row: 1; }
    .mini-bento-2 { grid-column: 1; grid-row: 2; }
    .mini-bento-3 { grid-column: 2; grid-row: 2; }
    .mini-bento-4 { grid-column: 1; grid-row: 3; }
    .mini-bento-5 { grid-column: 2; grid-row: 3; }
  }

  /* Same Banner Carousel primitive used for the homepage's Sofas edit
     (2026-09-29) - carries the homepage's own "themed edit" feel onto
     this dedicated page, with different real pieces than the homepage
     teaser shows (see each theme's "exclude" list). Auto-rotates every
     6s, dot navigation, pauses on hover. */
  .banner-carousel { position: relative; aspect-ratio: 2/1; margin-bottom: 40px; border: 0.5px solid var(--border); overflow: hidden; }
  .banner-slide { position: absolute; inset: 0; display: none; }
  .banner-slide.active { display: block; }
  .banner-slide a { display: block; width: 100%; height: 100%; position: relative; text-decoration: none; color: inherit; }
  .banner-slide img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .banner-slide-content {
    position: absolute; left: 0; right: 0; bottom: 0; z-index: 1;
    padding: 28px 32px; background: linear-gradient(to top, rgba(0,0,0,0.7), rgba(0,0,0,0));
    color: #fff;
  }
  .banner-slide-eyebrow { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.8; margin: 0 0 6px; }
  .banner-slide-title { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 28px; margin: 0 0 4px; }
  .banner-slide-brand { font-size: 13px; opacity: 0.9; margin: 0; }
  .banner-dots { position: absolute; bottom: 18px; right: 24px; z-index: 2; display: flex; gap: 6px; }
  .banner-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.5); border: none; cursor: pointer; padding: 0; }
  .banner-dot.active { background: #fff; }
  @media (max-width: 760px) {
    .banner-carousel { aspect-ratio: 4/3; }
    .banner-slide-title { font-size: 22px; }
  }
"""


def render_themed_edit_page(theme, products):
    slug = theme["slug"]
    title = theme["title"]
    page_url = f"{SITE_URL}/{slug}.html"
    n = len(products)
    description = f"{n} real {title.lower()}{'' if title.lower().endswith('s') else 's'}, from independent makers. {theme['intro']}"

    cards_to_render, variant_counts = _group_color_variants(products)
    carousel_html = _render_carousel(_resolve_carousel_picks(theme, cards_to_render))

    if cards_to_render:
        # Individual products use the exact same card as /work.html's own
        # results (product_card_html) - the richness comes from the
        # carousel above and the Mini Bento interlude below, not from
        # reinventing the card itself (2026-09-29, user's own call).
        before, bento_picks, side_picks, after = _split_for_bento(cards_to_render)
        before_html = "".join(
            product_card_html(p, show_brand=True, variant_count=variant_counts.get(id(p)))
            for p in before
        )
        body = f'<div class="grid">{before_html}</div>'
        if bento_picks:
            after_html = "".join(
                product_card_html(p, show_brand=True, variant_count=variant_counts.get(id(p)))
                for p in after
            )
            body += _render_bento_row(bento_picks, side_picks) + f'<div class="grid">{after_html}</div>'
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
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}{EDIT_PAGE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline">A themed edit</p>
  <div class="edit-header">
    <h1>{html.escape(title)}</h1>
    <p class="edit-intro">{html.escape(theme["intro"])}</p>
  </div>
  {carousel_html}
  {body}
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/work.html">Search everything</a> &middot; <a href="/about.html">About</a>
  </p>
</main>
<script>
  document.querySelectorAll(".card-image img, .mini-bento-tile img").forEach(function (img) {{
    img.addEventListener("load", function () {{
      var ratio = img.naturalWidth / img.naturalHeight;
      if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
    }});
  }});
</script>
<script>{CAROUSEL_JS}</script>
<script>{CARD_CLICK_TRACKING_JS}</script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def generate():
    slugs = []
    for theme in THEMES:
        products = theme["fetch"]()
        (DOCS_DIR / f"{theme['slug']}.html").write_text(render_themed_edit_page(theme, products))
        slugs.append(theme["slug"])
        print(f"{theme['slug']}.html: {len(products)} products")
    append_to_sitemap(slugs)


if __name__ == "__main__":
    generate()
