"""
Formground "Work by type" page generator (was "Browse", /browse/).

WHAT THIS DOES: generates uncapped, paginated, static type pages
(docs/work/{slug}.html, {slug}-2.html, ...) - one page per product TYPE
("Table Lamps", "Sofas"), listing every real match, not a curated 12 - plus
the three category pages (docs/work/furniture.html, lighting.html,
objects.html) and the "browse by type" menu (work_menu.py) that it writes
into the Work page itself.

MOVED 2026-10-04: these pages used to live at /browse/ (and Floor Lamps at
/floor-lamps.html). They are now /work/<type>.html under the Work nav item,
Edits moved to /edits/, and every old address is a redirect stub (redirects.py)
written by this script and generate_themed_edit_pages.py. Structure and reasons:
project-docs/Site_Patterns.md.

WHY THIS EXISTS (2026-10-02, agentic/organic findability review): the
catalog was reachable by crawlers only through brand pages. Work is a
JavaScript-fetched query UI with no stable URLs, the furniture/
lighting/ceramics/objects umbrella pages are noindex redirect stubs,
and the themed Edits (capped at MAX_PRODUCTS_PER_EDIT) are deliberately
a curated pick, not the category. So "find me a pendant lamp" had no
static entry point at all except Floor Lamps. These pages are that
entry point - same filter_products() call Work itself uses, so they
cannot drift from what search returns.

SCOPE: tiers A (ad-keyword categories) and C (other lighting) from the
scoping pass: table lamps, pendant lamps, dining tables, coffee tables,
sofas, wall lamps, ceiling lamps, chandeliers. The remaining tiers
(other furniture, soft furnishings, ceramics/objects) reuse this same
list - add an entry to BROWSE_CATEGORIES and re-run.

Under /work/ (not the site root) because pendant-lamps, table-lamps,
wall-lamps and ceiling-lamps were also the names of the capped Edit pages;
Edits now live under /edits/, so the same name never means two things.

ORDERING: deterministic brand round-robin (one product per brand per
pass, brands alphabetical), NOT query_engine.round_robin_order(), which
randomizes - a static page that reshuffles on every rebuild would churn
every diff and move products between pages. Interleaving is the same
"brand is the minimum unit of inclusion" principle search applies; a
size-ordered list would put the biggest catalog (Serax, Seletti) first.

RUN (after generate_brand_pages.py - needs sitemap.xml - and before
generate_themed_edit_pages.py, whose pages link here):
    python3 generate_browse_pages.py
"""

import html
import json
import math
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
BROWSE_DIR = DOCS_DIR / "work"          # type + category pages live under /work/ (moved from /browse/ 2026-10-04)
OLD_BROWSE_DIR = DOCS_DIR / "browse"    # now only redirect stubs
BACKEND_DIR = SCRAPER_DIR.parent / "backend"
DATA_DIR = SCRAPER_DIR.parent / "data"

# Houses (2026-10-04): the fourth category of Work. /work/houses.html lists every house;
# /work/houses-<country>.html lists the houses standing in that country (a country needs at
# least MIN_HOUSES_FOR_COUNTRY_PAGE houses for a page of its own). houses.json has no
# structured country, so it is read from the location text when that names one ("Aarhus,
# Denmark" - 12 houses stand outside their architect's home country) and otherwise taken
# to be the architect's own country (right for almost every house without a country).
# LISTING TEMPLATE (piloted on Table Lamps, approved and rolled out to every type 2026-10-04). A type
# page looks like the Work page showing one type: Work's header, search box, chips row, results line and
# card style (shared stylesheet work-results.css).
# Template pages hold 60 cards (not 300): Lighthouse flags a page over ~1,400 DOM elements and 300 cards
# made ~3,400; 60 is ~1,000. 60 also divides evenly into every column count the grid uses (6, 4, 3, 2) so
# no page ends in a ragged row, and matches the Houses pages. A "See more" link loads the next 60 in place.
LISTING_CARDS_PER_PAGE = 60

HOUSES_PER_PAGE = 60
MIN_HOUSES_FOR_COUNTRY_PAGE = 8

sys.path.insert(0, str(BACKEND_DIR))
import query_engine as qe  # noqa: E402

from generate_brand_pages import (  # noqa: E402
    SHARE_BTN_HTML,
    listing_pager_html,
    site_nav_html,
    slugify,
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_NAV_HTML,
    SITE_URL,
    product_card_html,
)
from generate_theme_landing_pages import (  # noqa: E402
    _group_color_variants,
    append_to_sitemap,
)
from image_sizes import CARD, sized  # noqa: E402
from site_assets import ICONS_CSS, LISTING_JS, MENU_SCRIPT, SHARE_JS, WORK_MENU_CSS, WORK_RESULTS_CSS  # noqa: E402
from redirects import write_redirect  # noqa: E402
import work_menu  # noqa: E402

# Each entry's `intent` goes straight to query_engine.filter_products().
# `plural` is the lowercase noun used in the intro/meta sentence.
BROWSE_CATEGORIES = [
    # Lighting
    {"slug": "table-lamps", "title": "Table Lamps", "group": "Lighting", "intent": {"category": "table lamp"}},
    {"slug": "pendant-lamps", "title": "Pendant Lamps", "group": "Lighting", "intent": {"category": "pendant"}},
    {"slug": "wall-lamps", "title": "Wall Lamps", "group": "Lighting", "intent": {"category": "wall lamp"}},
    # Flush and surface mounts are ceiling fixtures (In Common With,
    # Palefire, Danny Kaplan tag them that way instead of "ceiling lamp").
    {"slug": "ceiling-lamps", "title": "Ceiling Lamps", "group": "Lighting",
     "intents": [{"category": "ceiling lamp"}, {"category": "flush mount"}, {"category": "surface mount"}]},
    {"slug": "chandeliers", "title": "Chandeliers", "group": "Lighting", "intent": {"category": "chandelier"}},
    # Floor Lamps lived at the site root (generate_theme_landing_pages.py) and Portable Lamps
    # only as an Edit; both are ordinary types now (2026-10-04).
    {"slug": "floor-lamps", "title": "Floor Lamps", "group": "Lighting", "intent": {"category": "floor lamp"}},
    {"slug": "portable-lamps", "title": "Portable Lamps", "group": "Lighting", "intent": {"portable_only": True}},
    # Seating. Footstools, ottomans/poufs and stools are three separate
    # types by the user's ruling (2026-10-02): a footstool is the
    # armchair/lounge-chair companion for resting feet, a pouf is
    # something to sit on, and neither is a stool. Bar Stools is a
    # subset of Stools, Dining Chairs/Armchairs overlap Chairs - the
    # hierarchy is intentional, each page answers its own search.
    {"slug": "sofas", "title": "Sofas", "group": "Seating", "intent": {"category": "sofa"}},
    {"slug": "chairs", "title": "Chairs", "group": "Seating", "intent": {"category": "chair"},
     "related": ["dining-chairs", "armchairs", "side-chairs", "garden-chairs", "office-chairs", "folding-chairs", "kids-chairs"]},
    # Sub-types of Chairs worked out from product names (scrape.py _refine_chair_subtype,
    # 2026-10-04). Rocking chairs (14) are tagged but too few for a page of their own.
    {"slug": "garden-chairs", "title": "Garden and Outdoor Chairs", "group": "Seating",
     "intents": [{"category": "garden chair"}, {"category": "outdoor chair"}]},
    {"slug": "side-chairs", "title": "Side Chairs", "group": "Seating", "intent": {"category": "side chair"}},
    {"slug": "folding-chairs", "title": "Folding and Stacking Chairs", "group": "Seating",
     "intents": [{"category": "folding chair"}, {"category": "stacking chair"}]},
    {"slug": "kids-chairs", "title": "Kids' Chairs", "group": "Seating", "intent": {"category": "kids chair"}},
    {"slug": "office-chairs", "title": "Office and Desk Chairs", "group": "Seating",
     "intents": [{"category": "office chair"}, {"category": "desk chair"}]},
    {"slug": "dining-chairs", "title": "Dining Chairs", "group": "Seating", "intent": {"category": "dining chair"}},
    {"slug": "armchairs", "title": "Armchairs and Lounge Chairs", "group": "Seating",
     "intents": [{"category": "armchair"}, {"category": "lounge chair"}],
     "related": ["footstools"]},
    {"slug": "stools", "title": "Stools", "group": "Seating", "intent": {"category": "stool"}},
    {"slug": "bar-stools", "title": "Bar Stools", "group": "Seating", "intent": {"category": "bar stool"}},
    {"slug": "benches", "title": "Benches", "group": "Seating", "intent": {"category": "bench"}},
    {"slug": "footstools", "title": "Footstools", "group": "Seating", "intent": {"category": "footstool"},
     "blurb": "Made for resting your feet - the companion to an armchair or lounge chair.",
     "related": ["armchairs"]},
    {"slug": "ottomans-and-poufs", "title": "Ottomans and Poufs", "group": "Seating",
     "intents": [{"category": "ottoman"}, {"category": "pouf"}], "related": ["footstools"]},
    # Tables and desks
    {"slug": "dining-tables", "title": "Dining Tables", "group": "Tables and desks", "intent": {"category": "dining table"}},
    {"slug": "coffee-tables", "title": "Coffee Tables", "group": "Tables and desks", "intent": {"category": "coffee table"}},
    {"slug": "side-tables", "title": "Side Tables", "group": "Tables and desks", "intent": {"category": "side table"}},
    {"slug": "console-tables", "title": "Console Tables", "group": "Tables and desks",
     "intents": [{"category": "console table"}, {"category": "console"}]},
    {"slug": "bedside-tables", "title": "Bedside Tables", "group": "Tables and desks",
     "intents": [{"category": "bedside table"}, {"category": "nightstand"}]},
    {"slug": "outdoor-tables", "title": "Outdoor Tables", "group": "Tables and desks",
     "intents": [{"category": "outdoor table"}, {"category": "garden table"}]},
    {"slug": "bar-tables", "title": "Bar Tables", "group": "Tables and desks", "intent": {"category": "bar table"}},
    {"slug": "desks", "title": "Desks", "group": "Tables and desks", "intent": {"category": "desk"}},
    # Storage, beds and mirrors
    {"slug": "sideboards", "title": "Sideboards", "group": "Storage, beds and mirrors", "intent": {"category": "sideboard"}},
    {"slug": "cabinets", "title": "Cabinets", "group": "Storage, beds and mirrors", "intent": {"category": "cabinet"}},
    {"slug": "shelving", "title": "Shelving", "group": "Storage, beds and mirrors", "intent": {"category": "shelving"}},
    {"slug": "beds", "title": "Beds", "group": "Storage, beds and mirrors", "intent": {"category": "bed"}},
    {"slug": "mirrors", "title": "Mirrors", "group": "Storage, beds and mirrors", "intent": {"category": "mirror"}},
    # Objects. Candle holders and candles are distinct types (user
    # ruling 2026-10-02) - see _normalize_candle_holder in scrape.py.
    {"slug": "candle-holders", "title": "Candle Holders", "group": "Objects",
     "intent": {"category": "candle holder"}, "related": ["candles"]},
    {"slug": "candles", "title": "Candles", "group": "Objects",
     "intents": [{"category": "candle"}], "related": ["candle-holders"]},
    {"slug": "glass", "title": "Glass", "group": "Objects", "intent": {"category": "glass"}},
    {"slug": "vases", "title": "Vases", "group": "Objects", "intent": {"category": "vase"}},
    {"slug": "bowls", "title": "Bowls", "group": "Objects", "intent": {"category": "bowl"}},
    {"slug": "plates", "title": "Plates", "group": "Objects", "intent": {"category": "plate"}},
    {"slug": "trays", "title": "Trays", "group": "Objects", "intent": {"category": "tray"}},
    # Soft furnishings
    {"slug": "rugs", "title": "Rugs", "group": "Soft furnishings", "intent": {"category": "rug"}},
    {"slug": "cushions", "title": "Cushions", "group": "Soft furnishings", "intent": {"category": "cushion"}},
    {"slug": "blankets", "title": "Blankets and Throws", "group": "Soft furnishings", "intent": {"category": "blanket"}},
]
GROUP_ORDER = ["Lighting", "Seating", "Tables and desks", "Storage, beds and mirrors", "Soft furnishings", "Objects"]
CATEGORY_BY_SLUG = {c["slug"]: c for c in BROWSE_CATEGORIES}


def _category_products(category):
    """Union of the category's intents, de-duplicated by product id."""
    intents = category.get("intents") or [category["intent"]]
    seen, out = set(), []
    for intent in intents:
        for p in qe.filter_products(intent):
            if p["id"] not in seen:
                seen.add(p["id"])
                out.append(p)
    return out


TYPE_GRID_CSS = """
  /* the category pages' type tiles: fixed 6 / 4 / 2 columns like every card grid (Site_Patterns.md) */
  .type-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 20px; margin: 0 0 36px; align-items: start; }
  .type-grid .maker-card-hero { aspect-ratio: 1/1; }
  .type-group-title { font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); margin: 30px 0 14px; }
  @media (max-width: 959px) { .type-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
  @media (max-width: 639px) { .type-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; } }
  /* Houses: landscape photos at 4:3 in four larger columns (3 on tablet, 2 on phones) - a square
     crop cut half of every building; both text lines stay on one line so rows are even. */
  .type-grid--houses { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 22px 20px; }
  .type-grid--houses .maker-card-hero { aspect-ratio: 4/3; }
  .type-grid--houses .maker-name, .type-grid--houses .maker-country { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  @media (max-width: 959px) { .type-grid--houses { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  @media (max-width: 639px) { .type-grid--houses { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; } }
  .house-practices { font-size: 13px; line-height: 1.7; color: var(--text-secondary); margin: 0 0 14px; }
  .house-practices span { font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); margin-right: 6px; }
  .house-practices a { color: var(--text-primary); text-decoration: none; }
  .house-practices a:hover { text-decoration: underline; }
"""

PAGER_CSS = """
  .pager { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 40px 0 8px; }
  .pager a, .pager span {
    min-width: 38px; padding: 8px 12px; text-align: center; font-size: 14px;
    border: 0.5px solid var(--border); border-radius: 8px; text-decoration: none;
    color: var(--text-secondary);
  }
  .pager a:hover { color: var(--text-primary); border-color: var(--text-muted); }
  .pager span.current { color: var(--text-primary); border-color: var(--text-secondary); font-weight: 600; }
  .browse-list { list-style: none; padding: 0; margin: 0 auto; max-width: 520px; }
  .browse-list li { border-bottom: 0.5px solid var(--border); }
  .browse-list a {
    display: flex; justify-content: space-between; padding: 14px 4px;
    text-decoration: none; color: inherit; font-size: 16px;
  }
  .browse-group { max-width: 520px; margin: 32px auto 4px; font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); }
  .browse-list a:hover .browse-name { text-decoration: underline; }
  .browse-list .browse-n { color: var(--text-muted); font-size: 14px; }
"""


def _interleave_by_brand(products):
    """Deterministic one-per-brand-per-pass ordering (brands alphabetical,
    each brand's own products in the order filter_products() returned
    them, which is stable DB order)."""
    by_brand = {}
    for p in products:
        by_brand.setdefault(p["brand"], []).append(p)
    queues = [by_brand[b] for b in sorted(by_brand, key=str.lower)]
    out = []
    i = 0
    while queues:
        remaining = []
        for q in queues:
            out.append(q[i])
            if i + 1 < len(q):
                remaining.append(q)
        queues = remaining
        i += 1
    return out


def _page_slug(slug, page):
    return slug if page == 1 else f"{slug}-{page}"


def _pager_html(slug, page, pages):
    if pages <= 1:
        return ""
    items = []
    if page > 1:
        items.append(f'<a href="/work/{_page_slug(slug, page - 1)}.html" rel="prev">&larr; Prev</a>')
    for n in range(1, pages + 1):
        if n == page:
            items.append(f'<span class="current" aria-current="page">{n}</span>')
        else:
            items.append(f'<a href="/work/{_page_slug(slug, n)}.html">{n}</a>')
    if page < pages:
        items.append(f'<a href="/work/{_page_slug(slug, page + 1)}.html" rel="next">Next &rarr;</a>')
    return f'<nav class="pager" aria-label="Pages">{"".join(items)}</nav>'


def _pager_compact_html(slug, page, pages):
    """The numbered pager for a type/New page (shared implementation: generate_brand_pages.listing_pager_html)."""
    return listing_pager_html(lambda n: f"/work/{_page_slug(slug, n)}.html", page, pages)


def _head(title, description, page_url):
    return f"""<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/favicon-192x192.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(description)}">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<link rel="stylesheet" href="{WORK_MENU_CSS}">
<style>{PAGE_CSS}{PAGER_CSS}{TYPE_GRID_CSS}</style>"""


def _breadcrumb_json(crumbs):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(crumbs)
        ],
    })


def _itemlist_json(cards, start_index):
    """schema.org ItemList of Product for the page's cards - typed data for
    crawlers and agents that the visual cards alone don't carry. An Offer is
    included ONLY when both price and currency are stored (currency is
    known for few products; it is never guessed)."""
    items = []
    for i, p in enumerate(cards, start=start_index):
        product = {
            "@type": "Product",
            "name": p["product_name"],
            "url": p["product_url"],
            "image": p["image_url"],
            "brand": {"@type": "Brand", "name": p["brand"]},
        }
        if p.get("category"):
            product["category"] = p["category"].split(",")[0].strip()
        if p.get("price") and p.get("currency"):
            product["offers"] = {
                "@type": "Offer", "price": f'{p["price"]:.2f}',
                "priceCurrency": p["currency"],
            }
        items.append({"@type": "ListItem", "position": i, "item": product})
    return json.dumps({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": items},
                      ensure_ascii=False, separators=(",", ":"))


def _see_also_html(category):
    links = [CATEGORY_BY_SLUG[r] for r in category.get("related", []) if r in CATEGORY_BY_SLUG]
    if not links:
        return ""
    anchors = ", ".join(f'<a href="/work/{c["slug"]}.html">{html.escape(c["title"].lower())}</a>' for c in links)
    return f" See also: {anchors}."


LISTING_CSS = """
  /* The listing template: everything layout/card/search related comes from work-results.css (the Work
     page's own stylesheet); these are only the parts a listing adds. */
  .site-header { margin-bottom: 0; }
  .listing-title { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 26px; line-height: 1.15; text-align: center; margin: 34px 0 22px; }
  .listing-meta { font-size: 12px; color: var(--text-muted); text-align: center; margin: -14px 0 22px; }
  .listing-meta a { color: var(--text-accent); text-decoration: none; white-space: nowrap; }
  .listing-meta a:hover { text-decoration: underline; }
  .variant-badge {
    position: absolute; bottom: 6px; left: 6px; z-index: 1; background: rgba(250, 249, 247, 0.9);
    color: var(--text-secondary); font-size: 11px; font-weight: 500; padding: 4px 10px; border-radius: 10px;
    border: 0.5px solid transparent;
  }
  .listing-more { margin: 44px 0 0; padding-top: 22px; border-top: 0.5px solid var(--border); font-size: 13px; line-height: 1.8; color: var(--text-secondary); }
  .listing-more h2 { font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); margin: 0 0 6px; }
  .listing-more p { margin: 0 0 18px; }
  .listing-more h2 a { color: var(--text-muted); }
  .listing-more a { color: var(--text-primary); text-decoration: none; }
  .listing-more h2 a:hover { color: var(--text-primary); }
  .listing-more a:hover { text-decoration: underline; }
  .listing-more .n { color: var(--text-muted); }
  .listing-more .here { color: var(--text-primary); font-weight: 600; }
  .pager { margin-top: 28px; }
  /* With JavaScript "See more" is the one visible way on (listing.js adds .has-load-more): the numbered pager
     stays in the HTML for search engines and for visitors without JavaScript, but is not shown. */
  .has-load-more .pager { display: none; }
  .earlier-results { display: none; margin: 0 0 14px; font-size: 13px; }
  .has-load-more .earlier-results { display: block; }
  .earlier-results a { color: var(--text-muted); text-decoration: none; }
  .earlier-results a:hover { color: var(--text-primary); text-decoration: underline; }
  .pager .gap { border: 0; min-width: 0; padding: 8px 2px; color: var(--text-muted); }
"""

# product slug -> the curated Edits that cover it (for the "curated selection" link)
def _edits_for_type(slug):
    import generate_themed_edit_pages as edits
    titles = {t["slug"]: t["title"] for t in edits.THEMES}
    return [(es, titles[es]) for es, (browse_slug, _noun) in edits.EDIT_BROWSE_LINKS.items()
            if browse_slug == slug and es in titles]


def _listing_card_html(p, variant_count=None):
    """A product card identical to the Work page's own (search.js renderCard): photo with the share
    button over its corner, name (2-line slot), maker, and the empty detail line that keeps rows even."""
    url = p["brand_url"] if p["link_dead"] else p["product_url"]
    name, brand = html.escape(p["product_name"]), html.escape(p["brand"])
    image = (f'<img src="{html.escape(sized(p["image_url"], CARD))}" alt="{html.escape(p["product_name"])} by {brand}" loading="lazy">'
             if p["image_url"] else "")
    badge = f'<span class="variant-badge">{variant_count} finishes</span>' if variant_count and variant_count > 1 else ""
    return (
        f'<a class="card" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer" '
        f'data-product="{name}" data-brand="{brand}">'
        f'<div class="card-image">{image}{badge}'
        '<button class="share-btn" type="button" aria-label="Share this piece"><i class="ti ti-share-2" aria-hidden="true"></i></button></div>'
        f'<div class="card-body"><div class="card-title-wrap"><p class="card-title">{name}</p></div>'
        f'<p class="card-brand">{brand}</p><p class="card-detail"></p></div></a>'
    )


def render_listing_page(category, cards, variant_counts, page, pages, products, entries, cards_all, view=None):
    """The type page as the Work page showing one type. `view` (the New pages) overrides what differs for a
    page that is not one type: its slug/title/wording, breadcrumb, menu state, a sub-navigation row and the
    list at the bottom."""
    from collections import Counter
    slug, title = (view["slug"], view["title"]) if view else (category["slug"], category["title"])
    total = len(products)
    page_url = f"{SITE_URL}/work/{_page_slug(slug, page)}.html"
    cat_name = (view.get("cat") if view else work_menu.category_of_group(category["group"]))
    cat_slug = work_menu.CATEGORY_SLUGS[cat_name] if cat_name else None
    noun = view["noun"] if view else title.lower()
    makers = Counter(p["brand"] for p in products)
    n_makers = len(makers)
    summary = view["summary"](total, n_makers) if view else f"{total:,} {noun} from {n_makers} makers"
    page_note = f" - page {page} of {pages}" if pages > 1 else ""
    description = f"{summary}, listed in full{page_note}. Every result links straight to the maker's own site."
    edits = [] if view else _edits_for_type(slug)
    edit_line = ""
    if edits:
        links = " &middot; ".join(f'<a href="/edits/{es}.html">{html.escape(et)} &rarr;</a>' for es, et in edits)
        edit_line = f' &middot; {"Themed Edits" if len(edits) > 1 else "Themed Edit"}: {links}'
    # No results line any more (2026-10-04: count, "listed in full", page 1 of N, "no rankings" was page information
    # nobody needed above the products); only the Themed Edit link survives, when an Edit covers this type.
    edit_link_html = (f'<p class="listing-meta">{"Themed Edits" if len(edits) > 1 else "Themed Edit"}: {links}</p>'
                      if edits else "")
    if view:
        breadcrumb = _breadcrumb_json([("Formground", f"{SITE_URL}/"), ("Work", f"{SITE_URL}/work.html")]
                                      + [(t, f"{SITE_URL}{u}") for t, u in view["crumbs"]])
    else:
        breadcrumb = _breadcrumb_json([
            ("Formground", f"{SITE_URL}/"), ("Work", f"{SITE_URL}/work.html"),
            (cat_name, f"{SITE_URL}/work/{cat_slug}.html"), (title, f"{SITE_URL}/work/{slug}.html")])
    itemlist = _itemlist_json(cards, (page - 1) * LISTING_CARDS_PER_PAGE + 1)
    grid = "".join(_listing_card_html(p, variant_counts.get(id(p))) for p in cards)

    def maker_link(brand):
        slug_b = slugify(brand)
        return (f'<a href="/brands/{slug_b}.html">{html.escape(brand)}</a>'
                if (DOCS_DIR / "brands" / f"{slug_b}.html").exists() else html.escape(brand))
    top_makers = " &middot; ".join(f'{maker_link(b)} <span class="n">{n}</span>' for b, n in makers.most_common(40))
    more_makers = f" &middot; and {n_makers - 40} more" if n_makers > 40 else ""
    if view:
        siblings_heading = view["siblings_heading"]
        siblings = view["siblings"]
        subnav = view["subnav"](slug)
    else:
        # The whole category's types, the current one marked (bold, not a link) like the dropdown does.
        siblings_heading = f'<a href="/work/{cat_slug}.html">{html.escape(cat_name)} &rarr;</a>'
        subnav = ""
        siblings = " &middot; ".join(
            (f'<strong class="here" aria-current="page">{html.escape(e["title"])}</strong> <span class="n">{e["n"]:,}</span>'
             if e["slug"] == slug else
             f'<a href="/work/{e["slug"]}.html">{html.escape(e["title"])}</a> <span class="n">{e["n"]:,}</span>')
            for e in sorted(work_menu.category_entries(entries, cat_name), key=work_menu.entry_sort_key))
    menu_html = work_menu.render_menu(entries, current_slug=slug, current_category=cat_name)
    earlier = (f'<p class="earlier-results"><a href="/work/{_page_slug(slug, page - 1)}.html" rel="prev">'
               f'&larr; Earlier results</a></p>' if page > 1 else "")
    see_more = ""
    if page < pages:
        see_more = (f'<div class="load-more-row"><a class="load-more-btn" id="see-more" data-total="{len(cards_all)}" data-start="{(page - 1) * LISTING_CARDS_PER_PAGE}" '
                    f'href="/work/{_page_slug(slug, page + 1)}.html">See more {html.escape(noun)}</a>'
                    f'<span class="load-more-progress" id="see-more-progress"></span></div>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}{html.escape(f" - page {page}" if page > 1 else "")} — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)} — Formground">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/favicon-192x192.png">
<meta name="twitter:card" content="summary">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<link rel="stylesheet" href="{WORK_RESULTS_CSS}">
<link rel="stylesheet" href="{WORK_MENU_CSS}">
<style>{PAGER_CSS}{LISTING_CSS}</style>
<script type="application/ld+json">{breadcrumb}</script>
<script type="application/ld+json">{itemlist}</script>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("work")}
</header>
<main>
  <div class="search-wide">
    <form action="/work.html" method="get">
      <div class="ask-box">
        <i class="ti ti-search" aria-hidden="true"></i>
        <input name="q" type="text" placeholder="Search through a curated collection of work" autocomplete="off" aria-label="Search">
      </div>
    </form>
  </div>
  {menu_html}
  {subnav}
  <h1 class="listing-title">{html.escape(title)}</h1>
  {edit_link_html}
  {earlier}
  <div class="results-grid">{grid}</div>
  {see_more}
  {_pager_compact_html(slug, page, pages)}
  <section class="listing-more">
    <h2><a href="/makers.html">Makers &rarr;</a></h2>
    <p>{top_makers}{more_makers}</p>
    <h2>{siblings_heading}</h2>
    <p>{siblings}</p>
  </section>
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>{CARD_CLICK_TRACKING_JS}</script>
{MENU_SCRIPT}
<script src="{SHARE_JS}" defer></script>
<script src="{LISTING_JS}" defer></script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def _type_tile_html(e):
    """One type's tile on a category page: a photo, the type's name, how many pieces."""
    image = ""
    if e.get("image"):
        image = f'<img src="{html.escape(sized(e["image"], CARD))}" alt="{html.escape(e["title"])}" loading="lazy">'
    return (
        f'<a class="maker-card" href="/work/{e["slug"]}.html">'
        f'<div class="maker-card-hero">{image}</div>'
        f'<div class="maker-card-body"><span class="maker-name">{html.escape(e["title"])}</span>'
        f'<span class="maker-country">{e["n"]:,} pieces</span></div></a>'
    )


def _interleave_by_firm(houses):
    """Round-robin one house per firm per pass (firms alphabetical) so one practice with a
    deep list does not fill a page; deterministic, like _interleave_by_brand."""
    by_firm = {}
    for h in houses:
        by_firm.setdefault(h["firm"], []).append(h)
    queues = [by_firm[f] for f in sorted(by_firm)]
    out = []
    while any(queues):
        for q in queues:
            if q:
                out.append(q.pop(0))
    return out


# Names that end a location string when it states a country ("Veddinge, Zeeland, Denmark").
STATED_COUNTRIES = {
    "sweden": "Sweden", "norway": "Norway", "denmark": "Denmark", "finland": "Finland", "iceland": "Iceland",
    "austria": "Austria", "österreich": "Austria", "switzerland": "Switzerland", "germany": "Germany",
    "france": "France", "uk": "United Kingdom", "united kingdom": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom", "ireland": "Ireland", "italy": "Italy",
    "spain": "Spain", "portugal": "Portugal", "croatia": "Croatia", "new zealand": "New Zealand",
    "australia": "Australia", "japan": "Japan", "chile": "Chile", "argentina": "Argentina", "uruguay": "Uruguay",
    "mexico": "Mexico", "ecuador": "Ecuador", "costa rica": "Costa Rica", "fiji": "Fiji", "canada": "Canada",
    "usa": "United States", "united states": "United States",
}


def stated_country(location):
    """The country a location string names at its end, or None."""
    if not location:
        return None
    tail = location.replace(")", "").split(",")[-1].strip().lower()
    return STATED_COUNTRIES.get(tail)


def load_houses():
    import json as _json
    houses = _json.loads((DATA_DIR / "houses.json").read_text())
    firms = {a["name"]: a for a in _json.loads((DATA_DIR / "architects.json").read_text())}
    for h in houses:
        h["country"] = stated_country(h.get("location")) or firms.get(h["firm"], {}).get("country")
    return [h for h in houses if h.get("image")]


def house_groups(houses):
    """[(country, slug, houses)] for countries with enough houses for a page, biggest first."""
    by_country = {}
    for h in houses:
        if h.get("country"):
            by_country.setdefault(h["country"], []).append(h)
    groups = [(c, f"houses-{slugify(c)}", hs) for c, hs in by_country.items() if len(hs) >= MIN_HOUSES_FOR_COUNTRY_PAGE]
    return sorted(groups, key=lambda g: (-len(g[2]), g[0]))


def house_entries(groups):
    return [{"slug": slug, "title": country, "n": len(hs), "group": "Houses", "image": hs[0]["image"]}
            for country, slug, hs in groups]


def _house_work_card_html(h):
    meta = " · ".join(x for x in [h.get("location"), str(h["year"]) if h.get("year") else None] if x)
    # both text lines always exist and stay on one line, so every card in a row is the same height
    return (
        f'<a class="maker-card" href="{html.escape(h.get("url") or "#")}" target="_blank" rel="noopener noreferrer" '
        f'data-product="{html.escape(h["name"] or "House")}" data-brand="{html.escape(h["firm"])}">'
        f'<div class="maker-card-hero"><img src="{html.escape(h["image"])}" alt="{html.escape(h["name"] or "House")}" loading="lazy">{SHARE_BTN_HTML}</div>'
        f'<div class="maker-card-body"><span class="maker-name">{html.escape(h["name"] or "Untitled house")}</span>'
        f'<span class="maker-country">{html.escape(meta) if meta else "&nbsp;"}</span>'
        f'<span class="maker-country">by {html.escape(h["firm"])}</span></div></a>'
    )


def render_houses_page(slug, title, lead, houses, page, pages, entries, crumbs, firm_pages):
    """/work/houses.html (every house) and /work/houses-<country>.html. Same shell as the type
    pages; each house links to its architect's own project page."""
    page_url = f"{SITE_URL}/work/{_page_slug(slug, page)}.html"
    suffix = f" - page {page}" if page > 1 else ""
    firms_here = {}
    for h in houses:
        firms_here[h["firm"]] = firms_here.get(h["firm"], 0) + 1
    n_firms = len(firms_here)
    summary = f"{len(houses):,} houses by {n_firms} practice{'' if n_firms == 1 else 's'}{lead}"
    description = f"{summary}. Every house links straight to the architect's own project page."
    practices = ""
    if slug != "houses":  # the country pages name their practices; the full list is the Architects page
        links = " &middot; ".join(
            f'<a href="/architects/{firm_pages[f]}.html">{html.escape(f)}</a> ({n})' if f in firm_pages else html.escape(f)
            for f, n in sorted(firms_here.items(), key=lambda kv: (-kv[1], kv[0])))
        practices = f'<p class="house-practices"><span>Practices</span> {links}</p>'
    chunk = houses[(page - 1) * HOUSES_PER_PAGE: page * HOUSES_PER_PAGE]
    cards = "".join(_house_work_card_html(h) for h in chunk)
    breadcrumb = _breadcrumb_json([("Formground", f"{SITE_URL}/"), ("Work", f"{SITE_URL}/work.html")] +
                                  [(n, f"{SITE_URL}{u}") for n, u in crumbs])
    itemlist = json.dumps({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": (page - 1) * HOUSES_PER_PAGE + i,
         "item": {"@type": "CreativeWork", "name": h["name"], "url": h.get("url"), "image": h["image"],
                  "creator": {"@type": "Organization", "name": h["firm"]}}}
        for i, h in enumerate(chunk, start=1)]}, ensure_ascii=False, separators=(",", ":"))
    tagline = " &rsaquo; ".join(f'<a href="{u}">{html.escape(n)}</a>' for n, u in [("Work", "/work.html")] + crumbs[:-1])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head(f"{title}{suffix} — Formground", description, page_url)}
<script type="application/ld+json">{breadcrumb}</script>
<script type="application/ld+json">{itemlist}</script>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline">{tagline}</p>
  <h1>{html.escape(title)}</h1>
  <p class="category-intro">{html.escape(summary)}{f" (page {page} of {pages})" if pages > 1 else ""}. Every house links straight to the architect's own project page.</p>
  {practices}
  {work_menu.render_menu(entries, align="left", current_category="Houses", current_slug=slug)}
  <div class="type-grid type-grid--houses">{cards}</div>
  {_pager_html(slug, page, pages)}
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>{CARD_CLICK_TRACKING_JS}</script>
<script src="{SHARE_JS}" defer></script>
{MENU_SCRIPT}
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def _write_house_pages(houses, groups, entries):
    """Writes houses.html (+ -2 ...) and each country's pages; returns sitemap slugs."""
    import generate_architects_pages
    firm_pages = generate_architects_pages.firm_slugs()
    out_slugs = []
    ordered = _interleave_by_firm(houses)
    n_countries = len({h["country"] for h in houses if h.get("country")})
    targets = [("houses", "Houses", f" in {n_countries} countries", ordered, [("Houses", "/work/houses.html")])]
    for country, slug, hs in groups:
        targets.append((slug, f"Houses in {country}", f" in {country}", _interleave_by_firm(hs),
                        [("Houses", "/work/houses.html"), (country, f"/work/{slug}.html")]))
    for slug, title, lead, hs, crumbs in targets:
        pages = max(1, math.ceil(len(hs) / HOUSES_PER_PAGE))
        for page in range(1, pages + 1):
            (BROWSE_DIR / f"{_page_slug(slug, page)}.html").write_text(
                render_houses_page(slug, title, lead, hs, page, pages, entries, crumbs, firm_pages))
            out_slugs.append(f"work/{_page_slug(slug, page)}")
        print(f"work/{slug}: {len(hs)} houses, {pages} page(s)")
    return out_slugs


def render_category_page(cat_name, entries):
    """/work/furniture.html | lighting | objects: the category's groups and types, in full."""
    cat_slug = work_menu.CATEGORY_SLUGS[cat_name]
    page_url = f"{SITE_URL}/work/{cat_slug}.html"
    mine = work_menu.category_entries(entries, cat_name)
    types = [e for e in mine if not e.get("is_new")]       # the "New" entry is a view, not a type
    total = sum(e["n"] for e in types)
    description = (f"{total:,} pieces of {cat_name.lower()} from independent makers across {len(types)} types, listed in full - "
                   "each linking straight to the maker's own site.")
    blocks = []
    new_tiles = "".join(_type_tile_html(e) for e in mine if e.get("is_new"))
    if new_tiles:
        blocks.append(f'<div class="type-grid">{new_tiles}</div>')    # Furniture / New, above the groups
    for group in work_menu.TAXONOMY[cat_name]:
        tiles = "".join(
            _type_tile_html(e)
            for e in sorted((x for x in mine if x["group"] == group), key=work_menu.entry_sort_key)
        )
        label = work_menu.GROUP_LABELS.get(group, group)
        heading = f'<h2 class="type-group-title">{html.escape(label)}</h2>' if len(work_menu.TAXONOMY[cat_name]) > 1 else ""
        blocks.append(f'{heading}<div class="type-grid">{tiles}</div>')
    breadcrumb = _breadcrumb_json([("Formground", f"{SITE_URL}/"), ("Work", f"{SITE_URL}/work.html"), (cat_name, page_url)])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head(f"{cat_name} — Formground", description, page_url)}
<link rel="stylesheet" href="{WORK_RESULTS_CSS}">
<style>{LISTING_CSS}</style>
<script type="application/ld+json">{breadcrumb}</script>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("work")}
</header>
<main>
  <div class="search-wide">
    <form action="/work.html" method="get">
      <div class="ask-box">
        <i class="ti ti-search" aria-hidden="true"></i>
        <input name="q" type="text" placeholder="Search through a curated collection of work" autocomplete="off" aria-label="Search">
      </div>
    </form>
  </div>
  {work_menu.render_menu(entries, current_category=cat_name)}
  <h1 class="listing-title">{html.escape(cat_name)}</h1>
  <p class="listing-meta"><a href="/edits.html">Themed Edits &rarr;</a></p>
  {"".join(blocks)}
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>{CARD_CLICK_TRACKING_JS}</script>
{MENU_SCRIPT}
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


NEW_CATEGORIES = ("Furniture", "Lighting", "Objects")   # Houses carry no added-date, so no New view
NEW_PER_MAKER_CEILING = 10   # at most this many pieces per maker in each New view (2026-10-04, smaller makers)


def _new_sets():
    """{category: products added in the last NEW_ARRIVALS_WINDOW_DAYS days (the same window and filter the Work
    search's "new" keyword uses)}, newest first. A piece counts under a category when it belongs to one of
    that category's types, so not-yet-classified pieces are in none of them."""
    new_all = qe.filter_products({"new_only": True})
    ids_by_cat = {}
    for category in BROWSE_CATEGORIES:
        cat_name = work_menu.category_of_group(category["group"])
        for intent in category.get("intents") or [category["intent"]]:
            for p in qe.filter_products({**intent, "new_only": True}):
                ids_by_cat.setdefault(cat_name, set()).add(p["id"])
    newest = sorted(new_all, key=lambda p: p.get("released_at") or p["first_seen"] or "", reverse=True)
    return {c: _cap_per_maker([p for p in newest if p["id"] in ids_by_cat.get(c, set())], NEW_PER_MAKER_CEILING)
            for c in NEW_CATEGORIES}


def _cap_per_maker(products, ceiling):
    """The `ceiling` newest pieces of each maker (products arrive newest first), in the same order. Established
    makers release far more, so uncapped they would fill New (Ferm Living, Mater and Serax were 42% of it);
    capped, New shows breadth across the makers who released something."""
    seen, out = {}, []
    for p in products:
        if seen.get(p["brand"], 0) < ceiling:
            seen[p["brand"]] = seen.get(p["brand"], 0) + 1
            out.append(p)
    return out


def _new_entries(sets):
    """One "New" entry per category, shaped like a type's (so the menu, category page and lists treat it as
    one; work_menu.entry_sort_key puts it first). Its photo is the category's newest piece with an image."""
    out = []
    for cat in NEW_CATEGORIES:
        products = sets[cat]
        image = next((p["image_url"] for p in products if p["image_url"]), "")
        out.append({"slug": f"new-{work_menu.CATEGORY_SLUGS[cat]}", "title": "New", "n": len(products),
                    "group": None, "category": cat, "image": image, "is_new": True})
    return out


def _new_view_pages(entries, sets):
    """/work/new-furniture|lighting|objects.html: the category's recently added pieces as the same listing
    pages as the types (cards spread across makers so one new brand's batch does not fill the page)."""
    from generate_brand_pages import NEW_ARRIVALS_WINDOW_DAYS
    slugs = []
    for cat in NEW_CATEGORIES:
        vslug = f"new-{work_menu.CATEGORY_SLUGS[cat]}"
        products = sets[cat]
        cards, variant_counts = _group_color_variants(products)
        cards = _interleave_by_brand(cards)
        title = f"New in {cat}"
        crumbs = [(cat, f"/work/{work_menu.CATEGORY_SLUGS[cat]}.html"), (title, f"/work/{vslug}.html")]
        siblings = " &middot; ".join(
            (f'<strong class="here" aria-current="page">{html.escape(e["title"])}</strong> <span class="n">{e["n"]:,}</span>'
             if e["slug"] == vslug else
             f'<a href="/work/{e["slug"]}.html">{html.escape(e["title"])}</a> <span class="n">{e["n"]:,}</span>')
            for e in sorted(work_menu.category_entries(entries, cat), key=work_menu.entry_sort_key))
        view = {
            "slug": vslug, "title": title, "noun": "new pieces", "cat": cat, "crumbs": crumbs,
            "summary": lambda total, n, d=NEW_ARRIVALS_WINDOW_DAYS: f"{total:,} pieces new from their makers in the last {d} days, from {n} makers",
            "siblings_heading": f'<a href="/work/{work_menu.CATEGORY_SLUGS[cat]}.html">{html.escape(cat)} &rarr;</a>',
            "siblings": siblings, "subnav": lambda _slug: "",
        }
        pages = max(1, math.ceil(len(cards) / LISTING_CARDS_PER_PAGE))
        for page in range(1, pages + 1):
            chunk = cards[(page - 1) * LISTING_CARDS_PER_PAGE: page * LISTING_CARDS_PER_PAGE]
            out = BROWSE_DIR / f"{_page_slug(vslug, page)}.html"
            out.write_text(render_listing_page(None, chunk, variant_counts, page, pages, products, entries, cards, view=view))
            slugs.append(f"work/{_page_slug(vslug, page)}")
        print(f"work/{vslug}: {len(products)} products -> {len(cards)} cards, {pages} page(s)")
    return slugs


def render_new_hub(entries):
    """/work/new.html: where the home page's "New" heading lands - the three categories' New views as photo
    tiles. Not in the menu (New lives inside each category); no cards of its own."""
    page_url = f"{SITE_URL}/work/new.html"
    mine = [e for e in entries if e.get("is_new")]
    total = sum(e["n"] for e in mine)
    description = (f"{total:,} pieces recently added to Formground, by category - each linking straight to the "
                   "maker's own site.")
    tiles = "".join(_type_tile_html({**e, "title": f"New in {e['category']}"}) for e in mine)
    breadcrumb = _breadcrumb_json([("Formground", f"{SITE_URL}/"), ("Work", f"{SITE_URL}/work.html"), ("New", page_url)])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head("New — Formground", description, page_url)}
<link rel="stylesheet" href="{WORK_RESULTS_CSS}">
<style>{LISTING_CSS}</style>
<script type="application/ld+json">{breadcrumb}</script>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("work")}
</header>
<main>
  <div class="search-wide">
    <form action="/work.html" method="get">
      <div class="ask-box">
        <i class="ti ti-search" aria-hidden="true"></i>
        <input name="q" type="text" placeholder="Search through a curated collection of work" autocomplete="off" aria-label="Search">
      </div>
    </form>
  </div>
  {work_menu.render_menu(entries)}
  <h1 class="listing-title">New</h1>
  <div class="type-grid">{tiles}</div>
  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>{CARD_CLICK_TRACKING_JS}</script>
{MENU_SCRIPT}
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def generate():
    BROWSE_DIR.mkdir(exist_ok=True)
    # Old /browse/ page names, read BEFORE anything is rewritten: each becomes a redirect stub
    # to its new /work/ address (so old links and bookmarks still land on the right page).
    OLD_BROWSE_DIR.mkdir(exist_ok=True)
    old_names = {f.stem for f in OLD_BROWSE_DIR.glob("*.html")}
    # Drop stale pages first: a category that shrinks to fewer pages
    # must not leave an orphaned {slug}-4.html behind.
    for old in BROWSE_DIR.glob("*.html"):
        old.unlink()

    computed = []
    entries = []
    for category in BROWSE_CATEGORIES:
        products = _category_products(category)
        cards, variant_counts = _group_color_variants(products)
        cards = _interleave_by_brand(cards)
        computed.append((category, products, cards, variant_counts))
        entries.append({"slug": category["slug"], "title": category["title"], "n": len(products), "group": category["group"],
                        "image": cards[0]["image_url"] if cards else ""})

    houses = load_houses()
    groups = house_groups(houses)
    entries.extend(house_entries(groups))
    new_sets = _new_sets()
    entries.extend(_new_entries(new_sets))   # "New" sits in each category like a type

    sitemap_slugs = []
    for category, products, cards, variant_counts in computed:
        per_page = LISTING_CARDS_PER_PAGE
        pages = max(1, math.ceil(len(cards) / per_page))
        for page in range(1, pages + 1):
            chunk = cards[(page - 1) * per_page: page * per_page]
            out = BROWSE_DIR / f"{_page_slug(category['slug'], page)}.html"
            out.write_text(render_listing_page(category, chunk, variant_counts, page, pages, products, entries, cards))
            sitemap_slugs.append(f"work/{_page_slug(category['slug'], page)}")
        print(f"work/{category['slug']}: {len(products)} products -> {len(cards)} cards, {pages} page(s)")

    for cat_name, cat_slug in work_menu.CATEGORY_SLUGS.items():
        if cat_name == "Houses":
            continue  # its category page is the full list of houses, written below
        (BROWSE_DIR / f"{cat_slug}.html").write_text(render_category_page(cat_name, entries))
        sitemap_slugs.append(f"work/{cat_slug}")
    sitemap_slugs += _write_house_pages(houses, groups, entries)
    sitemap_slugs += _new_view_pages(entries, new_sets)
    (BROWSE_DIR / "new.html").write_text(render_new_hub(entries))
    sitemap_slugs.append("work/new")
    # /new.html moved here (2026-10-04): the old address stays as a stub
    write_redirect(DOCS_DIR / "new.html", "/work/new.html")
    # "Recently added" (first-seen based) was live for a few hours on 2026-10-04 and replaced by "New" (maker dates)
    write_redirect(BROWSE_DIR / "recently-added.html", "/work/new.html")
    for cat in NEW_CATEGORIES:
        for page in range(1, 9):
            write_redirect(BROWSE_DIR / f"{_page_slug('recently-added-' + work_menu.CATEGORY_SLUGS[cat], page)}.html",
                           f"/work/{_page_slug('new-' + work_menu.CATEGORY_SLUGS[cat], 1)}.html")
    # /work/ itself has no page of its own: the Work page is /work.html
    write_redirect(BROWSE_DIR / "index.html", "/work.html")

    # The menu on the Work page itself (frontend/work.html is hand-written, mirrored to docs/)
    frontend_work = SCRAPER_DIR.parent / "frontend" / "work.html"
    if work_menu.inject_into_page(frontend_work, work_menu.render_menu(entries, surprise="button")):
        print("updated the browse menu in frontend/work.html")
    import shutil
    import site_assets
    site_assets.stamp_html([frontend_work])  # menu stylesheet + script links (versioned)
    shutil.copy(frontend_work, DOCS_DIR / "work.html")

    # Old /browse/ addresses -> stubs
    existing_new = {f.stem for f in BROWSE_DIR.glob("*.html")}
    for stem in sorted(old_names | {"index"}):
        if stem == "index":
            target = "/work.html"
        elif stem in existing_new:
            target = f"/work/{stem}.html"
        else:
            base = stem.rsplit("-", 1)[0] if stem.rsplit("-", 1)[-1].isdigit() else stem
            target = f"/work/{base}.html"
        write_redirect(OLD_BROWSE_DIR / f"{stem}.html", target)

    append_to_sitemap([s for s in sitemap_slugs if s != "work/index"])


if __name__ == "__main__":
    generate()
