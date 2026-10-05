"""
Formground brand page generator.

WHAT THIS DOES:
  Generates one static, crawlable HTML page per brand (docs/brands/
  {slug}.html) listing every one of that brand's products currently on
  Formground, plus a "docs/makers.html" index linking to all of them,
  plus a regenerated docs/sitemap.xml covering every page. Unlike the
  search page itself (client-rendered, nothing for Google to index),
  these are plain static files - real text and links a search engine
  can read directly.

WHY THIS EXISTS:
  Two goals: (1) SEO - real, indexable content per brand, internally
  linked from makers.html (not from search result cards - every
  result card's only action stays "go to the source", per the
  fair-use/legal grounding this whole project relies on); (2) lets
  someone who likes one piece from a maker see everything else they
  have on Formground, from a page reached via makers.html or a search
  engine, not from the search results themselves.

WHO RUNS THIS:
  The GitHub Action (.github/workflows/scrape.yml), right after
  scrape.py, so brand pages regenerate every time the underlying data
  does. Run it yourself with:

    python scraper/generate_brand_pages.py
"""

import datetime
import html
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse
from designer_credits import credited_counts  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import site_sections  # noqa: E402
import query_engine as qe  # noqa: E402  - one definition of "New" (is_new_piece) for pages and search
from image_sizes import CARD, HERO, TILE, sized  # noqa: E402
from site_assets import ICONS_CSS, LISTING_JS, SHARE_JS  # noqa: E402

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
DB_PATH = DATA_DIR / "formground.db"
BRANDS_PATH = SCRAPER_DIR / "brands.json"
PROMOTIONS_PATH = DATA_DIR / "promotions.json"

# Promotions are OFF (2026-10-03, user: too demanding to maintain at this
# stage; the focus is the makers and a good browsing experience, promoting
# smaller makers and connecting them with buyers). One switch hides EVERY
# surface - Marketplace's Promotions tab and banner, the 'live promotion'
# callout on brand pages, the stockist 'live promotion' badges and the
# ?tab=promotions deep links - while data/promotions.json and the detector
# scripts are left untouched, so turning this back on restores everything.
PROMOTIONS_ENABLED = not site_sections.is_hidden("promotions")   # the switch is scraper/site_sections.py
RETAILERS_PATH = DATA_DIR / "retailers.json"
DOCS_DIR = SCRAPER_DIR.parent / "docs"
FRONTEND_DIR = SCRAPER_DIR.parent / "frontend"
BRANDS_DIR = DOCS_DIR / "brands"
SITE_URL = "https://formground.com"

# Same snippet added by hand to index.html/about.html/contact.html -
# kept here as one constant so both places it's used in this file
# can't drift from each other or from those hand-maintained pages.
CLOUDFLARE_ANALYTICS = (
    "<!-- Cloudflare Web Analytics -->"
    "<script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' "
    "data-cf-beacon='{\"token\": \"87e51fd2f5894326b3c6e883edc75a6d\"}'></script>"
    "<!-- End Cloudflare Web Analytics -->"
)

# Same tags added by hand to index.html/about.html/contact.html - kept
# here as one constant for the same reason as CLOUDFLARE_ANALYTICS above.
FAVICON_TAGS = (
    '<link rel="icon" href="/favicon.ico" sizes="any">\n'
    '<link rel="icon" href="/favicon-32x32.png" type="image/png" sizes="32x32">\n'
    '<link rel="icon" href="/favicon-16x16.png" type="image/png" sizes="16x16">\n'
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
)

# Site-wide header nav, added 2026-09-18 so every page - not just the
# homepage - lets a visitor jump straight to another top-level section
# instead of needing the back button or scrolling to the footer. Same
# constant-sharing rationale as CLOUDFLARE_ANALYTICS/FAVICON_TAGS above;
# its `.top-nav` CSS lives in site.css (shared) rather than PAGE_CSS,
# since the homepage also needs it and doesn't use PAGE_CSS.
def unique_slug(base, name, slugs_seen):
    """First free slug for `name`: the base slug, else base-2, base-3 ... A
    collision used to get `-{len(slugs_seen)}`, a number that depended on how
    many pages had been processed before it, so a page's address moved
    whenever unrelated data was added (found 2026-10-03: two designer pages
    went from -96/-97 to -174/-175). Callers iterate in sorted order, so the
    assignment is stable run to run."""
    slug, n = base, 2
    while slug in slugs_seen and slugs_seen[slug] != name:
        slug = f"{base}-{n}"
        n += 1
    return slug


def site_nav_html(current=None):
    """
    `current` marks which top-level section this generated page lives
    under, so e.g. every maker/architect page (and the makers.html/
    architects.html indexes themselves) highlights "Creators" the same
    way work.html hand-highlights "Work" - added 2026-09-20 since
    architects.html/makers.html previously used the fixed, un-highlighted
    nav below regardless of which section they were actually in. Pass
    None for pages that aren't under any single nav item (new.html) or
    write it "creators", "for-creators", etc. matching a real href's
    basename.
    """
    # About lives in the footer, not here - the 5th item pushed the nav
    # to an orphaned 4:1 wrap on the widths where it wrapped at all
    # (2026-09-20, see project memory); 4 items wrap cleanly at every
    # width instead.
    links = [
        ("work", "/work.html", "Work"),
        ("creators", "/creators.html", "Creators"),
        # Edits replaced Marketplace here (2026-10-03, user: Edits is more
        # relevant to keyword search). Marketplace stays one click away in
        # the footer on every page. Still 4 items - see the wrap note above.
        ("edits", "/edits.html", "Edits"),
        # For Creators moved to the footer (2026-10-04): it is not for the audience the ads target, and a
        # shorter header leaves less to parse. It stays one click away in the footer on every page.
    ]
    current_attr = ' class="current"'
    items = "\n".join(
        f'  <a href="{href}"{current_attr if key == current else ""}>{label}</a>'
        for key, href, label in links
    )
    return f'<nav class="top-nav">\n{items}\n</nav>'


# Un-highlighted nav, for generated pages that aren't under any single
# top-level section (new.html) - see site_nav_html() for the
# per-section-highlighted version everything else now uses.
SITE_NAV_HTML = site_nav_html()
# Header nav with "Edits" highlighted, for the Edits hub and every themed Edit.
SITE_NAV_HTML_EDITS = site_nav_html("edits")

# Full site nav in the footer (2026-09-30) - every page's own
# .foot-note used to carry only Home/Privacy/About (sometimes missing
# one of those too, drifted independently per page over time). Every
# real top-level section now gets a real link here, on every page,
# regardless of whether that page also has it in the header nav (which
# stays capped at 4 items - see site_nav_html()'s own docstring for why
# a 5th item there caused a wrap regression). Absolute paths throughout
# so this is identical whether the page sits at the site root or one
# level down (docs/brands/*.html) - this exact string is reused
# unmodified everywhere, not rebuilt per page.
SITE_FOOTER_HTML = (
    '&copy; 2026 Formground &middot; '
    '<a href="/">&larr; Back to Formground</a> &middot; '
    '<a href="/work.html">Work</a> &middot; '
    '<a href="/creators.html">Creators</a> &middot; '
    '<a href="/marketplace.html">Marketplace</a> &middot; '
    '<a href="/for-creators.html">For Creators</a> &middot; '
    '<a href="/edits.html">Edits</a> &middot; '
    '<a href="/privacy.html">Privacy</a> &middot; '
    '<a href="/about.html">About</a> &middot; '
    '<a href="/contact.html">Contact</a>'
)


def load_countries():
    """
    Country is only ever present in brands.json when genuinely
    confirmed (an explicit note, or a country-code domain like .it/
    .se) - never guessed. Brands without it just don't get a country
    tag, rather than showing something unverified.
    """
    brands = json.loads(BRANDS_PATH.read_text())
    return {b["name"]: b["country"] for b in brands if b.get("country")}


def load_hidden_brands():
    """
    A brand marked "hidden": true keeps its data and keeps being
    scraped, but gets no brand page, no makers.html entry, and no
    sitemap entry - for pausing a brand from showing up (e.g. a design
    direction that no longer fits well next to the others) without
    losing its data or its scrape schedule. See query_engine.py's
    HIDDEN_BRANDS for the matching backend-side exclusion (search/
    discover). Any previously-generated page for a brand that's since
    been hidden is deleted here too, rather than left as a stale,
    still-reachable file.
    """
    brands = json.loads(BRANDS_PATH.read_text())
    return {b["name"] for b in brands if b.get("hidden")}


def load_brand_tiers():
    """
    "established" is only ever set manually in brands.json (2026-09-30,
    same 39-brand list used for the keyword-research export) for a
    genuinely well-known/multinational/legacy design house, or a brand
    added specifically to fill a paid-ad keyword gap rather than as an
    independent-maker pick - never inferred from catalog size (a tiny
    catalog doesn't make a brand "independent" any more than a big one
    makes it "established" - Herman Miller-scale brands are excluded
    from the catalog entirely, not just tagged, per
    feedback_exclude_mega_corporate_furniture_houses). Every brand
    without the field defaults to "independent" - the unmarked case is
    the norm, matching makers.html's own "curated selection of makers,
    new and established" framing, not an exception that needs its own
    flag.
    """
    brands = json.loads(BRANDS_PATH.read_text())
    return {b["name"]: "established" for b in brands if b.get("tier") == "established"}


def load_promotions_by_brand():
    """
    Cross-references data/promotions.json (see
    generate_marketplace_page.py, which owns the real schema) against
    brand pages, so a brand with a live promotion links straight to it
    (2026-09-28) - most of a promotion's value is wasted if only
    someone who already knows to check Marketplace's Promotions tab
    ever sees it. Keyed by brand name; every entry already carries its
    own real product/retailer/discount data, so nothing new needs
    scraping or authoring here. Brands not currently promoted just get
    an empty list, same as before this existed.
    """
    if not PROMOTIONS_ENABLED or not PROMOTIONS_PATH.exists():
        return {}
    promotions = json.loads(PROMOTIONS_PATH.read_text(encoding="utf-8"))
    by_brand = {}
    for p in promotions:
        by_brand.setdefault(p["brand"], []).append(p)
    return by_brand


def load_stockists_by_brand():
    """
    Real, free fact about a brand - "where to buy this" - not a paid
    enhancement (2026-09-28, see project memory,
    enhanced_brand_profile_paid_tier_concept: "real facts are free,
    curated richness is paid"). Cross-references data/retailers.json's
    existing `brands` field against brand pages, the same
    zero-new-scraping pattern as load_promotions_by_brand above.

    A retailer chain with several locations (Svenssons' 5 Swedish
    stores) gets grouped into one entry per brand, not one per store -
    same "brand is the minimum unit of inclusion" grouping key
    generate_marketplace_page.py's own `_group_stockists` already uses
    (`r.get("brand") or r["name"]`), duplicated here rather than
    imported since generate_marketplace_page.py imports FROM this file,
    not the other way around.
    """
    if not RETAILERS_PATH.exists():
        return {}
    retailers = json.loads(RETAILERS_PATH.read_text(encoding="utf-8"))
    groups = {}
    order = []
    for r in retailers:
        key = r.get("brand") or r["name"]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    by_brand = {}
    for key in order:
        locations = groups[key]
        carried_brands = set()
        for loc in locations:
            carried_brands.update(loc.get("brands") or [])
        for brand_name in carried_brands:
            by_brand.setdefault(brand_name, []).append((key, locations))
    return by_brand

# A brand can have products across more than one of these - the page
# shows every umbrella that any of its products match. Kept as a
# plain, extendable dict (not a fixed enum) since the user has flagged
# these four will likely grow over time (e.g. textiles, glassware as
# their own umbrella) - adding a new one later is a one-line change
# here, not a rework. Word lists reused from query_engine.py's proven
# HYPERNYM_WORDS/category-inference logic for consistency, not
# reinvented.
UMBRELLA_KEYWORDS = {
    "Furniture": (
        "chair", "table", "stool", "bench", "sofa", "armchair", "ottoman",
        "console", "bookcase", "desk", "storage", "shelving", "shelf",
        "cabinet", "sideboard", "daybed", "modular unit", "seat", "seating",
        "screen", "rocker",
    ),
    "Lighting": (
        "lamp", "light", "sconce", "pendant", "chandelier", "surface mount",
        "flush mount", "wall mount", "suspension",
    ),
    "Ceramics": (
        "ceramic", "vase", "bowl", "plate", "cup", "mug", "pottery",
        "vessel", "carafe", "pitcher",
    ),
}
# Anything matching none of the above falls into this catch-all, by
# design - Formground's stated scope is furniture/lighting/ceramics/
# objects, so "doesn't match the first three" already means "objects".
DEFAULT_UMBRELLA = "Objects"


# A few real letters don't NFKD-decompose into a base letter + combining
# mark the way most accented Latin characters do (they're their own
# distinct letterform in Unicode, e.g. Polish "Ł" is a stroke, not a
# diacritic) - NFKD + ascii-encode silently drops them instead of
# falling back to their nearest plain-letter equivalent (confirmed
# live: "Łukasz Korol" slugified to "ukasz-korol", not "lukasz-korol").
# Added to as real cases are found, not guessed ahead of need.
SLUG_CHAR_OVERRIDES = {"Ł": "L", "ł": "l"}


TITLE_BRAND = " — Formground"


def fit_title(*candidates, limit=70):
    """First candidate whose full <title> (with the brand suffix) fits `limit`
    characters - search engines cut longer ones - else the last, shortest one."""
    for c in candidates:
        if len(c + TITLE_BRAND) <= limit:
            return c + TITLE_BRAND
    return candidates[-1] + TITLE_BRAND


def list_phrase(items):
    """['furniture', 'lighting', 'objects'] -> 'furniture, lighting and objects'."""
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def slugify(name):
    """
    A URL slug needs to be stable once a brand page is indexed -
    changing it later loses accumulated SEO value - so this needs to
    handle every real case in brands.json up front: accented
    characters ("Löwenhielm"), periods ("A. Petersen"), ampersands,
    multiple spaces.
    """
    for char, replacement in SLUG_CHAR_OVERRIDES.items():
        name = name.replace(char, replacement)
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "brand"


def _umbrellas_for_product(p):
    """Which umbrella(s) a single product matches - shared by
    umbrella_categories_for (unions this across a brand's whole
    catalog) and primary_image_for (needs it per-product to find the
    brand's primary category)."""
    category_tags = {t.strip().lower() for t in (p["category"] or "").split(",")}
    exact = {u for u in UMBRELLA_KEYWORDS if u.lower() in category_tags}
    if exact:
        # A category that IS one of these four umbrella names outright
        # (several single-umbrella brands hardcode it exactly - Ingo
        # Maurer, Gubi, Moustache, Northern, Silcohaus, Sé Collections -
        # same "hardcode the one category" precedent noted in
        # extract_wastberg) is authoritative on its own: no need to
        # also keyword-scan the product name, which only introduced
        # false positives - confirmed live 2026-09-20: Ingo Maurer's
        # "LED Bench"/"Floating Table"/"Lucellino Table" all showed a
        # spurious "Furniture" tag purely because their product names
        # contain furniture-shaped words, even though category already
        # unambiguously said "Lighting" (see project memory).
        return exact
    text = f"{p['category']} {p['product_name']}".lower()
    is_lighting = any(
        re.search(rf"\b{re.escape(k)}s?\b", text) for k in UMBRELLA_KEYWORDS["Lighting"]
    )
    found = set()
    for umbrella, keywords in UMBRELLA_KEYWORDS.items():
        for k in keywords:
            if umbrella == "Furniture" and k in ("table", "desk") and is_lighting:
                # A "table"/"desk" mention alongside a real lighting word
                # ("lamp", "light"...) always means "table lamp"/"desk
                # lamp" on this site, never actual furniture - confirmed
                # live 2026-09-20: Minimalux's real "Table Lamps"
                # category and Wästberg's product names (the collection
                # name plus mount type, e.g. "Faro Table" for a table
                # lamp) both falsely showed a "Furniture" tag purely
                # because of this collision (see project memory). Scoped
                # to these two words - no other Furniture keyword
                # collides with a real Lighting phrase.
                continue
            if umbrella == "Furniture" and k == "desk" and re.search(r"\bdesk\s+accessor", text):
                # A pen pot or tray described as a "desk accessory" is
                # an object, not furniture - same false-positive family
                # as the lighting collision above, confirmed live on
                # Minimalux's real "Desk Accessories" category (see
                # project memory).
                continue
            if re.search(rf"\b{re.escape(k)}s?\b", text):
                found.add(umbrella)
                break
    return found or {DEFAULT_UMBRELLA}


def umbrella_categories_for(products):
    """Union of umbrella categories across every product a brand has,
    checked against both category and product_name (some brands, like
    Bitossi, only have a real object-type signal in the name)."""
    found = set()
    for p in products:
        found |= _umbrellas_for_product(p)
    return sorted(found, key=lambda u: (u != "Furniture", u != "Lighting", u))


def primary_image_for(products, umbrellas):
    """
    One hero image for makers.html's card - the first product matching
    the brand's primary umbrella (umbrellas is already sorted Furniture
    > Lighting > Ceramics > Objects, see umbrella_categories_for), so a
    Furniture-and-Ceramics brand leads with furniture rather than
    whatever scraped first. Settled on a single hero image (not a
    multi-image strip) after reviewing both live with real data - one
    real, larger, uncropped-feeling shot of an actual piece was judged
    the clearer illustration of what a maker actually makes, over a row
    of smaller same-brand thumbnails.
    """
    for umbrella in umbrellas:
        for p in products:
            if umbrella in _umbrellas_for_product(p) and p["image_url"]:
                return p["image_url"]
    return ""


def product_card_html(p, show_brand=False, variant_count=None, share=False):
    """
    show_brand adds a brand-name line under the title - off by default
    since every existing caller (render_brand_page's own single-brand
    grid) already has the brand as page context and would find it
    redundant; the New-arrivals page (render_new_page) is the one place
    a mixed-brand grid actually needs it, since "Bench" alone means
    nothing without knowing whose.

    variant_count, when set to 2+, renders a "N finishes" badge over the
    image - the caller (currently only generate_theme_landing_pages.py's
    _group_color_variants) has already collapsed same-size/different-
    color variants of one product into this single representative card;
    see that function for why size variants are deliberately NOT
    collapsed the same way (2026-09-29, user's explicit call).
    """
    url = p["brand_url"] if p["link_dead"] else p["product_url"]
    alt_text = html.escape(f'{p["product_name"]} by {p["brand"]}')
    image = (
        f'<img src="{html.escape(sized(p["image_url"], CARD))}" alt="{alt_text}" loading="lazy">'
        if p["image_url"] else ""
    )
    if image and variant_count and variant_count > 1:
        image += f'<span class="variant-badge">{variant_count} finishes</span>'
    title_html = f'<p class="card-title">{html.escape(p["product_name"])}</p>'
    if show_brand:
        # .card-title-wrap reserves a full 2 lines' height so .card-brand
        # always starts at the same row across a mixed-brand grid (see
        # PAGE_CSS comment) - only needed when a brand line actually
        # follows; a single-brand grid (show_brand=False) has nothing
        # below the title to misalign, so it stays unwrapped.
        title_html = f'<div class="card-title-wrap">{title_html}</div>'
    brand_line = f'<p class="card-brand">{html.escape(p["brand"])}</p>' if show_brand else ""
    # the same share button as the Work page's cards (share.js reads data-product / data-brand)
    share_btn = SHARE_BTN_HTML if share else ""
    return f"""
      <a class="card" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer" data-product="{html.escape(p["product_name"])}" data-brand="{html.escape(p["brand"])}">
        <div class="card-image">{image}{share_btn}</div>
        <div class="card-body">
          {title_html}
          {brand_line}
        </div>
      </a>"""


# Shared across all three static generators (this file, generate_
# marketplace_page.py, generate_for_creators_page.py) - previously
# three independently hand-maintained copies of the same rules (found
# 2026-09-27 while stress-testing whether a "Sponsored" badge primitive
# could generalize across surfaces: the copies had already drifted -
# marketplace/for-creators used a fixed `190px` grid track + `justify-
# content: center` where this file used `minmax(190px, 1fr)`, and none
# of the three had `position: relative` on `.maker-card-hero`, which an
# absolutely-positioned badge needs to anchor to the hero instead of
# escaping to the page).
#
# `.maker-grid`'s track-sizing is deliberately NOT here - brand/maker
# index pages have enough cards to want the grid to stretch and fill
# each row (`minmax(_, 1fr)`), while Marketplace/For Creators sections
# typically show a handful of cards that read better centered at a
# fixed width - each of those two files keeps its own `.maker-grid`
# rule for that reason, layered on top of this shared block.
MAKER_CARD_CSS = """
  .maker-card { display: block; text-decoration: none; color: inherit; }
  .maker-card-hero {
    position: relative; aspect-ratio: 4/3; background: var(--surface-1);
    border: 0.5px solid var(--border); margin: 0 0 10px;
  }
  .maker-card-hero img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .maker-card-hero img.contain-fit { object-fit: contain; }
  .maker-card-body { padding: 0; text-align: center; }
  .maker-card .maker-name { display: block; font-size: 15px; font-weight: 500;
    color: var(--text-secondary); margin: 0 0 3px; }
  .maker-card:hover .maker-name { text-decoration: underline; }
  .maker-country { display: block; font-size: 11px; color: var(--text-secondary); margin: 0 0 3px; }
  .maker-categories { display: block; font-size: 11px; color: var(--text-muted); letter-spacing: 0.01em; }
"""

# Shared "Sponsored" priority-placement primitive (2026-09-28) - see
# project memory, retailer_stockist_and_promotions_concept.md's three
# stackable paid-placement levers. This is the first of the three:
# a labeled section running in the first row(s) of a grid, ONE shared
# label over the whole cluster rather than a badge repeated per card -
# same convention as Google/Amazon sponsored search results. Built as
# a shared primitive from day one (not Promotions-specific code) since
# For Creators and Brandvue are confirmed future consumers of the same
# mechanism, not hypothetical - see
# monetization_build_sequencing_and_shared_primitive.md.
#
# Deliberately doesn't care what's inside it: a promo-card, a
# maker-card, a tool-card - whatever shape the calling page's own cards
# already are. Priority here is about POSITION, not card size/richness
# (that's the separate "richer card" lever, not built yet) - a
# sponsored card can be perfectly normal-sized.
#
# STATUS: real, reusable code, currently unused - no live entry
# anywhere sets a sponsored flag, since no real paying customer exists
# yet (no payment/sign-up flow exists either - see the same memory
# file's item 1). Ships dormant and ready rather than half-built later
# under time pressure once a real sponsor does exist.
SPONSORED_SECTION_CSS = """
  .sponsored-section { margin-bottom: 28px; }
  .sponsored-label {
    text-align: center; font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--text-muted); margin: 0 0 14px;
  }
"""


def render_sponsored_section(cards_html, grid_class, label="Sponsored"):
    """
    Wraps already-rendered card HTML (any shape) in a labeled Sponsored
    section, meant to sit above a page's normal, unpaid grid.
    `grid_class` should match whatever grid class the calling page
    already uses for its own cards (e.g. "promo-grid", "maker-grid") so
    the sponsored cluster lays out identically to the free cards below
    it - this function only adds the label and wrapper, not a new
    layout system. Returns "" if there's nothing sponsored to show, so
    callers can always include the result unconditionally.
    """
    if not cards_html:
        return ""
    return (
        '    <div class="sponsored-section">\n'
        f'      <p class="sponsored-label">{html.escape(label)}</p>\n'
        f'      <div class="{grid_class}">\n{cards_html}\n      </div>\n'
        '    </div>'
    )


# Shared "banner/carousel" paid-placement primitive (2026-09-28) - the
# third and most prominent of the three stackable levers from project
# memory, retailer_stockist_and_promotions_concept.md: "a genuinely
# separate UI slot, not a grid card at all - a dedicated hero unit
# above the grid." Same "wrap already-rendered content, agnostic to
# shape" philosophy as render_sponsored_section above - a Promotions
# slide's content differs from whatever a future For Creators or
# Brandvue slide would show, so only the rotation mechanics are shared,
# not the slide markup itself.
#
# STATUS: real, reusable code, currently unused everywhere - no real
# entry sets a banner flag anywhere (no paid tier or payment flow
# exists yet), same dormant-until-a-real-customer status as the other
# two levers.
BANNER_CAROUSEL_CSS = """
  .banner-carousel { position: relative; margin-bottom: 32px; border-radius: var(--radius); overflow: hidden; aspect-ratio: 2.4/1; background: var(--surface-1); }
  .banner-slide { position: absolute; inset: 0; display: none; }
  .banner-slide.active { display: block; }
  /* The slide's own content (any shape a caller renders) fills this
     box - a plain block link is the common case, but this isn't
     assumed, just given full width/height to work with. */
  .banner-slide > * { display: block; width: 100%; height: 100%; position: relative; text-decoration: none; color: inherit; }
  .banner-slide img { width: 100%; height: 100%; object-fit: cover; display: block; }
  /* Same bottom-gradient-scrim treatment the homepage's own category
     tiles already use for text over a photo (see frontend/index.html's
     .cat-details) - proven to hold up across both dark and light real
     photos, reused rather than inventing a new one. Always visible
     here (not hover-only) since a banner needs to read at a glance. */
  .banner-slide-content {
    position: absolute; left: 0; right: 0; bottom: 0; z-index: 1;
    padding: 36px 40px; background: linear-gradient(to top, rgba(0,0,0,0.75), rgba(0,0,0,0.05) 60%, rgba(0,0,0,0));
    color: #fff;
  }
  /* The banner is a hero unit, not a grid card - it reuses .promo-badge/
     .promo-brand/.promo-name/.promo-price/.promo-cta so the same data
     renders in both places, but every one of them needs to read at
     hero scale, not card scale (2026-09-28, user: "make everything
     that is featured on the image bigger"). Scale is sanity-checked
     against real hero banners (illumsbolighus.dk, mohd's shop, both
     ~40px headlines at 7-8% of their banner's height, CTA buttons
     ~44-50px tall) - but the styling itself stays Formground's own:
     same gradient scrim as the homepage's .cat-details hover reveal,
     same pill-shaped, normal-case "Visit Shop" CTA every other
     Promotions card already uses, just sized for a hero instead of a
     card. Formground's own visual language wins over an external
     site's button conventions (2026-09-28, user: "we should be
     consistent across Formground first and foremost"). */
  .banner-slide .promo-badge { top: 20px; left: 20px; font-size: 13px; padding: 6px 14px; }
  .banner-slide-content .promo-brand { font-size: 13px; color: rgba(255,255,255,0.75); margin: 0 0 8px; }
  .banner-slide-content .promo-name {
    display: block; -webkit-line-clamp: unset; overflow: visible; min-height: 0;
    font-size: 34px; font-weight: 600; line-height: 1.15; color: #fff;
    max-width: 65%; margin: 0 0 14px;
  }
  .banner-slide-content .promo-price { font-size: 18px; margin: 0 0 22px; }
  .banner-slide-content .promo-price-was { color: rgba(255,255,255,0.6); }
  .banner-slide-content .promo-price-now { color: #fff; font-weight: 600; }
  /* White fill (not the card's dark fill) so the same pill still reads
     clearly against the photo's dark scrim - the one color change is
     for contrast, the shape/case/weight match every other "Visit Shop"
     pill on the site. */
  .banner-slide-content .promo-cta {
    display: inline-block; margin: 0; width: auto;
    font-size: 15px; font-weight: 600;
    padding: 15px 34px; background: #fff; color: #1a1816;
  }
  .banner-slide:hover .promo-cta { background: #f0ede8; }
  .banner-dots { position: absolute; bottom: 18px; right: 24px; z-index: 2; display: flex; gap: 6px; }
  .banner-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.5); border: none; cursor: pointer; padding: 0; }
  .banner-dot.active { background: #fff; }
  @media (max-width: 640px) {
    .banner-carousel { aspect-ratio: 4/3; }
    .banner-slide-content { padding: 22px 20px; }
    .banner-slide-content .promo-name { font-size: 24px; max-width: 85%; }
    .banner-slide-content .promo-price { font-size: 15px; margin-bottom: 14px; }
    .banner-slide-content .promo-cta { font-size: 14px; padding: 11px 24px; }
  }
"""

BANNER_CAROUSEL_JS = """
  // Banner/carousel rotation (2026-09-28) - a single slide is static,
  // no controls; 2+ slides get dot navigation and auto-rotation,
  // paused on hover so a reader isn't fighting the page to read it.
  document.querySelectorAll('.banner-carousel').forEach(function (carousel) {
    var slides = carousel.querySelectorAll('.banner-slide');
    var dots = carousel.querySelectorAll('.banner-dot');
    if (slides.length <= 1) return;
    var current = 0;
    var timer;
    function show(i) {
      current = i;
      slides.forEach(function (s, idx) { s.classList.toggle('active', idx === i); });
      dots.forEach(function (d, idx) { d.classList.toggle('active', idx === i); });
    }
    function next() { show((current + 1) % slides.length); }
    function prev() { show((current - 1 + slides.length) % slides.length); }
    function start() { timer = setInterval(next, 6000); }
    function stop() { clearInterval(timer); }
    dots.forEach(function (d, i) {
      d.addEventListener('click', function () { show(i); stop(); start(); });
    });
    carousel.addEventListener('mouseenter', stop);
    carousel.addEventListener('mouseleave', start);
    // Touch swipe (2026-09-29) - mouseenter/mouseleave above never fire
    // on a touch device, so mobile previously only had dot-tapping and
    // auto-rotation. touchmove decides real swipe intent (horizontal
    // movement clearly exceeding vertical) before preventDefault, so a
    // vertical page scroll starting inside the carousel is untouched.
    var touchStartX = 0, touchStartY = 0, isSwiping = false;
    carousel.addEventListener('touchstart', function (e) {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      isSwiping = false;
      stop();
    }, { passive: true });
    carousel.addEventListener('touchmove', function (e) {
      var dx = e.touches[0].clientX - touchStartX;
      var dy = e.touches[0].clientY - touchStartY;
      if (!isSwiping && Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) isSwiping = true;
      if (isSwiping) e.preventDefault();
    }, { passive: false });
    carousel.addEventListener('touchend', function (e) {
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


def render_banner_carousel(slides_html):
    """
    Dedicated hero unit meant to sit above a page's own grid entirely -
    not one of the grid's own cards. `slides_html` is a list of
    already-rendered slide HTML (any shape); returns "" when empty, so
    callers can always include the result unconditionally. A single
    slide renders with no dots/rotation (nothing to navigate between).
    """
    if not slides_html:
        return ""
    slides = "\n".join(
        f'      <div class="banner-slide{" active" if i == 0 else ""}">{slide}</div>'
        for i, slide in enumerate(slides_html)
    )
    if len(slides_html) > 1:
        dots = "\n".join(
            f'        <button type="button" class="banner-dot{" active" if i == 0 else ""}" data-index="{i}" aria-label="Slide {i + 1}"></button>'
            for i in range(len(slides_html))
        )
        dots_html = f'\n      <div class="banner-dots">\n{dots}\n      </div>'
    else:
        dots_html = ""
    return f'    <div class="banner-carousel">\n{slides}{dots_html}\n    </div>'


# Only page-specific rules here - shared rules (:root, body, home-link,
# h1, .tag, .foot-note) live in /site.css, linked with an absolute path
# below since these pages are nested under /brands/.
PAGE_CSS = """
  main { max-width: 1160px; margin: 0 auto; padding: 48px 20px 60px; }
  .maker-header { text-align: center; margin-bottom: 32px; }
  .eyebrow { font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--text-muted); margin: 0 0 6px; }
  .maker-name { font-size: 18px; font-weight: 500; color: var(--text-secondary); margin: 0 0 12px; }
  .brand-site-link { font-size: 13px; color: var(--text-accent); text-decoration: none; }
  .brand-site-link:hover { text-decoration: underline; }
  /* Real cross-link to Marketplace's Promotions tab (2026-09-28) - only
     rendered when this brand genuinely has a live promotion right now
     (see load_promotions_by_brand/render_brand_page). Quiet pill, not
     a shouty banner - it's a real fact worth surfacing, not an ad. */
  .promo-callout {
    display: inline-flex; align-items: center; gap: 6px; margin-top: 14px;
    font-size: 13px; font-weight: 500; color: var(--text-accent);
    background: var(--surface-1); border: 0.5px solid var(--border);
    border-radius: 999px; padding: 8px 16px; text-decoration: none;
  }
  .promo-callout:hover { background: var(--surface-2); border-color: var(--border-strong); }
  .promo-callout i { font-size: 14px; }
  /* "Where to buy" / "New from X" sections (2026-09-28) - real, free
     facts about a brand (which stockists carry it, what's recently
     added), not the paid richness tier - see project memory,
     enhanced_brand_profile_paid_tier_concept's free/paid split. */
  .brand-section { margin-top: 48px; }
  /* "New from X" sits at the TOP of a maker page, above the full range (and only exists when there is something new) */
  .brand-section--top { margin: 0 0 44px; }
  .brand-section-title {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--text-muted); margin: 0 0 16px;
  }
  .stockist-row { display: flex; flex-wrap: wrap; gap: 10px; }
  .stockist-item {
    display: flex; align-items: center; gap: 8px;
    background: var(--surface-1); border: 0.5px solid var(--border);
    border-radius: 999px; padding: 8px 14px 8px 10px;
    text-decoration: none; color: inherit; font-size: 13px;
  }
  .stockist-item:hover { background: var(--surface-2); border-color: var(--border-strong); }
  .stockist-item img { width: 18px; height: 18px; border-radius: 4px; flex-shrink: 0; }
  .stockist-name { font-weight: 500; }
  .stockist-location { color: var(--text-muted); font-size: 12px; }
  .tags { margin-bottom: 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
  /* Photo + plain caption, not an enclosing card box - the site-wide
     standard confirmed 2026-09-20 (see project memory): border/
     background/sharp corners live on the photo alone, caption text
     sits as plain content below it, matching Creators/the homepage's
     category tiles and work.html's result cards. */
  .card { display: block; text-decoration: none; color: inherit; }
  .card-image {
    aspect-ratio: 1/1; background: var(--surface-1); overflow: hidden;
    border: 0.5px solid var(--border); margin: 0 0 10px; position: relative;
  }
  /* Marks a card as standing in for several same-size color/finish
     variants (see product_card_html's variant_count param) - positioned
     like work.html's own share-btn corner treatment. */
  .variant-badge {
    position: absolute; bottom: 6px; left: 6px; z-index: 1;
    background: rgba(250, 249, 247, 0.9); color: var(--text-secondary);
    font-size: 11px; font-weight: 500; padding: 4px 10px; border-radius: 10px;
    border: 0.5px solid transparent; /* same box as .tag so the two small labels are one height */
  }
  .card-image img { width: 100%; height: 100%; object-fit: cover; }
  .card-image img.contain-fit { object-fit: contain; }
  /* Tecta's own product photography (confirmed live 2026-09-30, user:
     "see if we can crop tecta's images better") consistently frames the
     piece flush against the TOP of a portrait (4:5-ish) canvas with
     empty space left below it (e.g. a chair's backrest starts within a
     few px of y=0, legs/casters end well before the bottom edge) - a
     shape the existing ratio<0.55/>1.8 "contain-fit" safety net doesn't
     catch (these run ~0.7-0.8, not extreme enough), so the default
     center-crop into a square card clips the top of the backrest to
     "gain" cropping empty space at the bottom instead. Scoped to this
     one brand's own page via the [data-brand] attribute on <main> (see
     render_brand_page) rather than changed as this file's own sitewide
     default, since other brands' photography isn't confirmed to share
     this same top-heavy framing. */
  main[data-brand="Tecta"] .card-image img { object-position: top; }
  .card-body { padding: 0; }
  /* Reserves a full 2 lines' height so .card-brand always starts at the
     same row across every card in a grid, regardless of whether a given
     product name wraps to 1 or 2 lines - ported from work.html's own
     fix (2026-09-29), which this shared card markup had never received,
     so every page built from product_card_html() (new.html, brand
     pages, the theme landing pages, makers index) had brand names
     landing at different heights row to row. */
  .card-title-wrap { min-height: 2.6em; display: flex; align-items: flex-start; }
  .card-title {
    font-size: 13px; font-weight: 500; margin: 0; line-height: 1.3;
    display: -webkit-box; -webkit-box-orient: vertical;
    -webkit-line-clamp: 2; line-clamp: 2; overflow: hidden;
  }
  .card-brand {
    font-size: 12px; color: var(--text-secondary); margin: 2px 0 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .maker-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 16px; align-items: start; }
  /* two to a row on a phone (a single 190px-minimum column left the directories one long list) */
  @media (max-width: 640px) { .maker-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } }
""" + MAKER_CARD_CSS + """
  /* font-weight explicit since this class is also used on an <h1> in
     render_makers_index (the homepage's own header carries the same
     rule) - browsers bold headings by default, and this needs to look
     identical to the plain <p> version used everywhere else. */
  .page-tagline { font-size: 13px; font-weight: normal; color: var(--text-secondary); margin: 0 0 32px; }
  .category-intro { font-size: 14px; color: var(--text-secondary); max-width: 640px; margin: 0 0 28px; line-height: 1.6; }
  /* Real body text for crawlers/AI agents, same reasoning as
     Marketplace's own footer-description (2026-09-25, see project
     memory) - makers.html/architects.html/designers.html otherwise go
     straight from an invisible sr-only <h1> into the grid, with no
     visible text on the page at all past the meta description. */
  .footer-description { font-size: 12px; color: var(--text-muted); max-width: 640px; margin: 24px 0 0; line-height: 1.6; }
  .empty-state { font-size: 14px; color: var(--text-muted); text-align: center; padding: 60px 20px; }

  /* --- directory filter (makers.html, architects.html) --- */
  /* Same ask-box look, width (900px via .search-wide) and hero position
     as work.html/the homepage/creators.html, for a search box that
     lands in the identical spot on every page (2026-09-20, see project
     memory) - but this one filters the grid already rendered on the
     page client-side (name/city/category, substring match) rather than
     calling the backend. These pages are "browse who's here," not
     "search what they make," so it isn't wired to search.js's work.html
     redirect at all. */
  .search-wide { width: 100%; max-width: 900px; margin: 0 auto 32px; }
  .ask-box {
    display: flex; align-items: center; gap: 10px;
    background: var(--surface-1); border: 0.5px solid var(--border);
    border-radius: var(--radius); padding: 13px 16px;
  }
  .ask-box i.ti-search { font-size: 18px; color: var(--text-muted); }
  .ask-box input {
    border: none; background: none; outline: none; flex: 1;
    font-size: 15px; color: var(--text-primary); font-family: inherit;
  }
  .ask-box input::placeholder { color: var(--text-muted); }

  /* Breadcrumb - which of the three Creator groups you're browsing,
     always shown, never editable. Landing here directly (a category
     card, or a fresh URL) shows this with an empty input; arriving from
     Creators' own search box ("architects stockholm") shows it next to
     the pre-filled, already-applied "stockholm" filter (added
     2026-09-20, see project memory). Kept out of the <input>'s own
     value on purpose - no card's text literally contains the word
     "architect"/"maker", so baking the category word into the filter
     value itself would silently break every match. */
  /* padding: 7px vertical, not 4px - matches the "Surprise me" chip's
     own vertical padding on the homepage/work.html exactly, so the
     ask-box itself comes out the same overall height everywhere
     (measured live 2026-09-20: both 57px - see project memory). */
  .ask-box-context {
    flex-shrink: 0; font-size: 13px; font-weight: 500; color: var(--text-secondary);
    background: var(--surface-2); border: 0.5px solid var(--border-strong);
    padding: 7px 10px; border-radius: 999px;
  }

  /* Tier filter (makers.html only) - two independent toggle chips, not
     a 3-way tab set with an explicit "All" - clicking an active chip
     again clears it back to showing everyone, which is simpler than a
     bare "All" pill sitting oddly alongside the other two. Same pill
     shape/size as .ask-box-context above for visual consistency with
     the rest of this filter row. */
  .tier-filters { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin: 0 0 28px; }
  .filter-chip {
    font-size: 13px; font-weight: 500; color: var(--text-secondary); font-family: inherit;
    background: var(--surface-2); border: 0.5px solid var(--border-strong);
    padding: 7px 14px; margin: 0; cursor: pointer; border-radius: 999px; white-space: nowrap;
  }
  .filter-chip:hover { border-color: var(--text-muted); }
  .filter-chip.active {
    background: var(--text-primary); color: var(--surface-1); border-color: var(--text-primary);
  }

  /* Explicit, not relying on the browser's default [hidden] styling -
     .maker-card's own `display: block` below has the same specificity
     and comes later in source order, so it would otherwise win and
     leave a "hidden" card visible. */
  [hidden] { display: none !important; }
"""

# The share button's styles live in frontend/work-results.css (the Work page's own stylesheet) between SHARE-BTN
# markers; the maker pages embed that same block so the button looks and works identically there (edit it once).
def _shared_css_block(name):
    css = (Path(__file__).resolve().parent.parent / "frontend" / "work-results.css").read_text()
    return css[css.index(f"/* {name}:START"):css.index(f"/* {name}:END */")]


PAGE_CSS += _shared_css_block("SHARE-BTN") + _shared_css_block("LOAD-MORE")

# Maker pages hold BRAND_CARDS_PER_PAGE cards a page (the type pages' rule: Lighthouse's ~1,400-element limit;
# 60 divides every column count). Page 1 is /brands/<slug>.html, then /brands/<slug>-2.html ... A maker with 60 or
# fewer pieces stays one page. "See more" loads the next batch in place (listing.js); the pager stays in the HTML
# for crawlers and for visitors without JavaScript.
BRAND_CARDS_PER_PAGE = 60

LISTING_CONTROLS_CSS = """
  .pager { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 28px 0 8px; }
  .pager a, .pager span {
    min-width: 38px; padding: 8px 12px; text-align: center; font-size: 14px;
    border: 0.5px solid var(--border); border-radius: 8px; text-decoration: none; color: var(--text-secondary);
  }
  .pager a:hover { color: var(--text-primary); border-color: var(--text-muted); }
  .pager span.current { color: var(--text-primary); border-color: var(--text-secondary); font-weight: 600; }
  .pager .gap { border: 0; min-width: 0; padding: 8px 2px; color: var(--text-muted); }
  .has-load-more .pager { display: none; }
  .earlier-results { display: none; margin: 0 0 14px; font-size: 13px; }
  .has-load-more .earlier-results { display: block; }
  .earlier-results a { color: var(--text-muted); text-decoration: none; }
  .earlier-results a:hover { color: var(--text-primary); text-decoration: underline; }
"""
PAGE_CSS += LISTING_CONTROLS_CSS


# The share button markup (one definition; styles: work-results.css SHARE-BTN block, behaviour: share.js).
SHARE_BTN_HTML = ('<button class="share-btn" type="button" aria-label="Share this piece">'
                  '<i class="ti ti-share-2" aria-hidden="true"></i></button>')


def brand_page_slug(slug, page):
    return slug if page == 1 else f"{slug}-{page}"


def listing_pager_html(url_for, page, pages):
    """1 2 3 ... 14 Next: first, last and the pages around the current one. `url_for(n)` is page n's address.
    Real links, so every page is crawlable (shared by the type pages and the maker pages)."""
    if pages <= 1:
        return ""
    shown = sorted({1, pages} | {n for n in range(page - 1, page + 2) if 1 <= n <= pages})
    items = []
    if page > 1:
        items.append(f'<a href="{url_for(page - 1)}" rel="prev">&larr; Prev</a>')
    last = 0
    for n in shown:
        if n - last > 1:
            items.append('<span class="gap" aria-hidden="true">&hellip;</span>')
        items.append(f'<span class="current" aria-current="page">{n}</span>' if n == page else f'<a href="{url_for(n)}">{n}</a>')
        last = n
    if page < pages:
        items.append(f'<a href="{url_for(page + 1)}" rel="next">Next &rarr;</a>')
    return f'<nav class="pager" aria-label="Pages">{"".join(items)}</nav>'


def listing_controls_html(url_for, page, pages, total, noun):
    """(earlier-results link, See more row, pager) for one page of a paged listing."""
    earlier = (f'<p class="earlier-results"><a href="{url_for(page - 1)}" rel="prev">&larr; Earlier results</a></p>'
               if page > 1 else "")
    see_more = ""
    if page < pages:
        see_more = (f'<div class="load-more-row"><a class="load-more-btn" id="see-more" data-total="{total}" '
                    f'data-start="{(page - 1) * BRAND_CARDS_PER_PAGE}" href="{url_for(page + 1)}">See more {html.escape(noun)}</a>'
                    f'<span class="load-more-progress" id="see-more-progress"></span></div>')
    return earlier, see_more, listing_pager_html(url_for, page, pages)


def directory_filter_html(placeholder, category_label):
    return f"""
  <div class="search-wide">
    <div class="ask-box">
      <i class="ti ti-search" aria-hidden="true"></i>
      <span class="ask-box-context">{html.escape(category_label)}</span>
      <input id="directory-filter" type="text" placeholder="{placeholder}" autocomplete="off">
    </div>
  </div>"""


def tier_filter_html():
    """
    makers.html only - see load_brand_tiers() for what "established"
    means and how a brand gets it. Independent is listed first since
    it's the default/norm, not the exception.
    """
    return """
  <div class="tier-filters">
    <button type="button" class="filter-chip" data-tier="independent">Independent Makers</button>
    <button type="button" class="filter-chip" data-tier="established">Established Makers</button>
  </div>"""


# Overrides PAGE_CSS's own `main` (padding-top: 48px, tuned for brand/
# profile pages with no search box) and site.css's shared `.site-header`
# margin-bottom (40px) - later in source order wins at equal
# specificity, so this lands the filter box at the exact same position
# as work.html/the homepage/creators.html (2026-09-20, see project
# memory) without touching either shared rule for the pages that still
# want their own spacing.
HERO_SEARCH_POSITION_CSS = """
  main { padding-top: 24px; }
  .site-header { margin-bottom: 0; }
"""


# Plain substring match against each card's own text (name/city/category
# tags) - no fuzzy matching, no ranking, consistent with the rest of the
# site's "no algorithm, just real filtering" convention. Cards are
# hidden with the native [hidden] attribute - PAGE_CSS's own
# `[hidden] { display: none !important; }` rule (added alongside this)
# is what actually makes that stick, since without it .maker-card's own
# `display: block` (same specificity, later in source order) would win
# over the browser's default [hidden] styling and the card would stay
# visible.
DIRECTORY_FILTER_JS = """
  (function () {
    var filterInput = document.getElementById("directory-filter");
    // Tier chips only exist on makers.html - an empty NodeList here on
    // architects.html (which shares this same script) just means
    // activeTier never leaves null, so tierMatch below is always true
    // and nothing changes for that page.
    var tierButtons = document.querySelectorAll(".filter-chip[data-tier]");
    var activeTier = null;
    function applyFilter(q) {
      q = q.trim().toLowerCase();
      // .promo-card covers both promo-grid card shapes (a plain <a> for
      // a single offer, a <div class="promo-card promo-card-grouped">
      // for 2+ offers) - matched by class, not tag, since the grouped
      // shape isn't itself a link (see generate_marketplace_page.py's
      // _promo_card). Marketplace's search box claims to search
      // "stockists and promotions" but this used to only ever query
      // .maker-grid > a, so Promotions cards were never actually
      // filtered (2026-09-28 finding).
      document.querySelectorAll(".maker-grid > a, .promo-card").forEach(function (card) {
        var textMatch = !q || card.textContent.toLowerCase().includes(q);
        var tierMatch = !activeTier || card.dataset.tier === activeTier;
        card.hidden = !(textMatch && tierMatch);
      });
    }
    filterInput.addEventListener("input", function (e) { applyFilter(e.target.value); });
    // Each chip toggles independently - clicking the already-active one
    // clears back to showing every tier, clicking the other one swaps
    // which tier is active (a card can only ever be one or the other,
    // so having both active at once would just mean "all" again).
    tierButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tier = btn.dataset.tier;
        if (activeTier === tier) {
          activeTier = null;
          btn.classList.remove("active");
        } else {
          activeTier = tier;
          tierButtons.forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
        }
        applyFilter(filterInput.value);
      });
    });
    // Pre-filled from Creators' own search box (?q=stockholm after it
    // strips "architects"/"designers"/"makers" off the front and routes
    // here) - runs the exact same filter immediately, not just on the
    // next keystroke, so landing here already shows the real results
    // rather than the unfiltered full list (2026-09-20, see project
    // memory).
    var presetQuery = new URLSearchParams(window.location.search).get("q");
    if (presetQuery) {
      filterInput.value = presetQuery;
      applyFilter(presetQuery);
    }
  })();
"""


# One shared click-tracking script, included on every generated page
# that has any of these three link shapes, so a brand-new page type
# gets real analytics for free just by importing this constant the same
# way it already imports PAGE_CSS/CLOUDFLARE_ANALYTICS - no per-page
# tracking code to remember to write (2026-09-24, prompted by an audit
# finding almost none of the site's cards were tracked at all: every
# product card on every one of the ~9,300-product brand/new pages,
# every architect/designer/craftsperson card, every "Visit site" link).
#
# Only fires for a genuinely EXTERNAL destination (a different hostname
# than formground.com) - a card linking to another page on this same
# site (an index card to a profile page, say) is not a new signal,
# Cloudflare's own pageview analytics already sees that page load.
#
# Brand/product-name extraction has to handle two real, different card
# shapes rather than one:
#   .card (product cards - brand pages, new.html): .card-title is
#     always the product; .card-brand is only present when the grid
#     mixes brands (new.html) - a single-brand page's own product grid
#     has no .card-brand at all, so it falls back to the page's own
#     .maker-header .maker-name heading (the brand this whole page IS).
#   .maker-card (entity cards - every index page, AND the sub-item
#     grids inside an individual firm/designer's own page) - .maker-name
#     means something different depending on which of those two it is:
#     on an index page it's the entity's own name (the "brand"); inside
#     an individual page's sub-item grid (a firm's houses, a designer's
#     credited products) it's that specific item's name (the "product"),
#     with the real brand living at the page level instead. Checking for
#     a page-level .maker-header first is what tells these two apart -
#     an index page never has one (see generate_*_pages.py's own
#     sr-only <h1> on those), so its presence/absence is a reliable
#     signal for which shape a given .maker-card click actually is.
#   .brand-site-link (a bare "Visit site" link, no inner name/meta of
#     its own) - always attributed to the page-level brand, if any.
CARD_CLICK_TRACKING_JS = """
  (function () {
    // The tracking itself (page views, click-throughs, landing-page and
    // campaign carry-over) lives in ONE shared file, /fg-track.js, instead
    // of being pasted into hundreds of generated pages - see that file and
    // backend/analytics.py for what is logged.
    var s = document.createElement("script");
    s.src = "/fg-track.js";
    s.async = true;
    document.head.appendChild(s);
  })();
"""


def _brand_stockist_item(name, locations):
    website = locations[0]["website"]
    domain = urlparse(website).netloc.removeprefix("www.")
    favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=64" if domain else None
    icon_html = (
        f'<img src="{html.escape(favicon)}" alt="" loading="lazy" onerror="this.remove();">'
        if favicon else ""
    )
    if len(locations) == 1:
        loc = locations[0]
        city, country = loc.get("city", ""), loc.get("country", "")
        location_line = f"{city}, {country}" if city and country else (city or country or "Online retailer")
    else:
        countries = {loc.get("country", "") for loc in locations if loc.get("country")}
        location_line = (
            f"{len(locations)} locations in {countries.pop()}" if len(countries) == 1
            else f"{len(locations)} locations across {len(countries)} countries"
        )
    return f"""      <a class="stockist-item" href="{html.escape(website)}" target="_blank" rel="noopener noreferrer">
        {icon_html}<span class="stockist-name">{html.escape(name)}</span>
        <span class="stockist-location">{html.escape(location_line)}</span>
      </a>"""


def render_stockist_section(brand, stockist_groups):
    """
    "Where to buy" - a real, free fact (which real stockists carry this
    brand today), not a paid enhancement - see load_stockists_by_brand
    and project memory, enhanced_brand_profile_paid_tier_concept's
    free/paid organizing principle. Returns "" when there's nothing to
    show, so callers can include it unconditionally.
    """
    if not stockist_groups:
        return ""
    items = "\n".join(_brand_stockist_item(name, locations) for name, locations in stockist_groups)
    return f"""
  <section class="brand-section">
    <p class="brand-section-title">Where to buy {html.escape(brand)}</p>
    <div class="stockist-row">
{items}
    </div>
  </section>"""


def render_news_section(brand, new_products):
    """
    "News" - an auto-generated activity feed built from real data
    Formground already tracks (first_seen, the same signal powering the
    sitewide New Arrivals page - see NEW_ARRIVALS_WINDOW_DAYS), not
    brand-authored editorial content. Resolved this way deliberately
    (see project memory, enhanced_brand_profile_paid_tier_concept,
    "option 2") since a manually-written news feed would create ongoing
    admin work for the brand - the same thing already avoided for
    Promotions' taglines and For Creators' "highlight" field. Returns
    "" when this brand has nothing new within the window - genuinely
    empty is expected, not a bug, same as the sitewide New page.
    """
    if not new_products:
        return ""
    # Capped (2026-09-28) - checked live and found some brands (e.g.
    # HAY: 639 of 639 products) have their ENTIRE catalog flagged
    # "new" within the window, almost certainly a stale first_seen
    # backfill artifact from whenever this column was introduced, not
    # real signal. Uncapped, "News" would just be a redundant copy of
    # the whole product grid for those brands. new_products is already
    # sorted most-recent-first by the caller, so this keeps the
    # genuinely newest items regardless of how many technically qualify.
    cards = "".join(product_card_html(p, share=True) for p in new_products[:NEW_SECTION_CAP])
    return f"""
  <section class="brand-section brand-section--top">
    <p class="brand-section-title">New from {html.escape(brand)}</p>
    <div class="grid">{cards}</div>
  </section>"""


def render_brand_page(brand, slug, brand_url, products, umbrellas, country=None, promotions=None, stockists=None, new_products=None, page=1):
    tag_list = list(umbrellas) + ([country] if country else [])
    tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tag_list)
    # Real, live cross-link to Marketplace's Promotions tab (2026-09-28,
    # see load_promotions_by_brand) - only rendered when this brand
    # genuinely has 1+ live promotion right now, using the same
    # best-offer-wins-the-headline logic as the Promotions cards
    # themselves. ?tab=promotions lands directly on the right tab
    # rather than Marketplace's own default (Stockists).
    promo_callout = ""
    if promotions and not site_sections.is_hidden("promotions"):   # the callout links to Marketplace Promotions
        best_discount = max(
            (o.get("discount_pct") or 0) for p in promotions for o in p["offers"]
        )
        count = len(promotions)
        label = f"{count} live promotions" if count > 1 else "a live promotion"
        discount_note = f", up to {best_discount}% off" if best_discount else ""
        promo_callout = (
            '\n    <a class="promo-callout" href="/marketplace.html?tab=promotions">'
            f'<i class="ti ti-tag" aria-hidden="true"></i> {html.escape(brand)} has {label} right now'
            f'{discount_note} &rarr;</a>'
        )
    pages = max(1, -(-len(products) // BRAND_CARDS_PER_PAGE))
    page_products = products[(page - 1) * BRAND_CARDS_PER_PAGE: page * BRAND_CARDS_PER_PAGE]
    url_for = lambda n: f"/brands/{brand_page_slug(slug, n)}.html"
    earlier_html, see_more_html, pager_html = listing_controls_html(url_for, page, pages, len(products), "pieces")
    cards = "".join(product_card_html(p, share=True) for p in page_products)
    news_section = render_news_section(brand, new_products) if page == 1 else ""
    all_work_title = f'  <p class="brand-section-title">All of {html.escape(brand)}</p>\n' if news_section else ""
    stockist_section = "" if site_sections.is_hidden("maker_stockists") else render_stockist_section(brand, stockists)
    page_url = f"{SITE_URL}/brands/{brand_page_slug(slug, page)}.html"
    page_note = f" (page {page} of {pages})" if pages > 1 else ""
    pg = f", page {page}" if page > 1 else ""
    kinds = list_phrase([u.lower() for u in umbrellas]) if umbrellas else ""
    seo_title = fit_title(*([f"{brand}: {kinds}{pg}"] if kinds else []), f"{brand} products{pg}", f"{brand}{pg}")
    description = f"{html.escape(brand)}'s work on Formground - {len(products)} pieces{page_note}, linked straight to their own site."
    # Social preview: the one default Formground image, not the maker's own
    # photo - we don't have the maker's permission to use their images as
    # our preview card (decision 2026-10-05).
    og_image_tags = (
        f'<meta property="og:image" content="{SITE_URL}/og-default.png">\n'
        '<meta property="og:image:width" content="1200">\n'
        '<meta property="og:image:height" content="630">\n'
        f'<meta name="twitter:image" content="{SITE_URL}/og-default.png">\n'
    )
    twitter_card_type = "summary_large_image"
    # BreadcrumbList (Home -> Makers -> this brand) - cheap, accurate
    # structured data with a real shot at a rich-result breadcrumb in
    # search results. Deliberately no Product/price schema here: we
    # don't have reliable real-time price/availability data, and
    # claiming it would overstate what's really just a thumbnail-and-
    # link-back model (see the project's own fair-use grounding).
    breadcrumb_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Formground", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Makers", "item": f"{SITE_URL}/makers.html"},
            {"@type": "ListItem", "position": 3, "name": brand, "item": f"{SITE_URL}/brands/{slug}.html"},
        ],
    })
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(seo_title)}</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(seo_title)}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
{og_image_tags}<meta name="twitter:card" content="{twitter_card_type}">
<meta name="twitter:title" content="{html.escape(seo_title)}">
<meta name="twitter:description" content="{description}">
<script type="application/ld+json">{breadcrumb_json}</script>
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("creators")}
</header>
<main data-brand="{html.escape(brand)}">
  <div class="maker-header">
    <p class="eyebrow">Maker</p>
    <h1 class="maker-name">{html.escape(brand)}</h1>
    <div class="tags">{tags}</div>
    <a class="brand-site-link" href="{html.escape(brand_url)}" target="_blank" rel="noopener noreferrer">Visit site &rarr;</a>{promo_callout}
  </div>
{news_section}{all_work_title}  {earlier_html}
  <div class="grid" data-listing-grid>{cards}</div>
  {see_more_html}
  {pager_html}
{stockist_section}
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>
  // Same fix as render_makers_index's own script (added there first,
  // confirmed on Magis's "Déjà-vu" - see project memory), but never
  // carried over to this per-brand page's own product grid, which
  // uses the exact same .card-image aspect-ratio: 1/1 + object-fit:
  // cover treatment: a tall/narrow product photo (confirmed live on
  // several of Magis's own WordPress thumbnails, natively ~172x300)
  // loses most of its content to the crop instead of just being
  // letterboxed. Switches to "contain" once the real aspect ratio is
  // known to be this extreme.
  document.querySelectorAll(".card-image img").forEach(function (img) {{
    img.addEventListener("load", function () {{
      var ratio = img.naturalWidth / img.naturalHeight;
      if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
    }});
  }});
</script>
<script>{CARD_CLICK_TRACKING_JS}</script>
<script src="{SHARE_JS}" defer></script>
<script src="{LISTING_JS}" defer></script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def render_makers_index(brands_data):
    # Deliberately no product count here - "brand is the minimum unit
    # of inclusion", equal weight regardless of catalog size, is a
    # core principle elsewhere on the site (dashed-border cards, no
    # ranking by data richness) - showing "(1 piece)" next to
    # "(261 pieces)" on the one page listing every maker side by side
    # would visually undercut that. One hero image per brand (see
    # primary_image_for) doesn't leak catalog size either. Name /
    # country / categories are each their own row - reviewed live
    # against the previous mixed single-line version (categories and
    # country run together) before settling on this split, since it
    # keeps every card's text block the same shape regardless of
    # whether a country is confirmed or how many categories a brand
    # covers, rather than a line that's sometimes long and sometimes
    # short.
    items = ""
    for brand, slug, umbrellas, _count, country, image, tier in sorted(brands_data, key=lambda b: b[0].lower()):
        categories = " · ".join(umbrellas)
        country_html = html.escape(country) if country else "&nbsp;"
        image_tag = f'<img src="{html.escape(sized(image, CARD))}" alt="{html.escape(brand)}" loading="lazy">' if image else ""
        items += f"""
      <a class="maker-card" href="/brands/{slug}.html" data-tier="{tier}">
        <div class="maker-card-hero">{image_tag}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(brand)}</span>
          <span class="maker-country">{country_html}</span>
          <span class="maker-categories">{html.escape(categories)}</span>
        </div>
      </a>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Makers of furniture, lighting and objects — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="Every maker on Formground, browsable by name: independent and established makers of furniture, lighting and objects, each linked to their own site.">
<link rel="canonical" href="https://formground.com/makers.html">
<meta property="og:type" content="website">
<meta property="og:title" content="Makers of furniture, lighting and objects — Formground">
<meta property="og:description" content="Every maker on Formground, browsable by name: independent and established makers of furniture, lighting and objects, each linked to their own site.">
<meta property="og:url" content="https://formground.com/makers.html">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Makers — Formground">
<meta name="twitter:description" content="Every maker currently on Formground, browsable by name.">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}</style>
<style>{HERO_SEARCH_POSITION_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("creators")}
</header>
<main style="max-width:1160px;">{directory_filter_html("Filter by name, city, or category…", "Makers")}{tier_filter_html()}
  <h1 class="sr-only">Makers</h1>
  <div class="maker-grid">{items}
  </div>
  <p class="footer-description">Formground promotes a curated selection of makers, new and established, to be discovered. If you'd like to be featured, <a href="/contact.html">get in touch here</a>.</p>
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>
  // Same fix as frontend/index.html's renderCard(): a single image
  // stretched across this row's full width can lose most of a tall/
  // narrow product photo under object-fit: cover (an even more
  // aggressive crop than the 1:1 search-card case that first surfaced
  // this - see Magis "Déjà-vu"). Switches to "contain" once the real
  // aspect ratio is known to be this extreme.
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


# Retired 2026-09-20: these 4 slugs used to be full, indexable
# brand-listing pages (one per umbrella category). Checked first - not
# indexed by Google despite being live for weeks, no internal links to
# them from anywhere but the homepage tiles, and no unique content that
# work.html?q=<slug> doesn't already surface (see project memory).
# Kept only as this list, so the redirect stubs below still exist at
# their old URLs for anyone with a bookmark or old link.
RETIRED_CATEGORY_SLUGS = ["furniture", "lighting", "ceramics", "objects"]


# Where each retired category address goes now (2026-10-04: the three category pages under /work/).
RETIRED_CATEGORY_TARGETS = {
    "furniture": "/work/furniture.html",
    "lighting": "/work/lighting.html",
    "objects": "/work/objects.html",
    "ceramics": "/work/objects.html",
}


def render_category_redirect_stub(slug):
    """A redirect stub at the old docs/{slug}.html URL (see redirects.py), so an old
    bookmark or inbound link still lands on the matching /work/ category page."""
    from redirects import render_redirect
    return render_redirect(RETIRED_CATEGORY_TARGETS[slug])


# How far back "recently added" reaches before a piece rolls off the
# page - keeps this from slowly turning into a second full catalog as
# first_seen dates accumulate over months. Purely a display window;
# nothing is ever deleted from the database because of it.
NEW_ARRIVALS_WINDOW_DAYS = 90

# Caps a brand page's own "News" section (see render_news_section) -
# some brands (e.g. HAY: 639 of 639 products, confirmed live 2026-09-28)
# have their entire catalog flagged "new" within the window above,
# almost certainly a stale first_seen backfill artifact rather than
# real signal. Uncapped, the section would just duplicate the whole
# product grid for those brands.
NEW_SECTION_CAP = 6


def render_new_page(products):
    """
    products is already filtered (first_seen within
    NEW_ARRIVALS_WINDOW_DAYS, hidden brands excluded) and sorted most-
    recent-first by the caller (generate()) - this function only
    renders.

    Genuinely empty on a normal day is expected, not a bug: first_seen
    only gets a real date the first time a product is detected as new
    to its brand's catalog since the previous scrape (see scrape.py's
    run()) - nothing already in the catalog before this feature existed
    was backfilled with a guessed date, so this page starts empty on
    rollout and fills in gradually, one weekly scrape at a time.
    """
    page_url = f"{SITE_URL}/new.html"
    if products:
        n = len(products)
        description = (
            f"{n} piece{'s' if n != 1 else ''} newly added to Formground in the last "
            f"{NEW_ARRIVALS_WINDOW_DAYS} days, from makers - every result "
            "links straight to the maker's own site."
        )
    else:
        description = "Recently added pieces from makers on Formground, updated as new work is found."

    if products:
        cards = "".join(product_card_html(p, show_brand=True) for p in products)
        body = f'<div class="grid">{cards}</div>'
    else:
        body = '<p class="empty-state">Check back soon - new pieces are added here as they are found.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>New work from makers — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="New work from makers — Formground">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="New — Formground">
<meta name="twitter:description" content="{description}">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline">Discover design from makers.</p>
  <h1>Recently added</h1>
  <p class="category-intro">Pieces newly added to Formground, most recent first - updated as new work is found, roughly weekly rather than in real time.</p>
  {body}
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>
  // Same fix as render_brand_page/render_makers_index's own script
  // (see project memory) - this page's cards come from the same
  // product_card_html()/.card-image markup, so it needs the same
  // aspect-ratio safety net.
  document.querySelectorAll(".card-image img").forEach(function (img) {{
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


def _architects_sitemap_slugs():
    """Same self-healing rationale as _craftspeople_sitemap_slugs() -
    reads data/houses.json directly so render_sitemap() stays correct
    regardless of which generator last ran. A firm gets a page only if
    it has at least one real house in houses.json (see
    generate_architects_pages.py) - updated 2026-09-19 from the old
    "has any representative photo" filter when the house-as-product
    rebuild narrowed the real roster from 14 firms to 8; a sitemap
    generated against the old filter would keep listing (and letting
    search engines crawl) pages that no longer exist on disk."""
    path = DATA_DIR / "houses.json"
    if not path.exists():
        return []
    houses = json.loads(path.read_text())
    firm_names = {h["firm"] for h in houses}
    slugs_seen = {}
    slugs = []
    for name in sorted(firm_names):  # same sorted order + unique_slug as generate_architects_pages.py
        slug = unique_slug(slugify(name), name, slugs_seen)
        slugs_seen[slug] = name
        slugs.append(slug)
    return sorted(slugs)


def _designers_with_counts():
    """[(slug, product count)] for every designer who gets a page (2+ credited products - see
    generate_designers_pages.py's MIN_PRODUCTS), in the same sorted order and with the same unique_slug as that
    generator. Reads data/formground.db directly (the real source, no separate JSON file) so render_sitemap()
    stays correct regardless of which generator last ran."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT designer, COUNT(*) as n FROM products
        WHERE designer IS NOT NULL AND TRIM(designer) != '' AND image_url != ''
        GROUP BY designer
    """).fetchall()
    conn.close()
    # credits are split into the individual designers they name (designer_credits.py), then the 2+ bar applies
    rows = [(name, n) for name, n in credited_counts(rows).items() if n >= 2]
    slugs_seen = {}
    out = []
    for name, n in sorted(rows, key=lambda r: r[0]):
        slug = unique_slug(slugify(name), name, slugs_seen)
        slugs_seen[slug] = name
        out.append((slug, n))
    return out


def _designers_sitemap_slugs():
    return sorted(slug for slug, _ in _designers_with_counts())


def _designers_extra_page_slugs():
    """/designers/<slug>-2.html ... for designers with more than one page of products (60 a page)."""
    return [brand_page_slug(slug, page) for slug, n in _designers_with_counts()
            for page in range(2, -(-n // BRAND_CARDS_PER_PAGE) + 1)]


def update_creators_hub_counts(n_makers, n_designers, n_architects):
    """The three counts on the Creators page (hand-written, so they went stale: it said 17 firms, 42 designers,
    179 brands when the site had 43, 228 and 198). Rewritten from the real page lists on every run."""
    for folder in (FRONTEND_DIR, DOCS_DIR):
        path = folder / "creators.html"
        if not path.exists():
            continue
        text = path.read_text()
        new = re.sub(r'(<p class="group-count">)\d[\d,]* firms?(</p>)', rf"\g<1>{n_architects:,} firms\g<2>", text)
        new = re.sub(r'(<p class="group-count">)\d[\d,]* designers?(</p>)', rf"\g<1>{n_designers:,} designers\g<2>", new)
        new = re.sub(r'(<p class="group-count">)\d[\d,]* brands?(</p>)', rf"\g<1>{n_makers:,} brands\g<2>", new)
        if new != text:
            path.write_text(new)


def render_sitemap(brand_slugs):
    # lastmod is only set on the pages this script itself regenerates
    # every run (makers.html, brand pages) - their content can genuinely
    # change on any given run, so "today" is a real signal, not a gamed
    # one. The hand-maintained pages (homepage, about, contact) aren't
    # touched by this script, so they're left without lastmod rather
    # than given a date that doesn't reflect when they actually changed
    # - a wrong lastmod is worse than none, since search engines
    # discount sitemaps whose freshness signal turns out to be fake.
    today = datetime.date.today().isoformat()
    urls = [
        ("https://formground.com/", "weekly", "1.0", None),
        ("https://formground.com/work.html", "weekly", "0.8", None),
        ("https://formground.com/creators.html", "weekly", "0.7", None),
        ("https://formground.com/about.html", "monthly", "0.6", None),
        ("https://formground.com/contact.html", "monthly", "0.5", None),
        ("https://formground.com/for-creators.html", "monthly", "0.4", None),
        ("https://formground.com/privacy.html", "yearly", "0.2", None),
        ("https://formground.com/makers.html", "weekly", "0.7", today),
    ]
    urls.append(("https://formground.com/marketplace.html", "weekly", "0.5", None))
    urls += [(f"https://formground.com/brands/{slug}.html", "weekly", "0.5", today) for slug in brand_slugs]
    designer_slugs = _designers_sitemap_slugs()
    if designer_slugs:
        urls.append(("https://formground.com/designers.html", "weekly", "0.7", today))
        urls += [
            (f"https://formground.com/designers/{slug}.html", "weekly", "0.5", today)
            for slug in sorted(designer_slugs + _designers_extra_page_slugs())
        ]
    architect_slugs = _architects_sitemap_slugs()
    if architect_slugs:
        urls.append(("https://formground.com/architects.html", "weekly", "0.7", today))
        urls += [
            (f"https://formground.com/architects/{slug}.html", "weekly", "0.5", today)
            for slug in architect_slugs
        ]
    entries = []
    for loc, freq, pri, lastmod in urls:
        lastmod_tag = f"\n    <lastmod>{lastmod}</lastmod>" if lastmod else ""
        entries.append(
            f"  <url>\n    <loc>{loc}</loc>{lastmod_tag}\n    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>"
        )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{chr(10).join(entries)}\n</urlset>\n'


def generate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM products WHERE image_url != '' ORDER BY product_name"
    ).fetchall()
    conn.close()

    by_brand = {}
    for row in rows:
        by_brand.setdefault(row["brand"], []).append(dict(row))

    countries = load_countries()
    hidden_brands = load_hidden_brands()
    tiers = load_brand_tiers()
    promotions_by_brand = load_promotions_by_brand()
    stockists_by_brand = load_stockists_by_brand()
    BRANDS_DIR.mkdir(parents=True, exist_ok=True)

    # New-arrivals page: first_seen is only ever real (not NULL) for a
    # product genuinely detected as new since the previous scrape (see
    # scrape.py's run()) - a pre-existing product's unknown real add-
    # date was never guessed at, so this naturally excludes everything
    # already in the catalog before the feature existed rather than
    # needing a separate check here.
    # "New" (2026-10-04) = new from the maker - released_at within the window, or, for a maker whose platform
    # exposes no date, first seen well after our first scan of that maker (query_engine.is_new_piece). The brand
    # page's own "New from X" shows the same pieces the sitewide New pages count.
    new_arrivals = sorted(
        (dict(row) for row in rows
         if row["brand"] not in hidden_brands and qe.is_new_piece(dict(row))),
        key=lambda p: p.get("released_at") or p["first_seen"] or "",
        reverse=True,
    )
    # /new.html is now a redirect to /work/new.html, written by generate_browse_pages.py (2026-10-04)

    # Reuses the exact same filtered/sorted new_arrivals list the
    # sitewide New page just wrote, sliced per brand for each brand
    # page's own "News" section (see render_news_section) - one query,
    # not a second pass over the database.
    new_arrivals_by_brand = {}
    for p in new_arrivals:
        new_arrivals_by_brand.setdefault(p["brand"], []).append(p)

    slugs_seen = {}
    makers_data = []
    extra_page_slugs = []      # /brands/<slug>-2.html ... for makers with more than one page of pieces
    # Drop the numbered pages a previous run wrote (a maker that shrank must not leave an orphaned -4 page behind).
    _brand_slugs_now = {slugify(b) for b in by_brand}
    for old_page in BRANDS_DIR.glob("*-[0-9]*.html"):
        base = re.sub(r"-\d+$", "", old_page.stem)
        if base in _brand_slugs_now and old_page.stem not in _brand_slugs_now:
            old_page.unlink()
    for brand, products in by_brand.items():
        slug = slugify(brand)
        # Extremely unlikely at current scale, but two brands could
        # theoretically slugify to the same string - keep pages from
        # silently overwriting each other rather than assume it can't happen.
        if slug in slugs_seen and slugs_seen[slug] != brand:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = brand

        if brand in hidden_brands:
            # No page, no makers.html entry, no sitemap entry - and
            # delete any page generated before this brand was hidden,
            # rather than leave a stale file still reachable by anyone
            # with the old URL.
            (BRANDS_DIR / f"{slug}.html").unlink(missing_ok=True)
            continue

        brand_url = products[0]["brand_url"]
        umbrellas = umbrella_categories_for(products)
        country = countries.get(brand)
        page = render_brand_page(
            brand, slug, brand_url, products, umbrellas, country,
            promotions_by_brand.get(brand),
            stockists_by_brand.get(brand),
            new_arrivals_by_brand.get(brand),
        )
        (BRANDS_DIR / f"{slug}.html").write_text(page)
        brand_pages = max(1, -(-len(products) // BRAND_CARDS_PER_PAGE))
        for extra in range(2, brand_pages + 1):
            (BRANDS_DIR / f"{brand_page_slug(slug, extra)}.html").write_text(render_brand_page(
                brand, slug, brand_url, products, umbrellas, country, promotions_by_brand.get(brand),
                stockists_by_brand.get(brand), new_arrivals_by_brand.get(brand), page=extra))
            extra_page_slugs.append(brand_page_slug(slug, extra))
        image = primary_image_for(products, umbrellas)
        tier = tiers.get(brand, "independent")
        makers_data.append((brand, slug, umbrellas, len(products), country, image, tier))

    (DOCS_DIR / "makers.html").write_text(render_makers_index(makers_data))
    for slug in RETIRED_CATEGORY_SLUGS:
        (DOCS_DIR / f"{slug}.html").write_text(render_category_redirect_stub(slug))
    (DOCS_DIR / "sitemap.xml").write_text(render_sitemap(sorted([m[1] for m in makers_data] + extra_page_slugs)))
    update_creators_hub_counts(len(makers_data), len(_designers_sitemap_slugs()), len(_architects_sitemap_slugs()))

    print(f"Generated {len(makers_data)} brand pages, makers.html, "
          f"{len(RETIRED_CATEGORY_SLUGS)} retired-category redirect stubs, "
          f"new.html ({len(new_arrivals)} new arrival{'s' if len(new_arrivals) != 1 else ''}), "
          f"and sitemap.xml ({sum(m[3] for m in makers_data)} products total).")


if __name__ == "__main__":
    generate()
