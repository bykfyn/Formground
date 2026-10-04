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

sys.path.insert(0, str(BACKEND_DIR))
import query_engine as qe  # noqa: E402

from generate_brand_pages import (  # noqa: E402
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
from site_assets import ICONS_CSS, MENU_SCRIPT, WORK_MENU_CSS  # noqa: E402
from redirects import write_redirect  # noqa: E402
import work_menu  # noqa: E402

# ~300 cards is ~145 KB of HTML - the same weight as the existing
# Floor Lamps page, which is the one uncapped category page already
# live and loading fine. Serax's single brand page is 1.3 MB for
# comparison, so this is deliberately well under what the site already
# serves.
CARDS_PER_PAGE = 300

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
    {"slug": "chairs", "title": "Chairs", "group": "Seating", "intent": {"category": "chair"}},
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
  .type-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 20px; margin: 0 0 36px; align-items: start; }
  .type-grid .maker-card-hero { aspect-ratio: 1/1; }
  .type-group-title { font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); margin: 30px 0 14px; }
  @media (max-width: 959px) { .type-grid { grid-template-columns: repeat(4, 1fr); } }
  @media (max-width: 639px) { .type-grid { grid-template-columns: repeat(2, 1fr); gap: 16px; } }
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


def render_browse_page(category, cards, variant_counts, page, pages, total_products, entries):
    itemlist = _itemlist_json(cards, (page - 1) * CARDS_PER_PAGE + 1)
    slug, title = category["slug"], category["title"]
    page_url = f"{SITE_URL}/work/{_page_slug(slug, page)}.html"
    cat_name = work_menu.category_of_group(category["group"])
    cat_slug = work_menu.CATEGORY_SLUGS[cat_name]
    noun = title.lower()
    page_suffix = f" - page {page}" if page > 1 else ""
    full_title = f"{title}{page_suffix} — Formground"
    description = (
        f"{total_products:,} real {noun} from independent makers, listed in full"
        f"{f' (page {page} of {pages})' if pages > 1 else ''}. "
        "Every result links straight to the maker's own site."
    )
    breadcrumb = _breadcrumb_json([
        ("Formground", f"{SITE_URL}/"),
        ("Work", f"{SITE_URL}/work.html"),
        (cat_name, f"{SITE_URL}/work/{cat_slug}.html"),
        (title, f"{SITE_URL}/work/{slug}.html"),
    ])
    grid = "".join(
        product_card_html(p, show_brand=True, variant_count=variant_counts.get(id(p)))
        for p in cards
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head(full_title, description, page_url)}
<script type="application/ld+json">{breadcrumb}</script>
<script type="application/ld+json">{itemlist}</script>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline"><a href="/work.html">Work</a> &rsaquo; <a href="/work/{cat_slug}.html">{html.escape(cat_name)}</a></p>
  <h1>{html.escape(title)}</h1>
  <p class="category-intro">{html.escape(category.get("blurb", "") + " " if category.get("blurb") else "")}{total_products:,} {html.escape(noun)} from independent makers{f" - page {page} of {pages}" if pages > 1 else ""}. Every result links straight to the maker's own site.{_see_also_html(category)}</p>
  {work_menu.render_menu(entries, current_slug=slug, align="left")}
  <div class="grid">{grid}</div>
  {_pager_html(slug, page, pages)}
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
<script>{CARD_CLICK_TRACKING_JS}</script>
{MENU_SCRIPT}
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


def render_category_page(cat_name, entries):
    """/work/furniture.html | lighting | objects: the category's groups and types, in full."""
    cat_slug = work_menu.CATEGORY_SLUGS[cat_name]
    page_url = f"{SITE_URL}/work/{cat_slug}.html"
    mine = work_menu.category_entries(entries, cat_name)
    total = sum(e["n"] for e in mine)
    description = (f"{total:,} pieces of {cat_name.lower()} from independent makers across {len(mine)} types, listed in full - "
                   "each linking straight to the maker's own site.")
    blocks = []
    for group in work_menu.TAXONOMY[cat_name]:
        tiles = "".join(
            _type_tile_html(e)
            for e in sorted((x for x in mine if x["group"] == group), key=lambda x: x["title"].lower())
        )
        label = work_menu.GROUP_LABELS.get(group, group)
        heading = f'<h2 class="type-group-title">{html.escape(label)}</h2>' if len(work_menu.TAXONOMY[cat_name]) > 1 else ""
        blocks.append(f'{heading}<div class="type-grid">{tiles}</div>')
    breadcrumb = _breadcrumb_json([("Formground", f"{SITE_URL}/"), ("Work", f"{SITE_URL}/work.html"), (cat_name, page_url)])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_head(f"{cat_name} — Formground", description, page_url)}
<script type="application/ld+json">{breadcrumb}</script>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{SITE_NAV_HTML}
</header>
<main>
  <p class="page-tagline"><a href="/work.html">Work</a></p>
  <h1>{html.escape(cat_name)}</h1>
  <p class="category-intro">{total:,} pieces from independent makers, listed in full. For a curated selection, see <a href="/edits.html">Edits</a>.</p>
  {work_menu.render_menu(entries, align="left")}
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

    sitemap_slugs = []
    for category, products, cards, variant_counts in computed:
        pages = max(1, math.ceil(len(cards) / CARDS_PER_PAGE))
        for page in range(1, pages + 1):
            chunk = cards[(page - 1) * CARDS_PER_PAGE: page * CARDS_PER_PAGE]
            out = BROWSE_DIR / f"{_page_slug(category['slug'], page)}.html"
            out.write_text(render_browse_page(category, chunk, variant_counts, page, pages, len(products), entries))
            sitemap_slugs.append(f"work/{_page_slug(category['slug'], page)}")
        print(f"work/{category['slug']}: {len(products)} products -> {len(cards)} cards, {pages} page(s)")

    for cat_name, cat_slug in work_menu.CATEGORY_SLUGS.items():
        (BROWSE_DIR / f"{cat_slug}.html").write_text(render_category_page(cat_name, entries))
        sitemap_slugs.append(f"work/{cat_slug}")
    # /work/ itself has no page of its own: the Work page is /work.html
    write_redirect(BROWSE_DIR / "index.html", "/work.html")

    # The menu on the Work page itself (frontend/work.html is hand-written, mirrored to docs/)
    frontend_work = SCRAPER_DIR.parent / "frontend" / "work.html"
    if work_menu.inject_into_page(frontend_work, work_menu.render_menu(entries)):
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
