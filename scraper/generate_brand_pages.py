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
import unicodedata
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
DB_PATH = DATA_DIR / "formground.db"
BRANDS_PATH = SCRAPER_DIR / "brands.json"
DOCS_DIR = SCRAPER_DIR.parent / "docs"
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
        ("marketplace", "/marketplace.html", "Marketplace"),
        ("for-creators", "/for-creators.html", "For Creators"),
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


def product_card_html(p, show_brand=False):
    """
    show_brand adds a brand-name line under the title - off by default
    since every existing caller (render_brand_page's own single-brand
    grid) already has the brand as page context and would find it
    redundant; the New-arrivals page (render_new_page) is the one place
    a mixed-brand grid actually needs it, since "Bench" alone means
    nothing without knowing whose.
    """
    url = p["brand_url"] if p["link_dead"] else p["product_url"]
    alt_text = html.escape(f'{p["product_name"]} by {p["brand"]}')
    image = (
        f'<img src="{html.escape(p["image_url"])}" alt="{alt_text}" loading="lazy">'
        if p["image_url"] else ""
    )
    brand_line = f'<p class="card-brand">{html.escape(p["brand"])}</p>' if show_brand else ""
    return f"""
      <a class="card" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">
        <div class="card-image">{image}</div>
        <div class="card-body">
          <p class="card-title">{html.escape(p["product_name"])}</p>
          {brand_line}
        </div>
      </a>"""


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
    border: 0.5px solid var(--border); margin: 0 0 10px;
  }
  .card-image img { width: 100%; height: 100%; object-fit: cover; }
  .card-image img.contain-fit { object-fit: contain; }
  .card-body { padding: 0; }
  .card-title { font-size: 13px; font-weight: 500; margin: 0; }
  .card-brand { font-size: 12px; color: var(--text-secondary); margin: 2px 0 0; }
  .maker-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 16px; align-items: start; }
  .maker-card { display: block; text-decoration: none; color: inherit; }
  .maker-card-hero {
    aspect-ratio: 4/3; background: var(--surface-1);
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
  /* font-weight explicit since this class is also used on an <h1> in
     render_makers_index (the homepage's own header carries the same
     rule) - browsers bold headings by default, and this needs to look
     identical to the plain <p> version used everywhere else. */
  .page-tagline { font-size: 13px; font-weight: normal; color: var(--text-secondary); margin: 0 0 32px; }
  .category-intro { font-size: 14px; color: var(--text-secondary); max-width: 640px; margin: 0 0 28px; line-height: 1.6; }
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
    flex-shrink: 0; font-size: 13px; font-weight: 600; color: var(--text-secondary);
    background: var(--surface-2); border: 0.5px solid var(--border-strong);
    padding: 7px 10px; border-radius: 999px;
  }

  /* Explicit, not relying on the browser's default [hidden] styling -
     .maker-card's own `display: block` below has the same specificity
     and comes later in source order, so it would otherwise win and
     leave a "hidden" card visible. */
  [hidden] { display: none !important; }
"""


def directory_filter_html(placeholder, category_label):
    return f"""
  <div class="search-wide">
    <div class="ask-box">
      <i class="ti ti-search" aria-hidden="true"></i>
      <span class="ask-box-context">{html.escape(category_label)}</span>
      <input id="directory-filter" type="text" placeholder="{placeholder}" autocomplete="off">
    </div>
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
    function applyFilter(q) {
      q = q.trim().toLowerCase();
      document.querySelectorAll(".maker-grid > a").forEach(function (card) {
        var match = !q || card.textContent.toLowerCase().includes(q);
        card.hidden = !match;
      });
    }
    filterInput.addEventListener("input", function (e) { applyFilter(e.target.value); });
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


def render_brand_page(brand, slug, brand_url, products, umbrellas, country=None):
    tag_list = list(umbrellas) + ([country] if country else [])
    tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tag_list)
    cards = "".join(product_card_html(p) for p in products)
    page_url = f"{SITE_URL}/brands/{slug}.html"
    description = f"{html.escape(brand)}'s work on Formground - {len(products)} pieces, linked straight to their own site."
    # Reusing the same hero image makers.html already picks for this
    # brand (see primary_image_for) as the share-preview image, rather
    # than a generic sitewide fallback - a real photo of what this maker
    # actually makes is a stronger, more specific preview than the
    # Formground logo would be, and it's already computed for free.
    hero_image = primary_image_for(products, umbrellas)
    og_image_tags = (
        f'<meta property="og:image" content="{html.escape(hero_image)}">\n'
        f'<meta name="twitter:image" content="{html.escape(hero_image)}">\n'
        if hero_image else ""
    )
    twitter_card_type = "summary_large_image" if hero_image else "summary"
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
            {"@type": "ListItem", "position": 3, "name": brand, "item": page_url},
        ],
    })
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(brand)} on Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(brand)} on Formground">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
{og_image_tags}<meta name="twitter:card" content="{twitter_card_type}">
<meta name="twitter:title" content="{html.escape(brand)} on Formground">
<meta name="twitter:description" content="{description}">
<script type="application/ld+json">{breadcrumb_json}</script>
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("creators")}
</header>
<main>
  <div class="maker-header">
    <p class="eyebrow">Maker</p>
    <h1 class="maker-name">{html.escape(brand)}</h1>
    <div class="tags">{tags}</div>
    <a class="brand-site-link" href="{html.escape(brand_url)}" target="_blank" rel="noopener noreferrer">Visit site &rarr;</a>
  </div>
  <div class="grid">{cards}</div>
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/privacy.html">Privacy</a> &middot; <a href="/about.html">About</a>
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
    for brand, slug, umbrellas, _count, country, image in sorted(brands_data, key=lambda b: b[0].lower()):
        categories = " · ".join(umbrellas)
        country_html = html.escape(country) if country else "&nbsp;"
        image_tag = f'<img src="{html.escape(image)}" alt="{html.escape(brand)}" loading="lazy">' if image else ""
        items += f"""
      <a class="maker-card" href="/brands/{slug}.html">
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
<title>Makers — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="Every maker currently on Formground, browsable by name.">
<link rel="canonical" href="https://formground.com/makers.html">
<meta property="og:type" content="website">
<meta property="og:title" content="Makers — Formground">
<meta property="og:description" content="Every maker currently on Formground, browsable by name.">
<meta property="og:url" content="https://formground.com/makers.html">
<meta property="og:image" content="{SITE_URL}/favicon-192x192.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Makers — Formground">
<meta name="twitter:description" content="Every maker currently on Formground, browsable by name.">
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link rel="stylesheet" href="/site.css">
<style>{PAGE_CSS}</style>
<style>{HERO_SEARCH_POSITION_CSS}</style>
</head>
<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html("creators")}
</header>
<main style="max-width:1160px;">{directory_filter_html("Filter by name, city, or category…", "Makers")}
  <h1 class="sr-only">Makers</h1>
  <div class="maker-grid">{items}
  </div>
  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/privacy.html">Privacy</a> &middot; <a href="/about.html">About</a>
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


def render_category_redirect_stub(slug):
    """
    A lightweight redirect stub at the old docs/{slug}.html URL, same
    pattern as frontend/search.html's own retirement - noindex, JS
    redirect, real canonical - so an old bookmark or inbound link still
    lands somewhere useful instead of 404ing.
    """
    target = f"/work.html?q={slug}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Formground</title>
<meta name="robots" content="noindex">
<script>
  window.location.replace('{target}');
</script>
<link rel="canonical" href="{SITE_URL}/work.html">
</head>
<body>
<p>Formground has moved this page to <a href="{target}">{target}</a>.</p>
</body>
</html>
"""


# How far back "recently added" reaches before a piece rolls off the
# page - keeps this from slowly turning into a second full catalog as
# first_seen dates accumulate over months. Purely a display window;
# nothing is ever deleted from the database because of it.
NEW_ARRIVALS_WINDOW_DAYS = 90


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
<title>New — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="{description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="website">
<meta property="og:title" content="New — Formground">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{SITE_URL}/favicon-192x192.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="New — Formground">
<meta name="twitter:description" content="{description}">
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link rel="stylesheet" href="/site.css">
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
    &copy; 2026 Formground &middot; <a href="/">&larr; Back to Formground</a> &middot; <a href="/privacy.html">Privacy</a> &middot; <a href="/about.html">About</a>
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
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def _craftspeople_sitemap_slugs():
    """
    Reads data/craftspeople.json directly (rather than relying on
    generate_craftspeople_pages.py having appended to a previous
    sitemap.xml) so render_sitemap() is self-contained and correct
    regardless of which generator last ran - a real ordering bug
    otherwise: this function used to fully rebuild sitemap.xml from
    scratch, which would silently wipe out any craftspeople URLs a
    prior run of generate_craftspeople_pages.py had appended.
    """
    path = DATA_DIR / "craftspeople.json"
    if not path.exists():
        return []
    people = json.loads(path.read_text())
    slugs_seen = {}
    slugs = []
    for person in people:
        slug = slugify(person["name"])
        if slug in slugs_seen and slugs_seen[slug] != person["name"]:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = person["name"]
        slugs.append(slug)
    return sorted(slugs)


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
    for name in firm_names:
        slug = slugify(name)
        if slug in slugs_seen and slugs_seen[slug] != name:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = name
        slugs.append(slug)
    return sorted(slugs)


def _designers_sitemap_slugs():
    """Same self-healing rationale as _craftspeople_sitemap_slugs() -
    reads data/formground.db directly (the real source for
    generate_designers_pages.py, no separate JSON file) so
    render_sitemap() stays correct regardless of which generator last
    ran. A designer gets a page only with 2+ real credited products
    (see generate_designers_pages.py's MIN_PRODUCTS) - mirrored here so
    a designer who drops below that bar doesn't stay listed."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT designer, COUNT(*) as n FROM products
        WHERE designer IS NOT NULL AND TRIM(designer) != '' AND image_url != ''
        GROUP BY designer HAVING n >= 2
    """).fetchall()
    conn.close()
    slugs_seen = {}
    slugs = []
    for name, _ in rows:
        slug = slugify(name)
        if slug in slugs_seen and slugs_seen[slug] != name:
            slug = f"{slug}-{len(slugs_seen)}"
        slugs_seen[slug] = name
        slugs.append(slug)
    return sorted(slugs)


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
        ("https://formground.com/marketplace.html", "weekly", "0.5", None),
        ("https://formground.com/privacy.html", "yearly", "0.2", None),
        ("https://formground.com/makers.html", "weekly", "0.7", today),
        ("https://formground.com/new.html", "weekly", "0.6", today),
    ]
    urls += [(f"https://formground.com/brands/{slug}.html", "weekly", "0.5", today) for slug in brand_slugs]
    craftspeople_slugs = _craftspeople_sitemap_slugs()
    if craftspeople_slugs:
        urls.append(("https://formground.com/craftspeople.html", "weekly", "0.7", today))
        urls += [
            (f"https://formground.com/craftspeople/{slug}.html", "weekly", "0.5", today)
            for slug in craftspeople_slugs
        ]
    designer_slugs = _designers_sitemap_slugs()
    if designer_slugs:
        urls.append(("https://formground.com/designers.html", "weekly", "0.7", today))
        urls += [
            (f"https://formground.com/designers/{slug}.html", "weekly", "0.5", today)
            for slug in designer_slugs
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
    BRANDS_DIR.mkdir(parents=True, exist_ok=True)

    # New-arrivals page: first_seen is only ever real (not NULL) for a
    # product genuinely detected as new since the previous scrape (see
    # scrape.py's run()) - a pre-existing product's unknown real add-
    # date was never guessed at, so this naturally excludes everything
    # already in the catalog before the feature existed rather than
    # needing a separate check here.
    cutoff = (datetime.date.today() - datetime.timedelta(days=NEW_ARRIVALS_WINDOW_DAYS)).isoformat()
    new_arrivals = sorted(
        (dict(row) for row in rows
         if row["first_seen"] and row["first_seen"] >= cutoff and row["brand"] not in hidden_brands),
        key=lambda p: p["first_seen"],
        reverse=True,
    )
    (DOCS_DIR / "new.html").write_text(render_new_page(new_arrivals))

    slugs_seen = {}
    makers_data = []
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
        page = render_brand_page(brand, slug, brand_url, products, umbrellas, country)
        (BRANDS_DIR / f"{slug}.html").write_text(page)
        image = primary_image_for(products, umbrellas)
        makers_data.append((brand, slug, umbrellas, len(products), country, image))

    (DOCS_DIR / "makers.html").write_text(render_makers_index(makers_data))
    for slug in RETIRED_CATEGORY_SLUGS:
        (DOCS_DIR / f"{slug}.html").write_text(render_category_redirect_stub(slug))
    (DOCS_DIR / "sitemap.xml").write_text(render_sitemap(sorted(m[1] for m in makers_data)))

    print(f"Generated {len(makers_data)} brand pages, makers.html, "
          f"{len(RETIRED_CATEGORY_SLUGS)} retired-category redirect stubs, "
          f"new.html ({len(new_arrivals)} new arrival{'s' if len(new_arrivals) != 1 else ''}), "
          f"and sitemap.xml ({sum(m[3] for m in makers_data)} products total).")


if __name__ == "__main__":
    generate()
