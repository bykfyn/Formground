"""
Formground scraper.

WHAT THIS DOES:
  Reads the brand list from brands.json, visits each brand's site,
  and pulls out product info (name, category, material, dimensions,
  link back to the product page). Saves everything into the shared
  database at data/formground.db.

WHO RUNS THIS:
  Normally nobody manually - the GitHub Action (.github/workflows/scrape.yml)
  runs this automatically on a schedule. You can also run it yourself with:

    python scrape.py

HOW IT'S ORGANIZED:
  - Brands marked "scrapable": false in brands.json are skipped entirely
    (e.g. Bennet Schlesinger, whose site disallows automated access via
    robots.txt - we respect that rather than working around it).
  - Each brand can have its own extraction logic, since every site is
    built differently. Right now only Kieran Kinsella has a working
    extractor, as a proof of concept. Adding more brands means adding
    more small functions like extract_kieran_kinsella() below.
"""

import argparse
import concurrent.futures
import datetime
import gzip
import html
import json
import re
import sqlite3
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
DB_PATH = DATA_DIR / "formground.db"
BRANDS_PATH = SCRAPER_DIR / "brands.json"
REPORT_PATH = DATA_DIR / "last_scrape_report.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FormgroundBot/0.1; "
        "+discovery tool for independent design brands; "
        "respects robots.txt; remove-on-request)"
    )
}

# Hard ceilings so a single misbehaving site (one that never returns an
# empty page, for instance) can't turn a run that should take minutes into
# one that runs for hours or days. MAX_SECONDS_PER_BRAND is the one that
# actually matters - it bounds worst-case time directly, regardless of how
# many pages a real catalog happens to need (In Common With's heavy
# variant-as-separate-product listings need ~90 pages to see its full,
# legitimate ~550-design catalog, so a low page count alone would cut into
# real data rather than just catching runaway pagination). MAX_PAGES_PER_BRAND
# stays as a generous secondary backstop for a server that responds
# instantly but never signals "done."
MAX_PAGES_PER_BRAND = 200            # 200 x 250/page = 50,000 raw items - backstop, not expected to bind
MAX_SECONDS_PER_BRAND = 5 * 60       # give up on one brand after 5 minutes no matter what
MAX_TOTAL_RUNTIME_SECONDS = 20 * 60  # whole run gives up and reports what it has after 20 minutes

# run() scrapes this many brands concurrently (see run()'s own comment) -
# each brand's own extractor is almost entirely spent waiting on HTTP
# responses from *that brand's own site*, not CPU work, so running several
# at once doesn't put more load on any single target - it just stops one
# slow brand's network wait from blocking every brand after it in the
# list. Added 2026-09-13 once the catalog's growth trajectory (a few
# hundred brands, not ~50) made the old fully-sequential run a real
# scaling problem, not just a theoretical one - a handful of workers is
# enough to meaningfully multiply how much fits in MAX_TOTAL_RUNTIME_SECONDS
# without needing to touch that ceiling itself.
MAX_CONCURRENT_BRANDS = 8


def _fetch_json(url, retries=2, timeout=30):
    """
    GET a URL and parse it as JSON, retrying on timeouts/transient errors
    before giving up. Some stores (e.g. Another Country's WooCommerce Store
    API) are slow enough on larger pages that a single 15s attempt isn't
    reliable - a full page of real data shouldn't be dropped over one
    slow response.
    """
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_error = e
            if attempt < retries:
                time.sleep(2)
    print(f"  Could not fetch {url} after {retries + 1} attempts: {last_error}")
    return None


def setup_database():
    """Creates the products table if it doesn't already exist."""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            brand_url TEXT NOT NULL,
            product_name TEXT NOT NULL,
            product_url TEXT NOT NULL,
            category TEXT,
            material_options TEXT,
            dimensions TEXT,
            notes TEXT,
            thin INTEGER DEFAULT 0,
            image_url TEXT,
            designer TEXT,
            last_checked TEXT,
            first_seen TEXT
        )
    """)
    # ALTER TABLE ADD COLUMN fails if the column already exists - this only
    # matters for a database created before these columns existed, so it's
    # safe to ignore that specific failure.
    #
    # first_seen has no DEFAULT, so adding it to an existing database
    # leaves every already-there row NULL - exactly the semantics wanted
    # for the "New" page (see run()'s carry-forward logic below): a
    # product already in the catalog before this column existed has an
    # unknown real add-date, not "added today," so it must not show up
    # as new. Only a product that's genuinely absent from the previous
    # scrape gets a real first_seen date going forward.
    for statement in (
        "ALTER TABLE products ADD COLUMN thin INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN image_url TEXT",
        "ALTER TABLE products ADD COLUMN designer TEXT",
        "ALTER TABLE products ADD COLUMN link_dead INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN first_seen TEXT",
    ):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn


def save_product(conn, product):
    """
    Inserts or updates a single product record. "thin" marks an entry that
    represents something coarser than an individual product - a named
    collection/series rather than a specific piece (see
    extract_paola_paronetto) - so the frontend can give it the dashed-
    border "different kind of entry" treatment already decided on, same
    size and prominence either way, never a lesser one.

    "designer" is collected but deliberately not surfaced on cards today
    (see extract_baleri_italia) - it's the only one of the 16 extractors
    where this is easy to capture, and showing it there but nowhere else
    would credit some products' designers by name and not others, purely
    from scraping convenience. Stored anyway rather than discarded, in
    case more brands' extractors pick this up later and it can be shown
    consistently across all of them at once.

    "first_seen" (the "New" page's data source) must be set by the
    caller before calling this - see run()'s carry-forward-or-stamp-today
    logic, computed once per brand right before that brand's old rows are
    deleted. Never computed in here, since by the time save_product runs
    the old row (and its real first_seen) is already gone.
    """
    conn.execute("""
        INSERT INTO products (brand, brand_url, product_name, product_url,
                               category, material_options, dimensions, notes, thin, image_url, designer, last_checked, first_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
    """, (
        product["brand"],
        product["brand_url"],
        product["product_name"],
        product["product_url"],
        product.get("category", ""),
        json.dumps(product.get("material_options", [])),
        product.get("dimensions", ""),
        product.get("notes", ""),
        1 if product.get("thin") else 0,
        product.get("image_url", ""),
        product.get("designer", ""),
        product.get("first_seen"),
    ))
    conn.commit()


# ---------------------------------------------------------------------------
# PER-BRAND EXTRACTORS
# Each brand's site is structured differently, so each gets its own small
# function. This is the proof-of-concept extractor - it's based on the real
# product pages already confirmed for Kieran Kinsella during Phase 1 triage.
# ---------------------------------------------------------------------------

def _squarespace_image_url(img_tag):
    """
    Squarespace lazy-loads images - the real URL is in data-src, and src
    is often left blank until JS runs (confirmed on H. Bigeleisen; Kieran
    Kinsella and Yird Ceramics populate both, so data-src is still the
    reliable one to prefer). Shared by the three Squarespace-based
    extractors below.
    """
    if not img_tag:
        return ""
    return img_tag.get("data-src") or img_tag.get("src") or ""

def extract_kieran_kinsella(brand):
    """
    Known structured product pages on kierankinsella.com (confirmed during
    Phase 1 triage - the main gallery page itself is unstructured photography,
    so we go directly to the known /wood product pages instead).
    """
    known_product_pages = [
        "bulb-wood", "kettle-wood", "bench-wood", "cauldron-wood",
        "drop-wood", "dome-wood",
    ]

    products = []
    for slug in known_product_pages:
        url = f"{brand['url'].rstrip('/')}/{slug}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # bench-wood turned out to be a multi-item gallery, not a single
        # product page like the other five - its <h3> ("Benches, Seat &
        # Double Trunk") is a section heading, not any one piece's name.
        # The real per-piece names live in each gallery image's lightbox
        # caption (data-description), confirmed live: 5 real distinct
        # pieces (Macaroni Bench, Double Trunk Bench, Bench with chains,
        # Seat, Cloud Bench), each with its own image in the same button.
        # Check for this pattern generically rather than hardcoding it to
        # bench-wood, in case another of these pages is also a gallery.
        lightbox_buttons = soup.find_all(
            "button", attrs={"data-sqsp-image-classic-block-lightbox-button": True}
        )
        gallery_items = []
        for btn in lightbox_buttons:
            caption = BeautifulSoup(
                html.unescape(btn.get("data-description", "")), "html.parser"
            ).get_text(strip=True)
            if caption:
                gallery_items.append((caption, btn.find("img")))

        if gallery_items:
            for name, img in gallery_items:
                products.append({
                    "brand": brand["name"],
                    "brand_url": brand["url"],
                    "product_name": name,
                    "product_url": url,
                    "category": "Furniture / Object",
                    "material_options": [],
                    "dimensions": "",
                    # Every Kieran Kinsella piece is hand-carved wood - a
                    # brand-wide fact, not a per-item one, so hardcoding it
                    # here just repeats the identical phrase on all 10
                    # cards. Same reasoning as material_options that just
                    # restate the category (see materialDuplicatesCategory
                    # in frontend/index.html) - left blank rather than
                    # shown as if it distinguished this piece from another.
                    "notes": "",
                    "image_url": _squarespace_image_url(img),
                })
        else:
            # The page's only <h1> is the Squarespace site logo/title
            # ("Kieran Kinsella"), not the product name - confirmed by
            # inspecting the live page. The real product name is the
            # page's <h3> instead (true for the other five pages).
            title = soup.find("h3")
            product_name = title.get_text(strip=True) if title else slug.replace("-", " ").title()

            products.append({
                "brand": brand["name"],
                "brand_url": brand["url"],
                "product_name": product_name,
                "product_url": url,
                "category": "Furniture / Object",
                "material_options": [],  # would need a follow-up pass to parse material text
                "dimensions": "",
                # Same reasoning as the gallery-items branch above - every
                # piece is hand-carved wood, a brand-wide fact repeated
                # identically on every card, not a per-item distinguisher.
                "notes": "",
                "image_url": _squarespace_image_url(soup.find("img")),
            })
        time.sleep(1)  # be polite - don't hammer the site

    return products


def extract_paola_paronetto(brand):
    """
    paolaparonetto.com only publishes named design collections
    (Bottiglie, Vulcano Etna, Cactus...), not individual products - each
    collection's own page is confirmed purely editorial (a name, a short
    description, an image gallery), with no per-piece names, materials,
    or dimensions underneath it to extract. Rather than skip the brand
    entirely for lacking product-level data, each named collection is
    treated as its own lightweight entry - "collection is the minimum
    unit of inclusion" here, one level more granular than the existing
    "brand is the minimum unit of inclusion" principle already applied to
    catalog-less brands elsewhere. Material is hardcoded to Ceramic since
    that's a known, stated fact about the whole brand, not a guess.
    """
    url = f"{brand['url'].rstrip('/')}/collezioni/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    seen_slugs = set()
    for a in soup.find_all("a", href=True):
        if "/collezioni/" not in a["href"]:
            continue
        slug = a["href"].split("/collezioni/", 1)[1].strip("/")
        name = a.get_text(strip=True)
        if not slug or not name or slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # The listing page itself has no images - each collection's own
        # page does (confirmed live: a "slider-slide-image" gallery), so
        # this needs one extra small fetch per collection to get a real
        # thumbnail rather than leaving this brand image-less.
        image_url = ""
        try:
            detail_resp = requests.get(a["href"], headers=HEADERS, timeout=15)
            detail_resp.raise_for_status()
            detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
            img = detail_soup.find("img", class_="slider-slide-image")
            image_url = img.get("src", "") if img else ""
        except requests.RequestException as e:
            print(f"  Could not fetch collection image at {a['href']}: {e}")
        time.sleep(1)  # be polite - don't hammer the site

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": a["href"],
            # "Ceramics" isn't a guess here - the entire brand only works
            # in ceramic (confirmed repeatedly during brand research), so
            # this is as factual as material_options below. Left blank
            # before, this brand was wrongly excluded from the "Ceramics"
            # browse chip - the chip's query extracts category="ceramics"
            # AND material="ceramic", both required, so a real material
            # match with no category still failed.
            "category": "Ceramics",
            "material_options": ["Ceramic"],
            "dimensions": "",
            # No explanatory note here on purpose - the dashed border
            # (thin=True) already signals "different kind of entry."
            # Formground's job is discovery, not explaining itself; the
            # user infers from the image and follows through to the
            # brand's own site for anything more.
            "notes": "",
            "thin": True,
            "image_url": image_url,
        })

    return products


def extract_hbigeleisen(brand):
    """
    hbigeleisen.com is Squarespace commerce using a "Summary Block" for its
    /in-stock catalog page - each item is a real, separate <a class="product">
    with its own title and price, no variant-as-product duplication like the
    Shopify brands (confirmed by inspecting the live page).
    """
    url = f"{brand['url'].rstrip('/')}/in-stock"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    for a in soup.find_all("a", class_="product", href=True):
        title_el = a.find(class_="product-title")
        name = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": f"{brand['url'].rstrip('/')}{a['href']}",
            "category": _infer_category_from_name(name, "", brand["name"]),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": _squarespace_image_url(a.find("img")),
        })

    return products


def extract_yird_ceramics(brand):
    """
    yirdstudio.com is Squarespace commerce using a "Product List Block" -
    each item is an <a class="product-list-item-link"> whose text runs
    together as "Name" + price + status (e.g. "Sold out"), confirmed by
    inspecting the live /shop page. Split those apart with a regex rather
    than trusting whitespace, since there's no separating markup.
    """
    url = f"{brand['url'].rstrip('/')}/shop"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    seen_urls = set()
    for a in soup.find_all("a", class_="product-list-item-link", href=True):
        product_url = f"{brand['url'].rstrip('/')}{a['href']}"
        if product_url in seen_urls:
            continue
        seen_urls.add(product_url)

        text = a.get_text(strip=True)
        # Name runs up to the currency code (PLN) or "Sale Price:"/"Sold out".
        match = re.search(r"(PLN|Sale Price:|Sold out)", text)
        name = text[: match.start()].strip() if match else text
        # Sold-out/on-sale status used to go in notes, but that's
        # inventory/commerce status, not a design fact - inconsistent
        # with the existing "no pricing chrome on cards" principle, so
        # it's not captured at all now, not just hidden.

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": product_url,
            "category": "Ceramics",
            "material_options": ["Ceramic"],
            "dimensions": "",
            "notes": "",
            "image_url": _squarespace_image_url(a.find("img")),
        })

    return products


def extract_ingo_maurer(brand):
    """
    ingo-maurer.com has no product API, but its single /en/products/ page
    server-renders the entire catalog (266 items as of this writing) as
    one isotope grid - name, image, and link for every product in one
    fetch, same shape as H. Bigeleisen/Yird Ceramics above. Category is
    hardcoded "Lighting" since the brand makes nothing else (confirmed
    by scanning all live product names - no furniture/ceramics/objects
    mixed in). About half the listing (129 of 266) is marked
    "Discontinued Models" via a `pc10`/`is-ceased` class pair on each
    <li> - these are excluded, same principle as not showing dead links
    elsewhere: a design no longer produced isn't a real search result.
    """
    url = f"{brand['url'].rstrip('/')}/en/products/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    domain = brand["url"].rstrip("/")
    products = []
    for li in soup.find_all("li", class_="data-cell"):
        if "is-ceased" in li.get("class", []):
            continue

        title_el = li.find(class_="isotope-data-title")
        link_el = title_el.find("a", href=True) if title_el else None
        if not link_el:
            continue

        img = li.find("img")
        image_url = img.get("src", "") if img else ""
        # One listing ("18 x 18") points at a "coming soon" placeholder
        # graphic instead of a real product photo - a real image URL,
        # but not a real product photo, so it's dropped here rather than
        # relying on the generic "no image" filter downstream to catch it.
        if "comingsoon" in image_url.lower():
            continue
        if image_url.startswith("/"):
            image_url = f"{domain}{image_url}"

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": link_el.get_text(strip=True),
            "product_url": f"{domain}{link_el['href']}",
            "category": "Lighting",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_url,
        })

    return products


# Källemo's own category folders under /en/products/ - "archive" is
# excluded entirely (discontinued designs, same treatment as Ingo
# Maurer's ceased models); the rest map to a clean single-word category
# where the folder is unambiguous, and blank where it genuinely mixes
# object types (confirmed by reading each category's real product names
# before deciding - "sofas-easychairs" mixes sofas/armchairs, "other"
# and "limited" mix benches/footstools/cabinets/art objects).
KALLEMO_CATEGORIES = {
    "chairs": "Chair",
    "tables": "Table",
    "shelves": "Shelf",
    "sofas-easychairs": "",
    "other": "",
    "limited": "",
}


def extract_kallemo(brand):
    """
    kallemo.se (Joomla, no product API) organizes its catalog into a
    handful of category listing pages under /en/products/{category} -
    each one server-renders every item's name, designer, and image in
    one fetch (confirmed live: no per-product fetch needed for the data
    Formground actually shows). Designer is captured but not displayed
    on cards, same reasoning as Baleri Italia's designer field - showing
    it for only the brands whose markup happens to make it easy would
    credit some products' designers and not others, purely from scraping
    convenience, not a real editorial choice.
    """
    domain = brand["url"].rstrip("/")
    products = []

    for category_slug, category_label in KALLEMO_CATEGORIES.items():
        url = f"{domain}/en/products/{category_slug}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for title_el in soup.find_all(class_="el-title"):
            link_el = title_el.find_parent("a", href=True)
            if not link_el:
                continue

            img = link_el.find("img")
            image_url = img.get("src", "") if img else ""
            if image_url.startswith("/"):
                image_url = f"{domain}{image_url}"

            designer_el = link_el.find(class_="el-meta")

            products.append({
                "brand": brand["name"],
                "brand_url": brand["url"],
                "product_name": title_el.get_text(strip=True),
                "product_url": f"{domain}{link_el['href']}",
                "category": category_label,
                "material_options": [],
                "dimensions": "",
                "notes": "",
                "image_url": image_url,
                "designer": designer_el.get_text(strip=True) if designer_el else "",
            })

        time.sleep(1)  # be polite - don't hammer the site

    return products


def _split_joris_poggioli_materials(raw):
    """
    Joris Poggioli's own material field is free-text prose, not a
    clean delimited list - about a quarter of the 74 products (found
    via a real user report on "Fernando") read like "Rosewood 100%
    gloss & cream velvet or Brushed stainless steel & dark olive green
    velvet", which a plain "/" split (the site's more common separator,
    e.g. "Black bronze / Plywood") leaves untouched as one long
    sentence-like blob instead of short material tags. This handles
    the real conjunctions found across the catalog ("/", " or ", " & ",
    " and ", ",") and drops the "Other finishes available upon
    request" caveat some entries end with (informational, not a
    material). Not a perfect grammatical parse - a few fragments stay
    slightly phrase-like (e.g. "Sculpted in massive oak") rather than a
    single clean noun - but a real improvement over one giant sentence.
    """
    text = re.sub(r"\.?\s*other finishes available upon request\.?", "", raw, flags=re.IGNORECASE)
    parts = re.split(r"\s*/\s*|\s+or\s+|\s*&\s*|\s+and\s+|\s*,\s*", text, flags=re.IGNORECASE)
    cleaned = []
    for p in parts:
        # A separator sequence like ", or " leaves a leading "or "/"and "
        # on the next fragment once the comma's already been split on -
        # strip that leftover conjunction rather than keeping it as
        # part of the material name.
        p = re.sub(r"^(or|and)\s+", "", p.strip(), flags=re.IGNORECASE)
        p = p.strip().rstrip(".")
        if p:
            cleaned.append(p)
    return cleaned


def extract_joris_poggioli(brand):
    """
    jorispoggioli.com is a Next.js app with no robots.txt at all (no
    file exists - the site returns its own 404 page for the path,
    confirmed live) and no bot restrictions of any kind. It doesn't
    need per-product fetches or even a dedicated listing page: the
    homepage's own server-rendered __NEXT_DATA__ JSON blob already
    embeds the complete "design" catalog (74 items) with clean
    structured fields - name, category (designType), material,
    dimensions, and image - richer data than most brands here, in one
    fetch. The site's separate "architecture" section (real interior/
    hospitality project case studies, not purchasable objects - same
    shape as Piet Hein Eek's excluded categories) isn't part of this
    data at all, so there's nothing to filter out.
    """
    domain = brand["url"].rstrip("/")
    try:
        resp = requests.get(domain, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {domain}: {e}")
        return []

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text, re.S,
    )
    if not match:
        print(f"  Could not find __NEXT_DATA__ on {domain}")
        return []

    try:
        data = json.loads(match.group(1))
        items = data["props"]["pageProps"]["designItems"]
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  Unexpected __NEXT_DATA__ shape on {domain}: {e}")
        return []

    products = []
    for item in items:
        dims = item.get("dimensions", {}) or {}
        dimension_parts = [
            f"{label} {dims[key]}"
            for key, label in (("height", "H"), ("width", "W"), ("depth", "D"), ("diameter", "Ø"))
            if dims.get(key)
        ]

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": item.get("name", ""),
            "product_url": f"{domain}/design/{item['designTypeSlug']}/{item['slug']}",
            "category": item.get("designType", "").title(),
            "material_options": _split_joris_poggioli_materials(item.get("material") or ""),
            "dimensions": " x ".join(dimension_parts) + " cm" if dimension_parts else "",
            "notes": "",
            "image_url": item.get("imageGrid", {}).get("url", ""),
        })

    return products


# moustache.fr (PrestaShop) has no single "all products" listing that's
# actually complete - its real "86-all" category turned out to be its
# own distinct 54-item subset, not a superset (confirmed live: only 12
# of "chaises"(21)'s 54 products also appear there). The site instead
# runs two parallel, near-non-overlapping category trees under the same
# /en/ locale - an older French-slugged one (chaises, etageres, tables-
# basses...) and a newer English-slugged one (chairs, shelves, coffee-
# tables...) - most likely because English URL slugs were only ever set
# on newer categories, not because these are different markets. Rather
# than reverse-engineer which tree is canonical, every real object-type
# category from both trees is fetched and results are deduped by
# Prestashop's own numeric product ID, which is stable across whichever
# category page a product happens to appear on. Aggregator-only
# categories (all/new arrivals/collectible/divers/produits) are
# deliberately skipped - not real object types, and every product
# checked from them also appears under a specific-type category anyway.
MOUSTACHE_CATEGORIES = {
    "21-chaises": "Chair", "24-etageres": "Shelf", "25-bancs": "Bench",
    "26-tables-basses": "Coffee table", "28-portes-manteaux-pateres": "Coat rack",
    "29-luminaire": "Lighting", "31-lampes-de-table": "Table lamp",
    "32-suspensions": "Pendant light",
    "35-vases": "Vase", "36-vide-poches": "Catchall tray", "37-miroirs": "Mirror",
    "38-carafes": "Carafe", "39-centres-de-table": "Centerpiece",
    "40-corbeilles-a-fruits": "Fruit basket", "41-tapis": "Rug",
    "68-wallpapers-posters": "Wallpaper", "69-armchairs": "Armchair",
    "72-stool": "Stool", "73-sculpture": "Sculpture", "88-sofas": "Sofa",
    "102-benches": "Bench", "103-sofas": "Sofa", "105-chairs": "Chair",
    "107-stool": "Stool", "109-shelves": "Shelf", "111-armchairs": "Armchair",
    "113-doors-coats": "Coat rack", "114-coffee-tables": "Coffee table",
    "117-tables": "Table", "118-offices": "Desk", "119-dressers-sideboards": "Sideboard",
    "123-carafes": "Carafe", "125-centerpieces": "Centerpiece",
    "128-fruit-baskets": "Fruit basket", "132-mirrors": "Mirror",
    "134-wallpapers": "Wallpaper", "135-sculpture": "Sculpture", "138-rugs": "Rug",
    "140-vases": "Vase", "143-shelf-to-screw": "Shelf", "146-table-lamps": "Table lamp",
    "147-suspensions": "Pendant light", "150-appliques": "Wall light",
    "153-floor-lamps": "Floor lamp", "155-sculpture": "Sculpture",
    "157-photography": "Photography",
}


def extract_moustache(brand):
    """
    Each color is its own top-level PrestaShop product (confirmed live:
    "Gelato chair" alone has 42 separate product IDs, one per color -
    78% of the raw catalog turned out to be this same pattern already
    seen on several Shopify/WooCommerce brands, just with zero
    distinguishing text in the name itself - the color only lives in
    the product URL's "#/{id}-color-{name}" fragment). Grouped by exact
    product name (no _base_name() splitting needed, there's no suffix
    to strip) with colors parsed out of that fragment and folded into
    material_options, same treatment as every other brand's variant-as-
    separate-product problem. Fabric swatch listings ("Extra Bold fabric
    samples") are excluded by a "sample" name check, same pattern used
    for Grain's material samples.
    """
    domain = brand["url"].rstrip("/")
    seen_ids = set()
    raw_products = []

    for category_slug, category_label in MOUSTACHE_CATEGORIES.items():
        page = 1
        while page <= MAX_PAGES_PER_BRAND:
            url = f"{domain}/en/{category_slug}"
            if page > 1:
                url += f"?page={page}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  Could not fetch {url}: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.find_all("article", class_="product-miniature")
            if not articles:
                break

            for article in articles:
                product_id = article.get("data-id-product")
                if not product_id or product_id in seen_ids:
                    continue
                seen_ids.add(product_id)

                link_el = article.find("a", class_="product-thumbnail", href=True)
                name_el = article.find(class_="product-miniature-name")
                img = article.find("img")
                if not link_el or not name_el:
                    continue

                name = name_el.contents[0].strip() if name_el.contents else name_el.get_text(strip=True)
                if "sample" in name.lower():
                    continue  # fabric swatches, not a design object (e.g. "Extra Bold fabric samples")
                href = link_el["href"]
                color_match = re.search(r"#/\d+-color-([a-z0-9_]+)", href)
                color = color_match.group(1).replace("_", " ").title() if color_match else ""

                raw_products.append({
                    "name": name,
                    "product_url": href.split("#")[0],
                    "category": category_label,
                    "color": color,
                    "image_url": img.get("src", "") if img else "",
                })

            if not soup.find("a", href=re.compile(r"\?page=" + str(page + 1))):
                break
            page += 1
            time.sleep(1)  # be polite - don't hammer the site

    grouped = {}
    for p in raw_products:
        grouped.setdefault(p["name"], []).append(p)

    products = []
    for name, group in grouped.items():
        first = group[0]
        colors = sorted({p["color"] for p in group if p["color"]})
        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": first["product_url"],
            "category": first["category"],
            "material_options": colors,
            "dimensions": "",
            "notes": "",
            "image_url": first["image_url"],
        })

    return products


def extract_baleri_italia(brand):
    """
    baleri-italia.com has a "products.json" endpoint too, but unlike a real
    Shopify store it returns a page of pre-rendered HTML in a "content"
    field rather than structured product data - a custom AJAX setup, not
    the Shopify API. Its "page" query param is silently ignored (every
    page number returns the identical first page, and "hasMorePages" is
    always true regardless) - confirmed by comparing page=1/2/3 directly,
    and the real cause of a run that hit the 5-minute per-brand safety
    limit fetching the same 24 products over and over. No working
    pagination mechanism was found without reverse-engineering the site's
    own frontend requests, which isn't worth it for one brand - so this
    only fetches the single page it can reliably get. Real catalog is
    almost certainly larger than the ~24 products this returns; that's a
    known, documented limitation, not a bug in this function.
    """
    base = brand["url"].rstrip("/")
    products = []

    data = _fetch_json(f"{base}/products.json?limit=24&page=1")
    if data is None or not data.get("content"):
        return products

    fragment = BeautifulSoup(data["content"], "html.parser")
    for a in fragment.find_all("a", class_="previewBox", href=True):
        title_el = a.find(class_="previewBox__title")
        type_el = title_el.find_next("p") if title_el else None
        # Designer/year ("subtitle" element) is collected but not shown
        # on cards (see save_product's docstring) - this is the only
        # extractor of the 16 whose markup makes it easy to grab, and
        # displaying it here alone would credit some products' designers
        # by name and not others, purely from scraping convenience.
        designer_el = a.find(class_="subtitle")

        name = title_el.get_text(strip=True) if title_el else ""
        product_type = type_el.get_text(strip=True) if type_el else ""
        full_name = f"{name} {product_type}".strip() if product_type else name

        img = a.find("img")
        image_url = img.get("src", "") if img else ""
        if image_url.startswith("/"):
            image_url = f"{base}{image_url}"

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": full_name,
            "product_url": a["href"],
            "category": product_type,
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_url,
            "designer": designer_el.get_text(strip=True) if designer_el else "",
        })

    return products


# Structural signals (not text guesses) that a listing isn't a real
# design object at all - confirmed live per brand as each was found:
# "Finish Samples" (In Common With's swatch listings, e.g. "Saga
# Finishes"), "Swatches" (Another Country's fabric samples), "Spare
# Part"/"Spare Parts" (101cph's mounting plates/cable kits), "Libri
# fisici" (Bitossi's actual physical books), "Architectuur"/
# "Architectuur projecten"/"Inrichtingen"/"Horeca" (Piet Hein Eek runs
# real architecture/interior-fit-out case studies - hospitality venues,
# private homes - through the same WooCommerce catalog as its actual
# furniture; confirmed live these are all price=0 project writeups, not
# purchasable objects). Checked against each brand's real category
# breakdown before adding - e.g. Bitossi's "Designers" category was NOT
# added here despite sounding similarly suspicious, because its actual
# products (Vaso, Bolo) are real ceramic pieces just organized by which
# designer made them, and Piet Hein Eek's much larger "Opdrachten"
# (commissions) category was deliberately NOT added here either - it
# mixes those same project writeups with genuinely real, purchasable
# custom/bespoke furniture, too broad a net to exclude cleanly.
# "Care Kit" (Galvin Brothers' furniture maintenance kit, same shape as
# Piet Hein Eek's maintenance sets - not a design object). "editorial"/
# "musica"/"operativo" (Utilitario Mexicano's books/magazines, vinyl
# records, and a gift-card listing - same "Libri fisici" shape as
# Bitossi, just Spanish-language category names this time).
EXCLUDED_CATEGORIES = {
    "finish samples", "swatches", "spare part", "spare parts", "libri fisici",
    "architectuur", "architectuur projecten", "inrichtingen", "horeca",
    "care kit", "editorial", "musica", "operativo",
}

# Utilitario Mexicano's product_type is blank across its entire ~490-
# item catalog, so EXCLUDED_CATEGORIES above (which only checks
# product_type) never catches its non-design items - its real
# taxonomy lives in Shopify `tags` instead, terse Spanish category
# words: "abarrotes"/"refresco"/"soda" (groceries/drinks - confirmed
# live: a kombucha, an energy drink, and a "club" soda all carry
# these), "aseo"/"baño"/"cuidado personal" (personal care - a woven
# bath scrubber), "editorial"/"libro"/"libros" (a physical book,
# "musica"/"operativo" above are this same brand's other Spanish
# category names, just via product_type on different listings).
# "accesorio"/"accesorios" was deliberately NOT added here - too broad,
# and one such listing (a wall coat hook, "Gancho / Perchero Peltre")
# is a genuine design object. Checked as whole-tag membership, not a
# substring search, so a real product's own tag can't accidentally
# match a fragment of one of these words.
EXCLUDED_TAGS = {
    "abarrotes", "refresco", "soda", "aseo", "baño", "cuidado personal",
    "editorial", "libro", "libros",
}

# Some Shopify brands use product_type for something other than a real
# category - confirmed on Pinch, where it's actually an electrical
# certification mark or stock/bed-size status ("UL", "CE", "US Ex
# display"...), not a category at all. Left in place, this caused the
# same real design to appear as separate duplicate entries (grouped by
# (product_type, name), so "Ewer table light" tagged UL and tagged CE
# became two products instead of one). These known-junk values are
# treated as blank for both grouping and display - real product_type
# values on other brands are left untouched, even generic-sounding ones
# that do meaningfully distinguish otherwise-identically-named products
# (e.g. Bitossi's "Novità"/"Classici").
JUNK_PRODUCT_TYPES = {
    "ul", "ce", "stock", "us bed", "uk bed", "us ex display",
    "uk ex display", "studio sale",
}


def _clean_product_type(product_type):
    value = (product_type or "").strip()
    return "" if value.lower() in JUNK_PRODUCT_TYPES else value


# Bitossi Ceramiche names most pieces after their generic object type
# rather than a proper name (confirmed live: "Vaso", "Alzata",
# "Scultura", "Sgabello" are literally the names shown on their own
# site's "Prodotti"/products page, not hidden category data) - and its
# Shopify product_type is a collection line ("Classici", "Novità"), not
# an object type at all, so category ends up useless for most of its
# catalog. Checked against the real data before adding this: covers 55
# of 88 Bitossi products. Harmless elsewhere - an English product name
# won't start with one of these Italian words by coincidence.
ITALIAN_OBJECT_TYPES = {
    "vaso": "Vase", "bolo": "Bowl", "boletto": "Bowl", "tavolino": "Table",
    "alzata": "Stand", "scultura": "Sculpture", "sgabello": "Stool",
    "centrotavola": "Centerpiece", "miniatura": "Figurine", "statua": "Statue",
    "posacenere": "Ashtray", "ciotola": "Bowl", "piatto": "Plate",
}

# Bitossi's known collection-line labels, which aren't a real object-type
# category - a blank category also qualifies (nothing to lose by trying
# name-based inference in that case either).
UNHELPFUL_CATEGORIES = {"classici", "novità", "collezioni", "designers", ""}

# English object-type keyword fallback, for brands whose Shopify
# product_type carries no real category signal at all (confirmed on
# Pinch: 148 of 148 products had product_type either blank or one of
# JUNK_PRODUCT_TYPES, meaning the live search's category filter could
# never surface a single one of them - "sofa" didn't even return
# Pinch's own "Boyd sofa" - see project memory). Same idea as
# ITALIAN_OBJECT_TYPES above, just keyed on the object-type word
# already present in most English product names instead of a foreign
# first word.
#
# Checked as an ordered list, not a dict, because match order matters:
# a multi-word phrase has to be tried before any single word it
# contains, or the wrong single word wins first - confirmed against
# every real Pinch product name before shipping this (see project
# memory): "Ewer table light" is a lighting fixture, but checking bare
# "table" first would tag it furniture; "Clyde lamp table" is a side
# table (furniture), but checking bare "lamp" first would tag it
# lighting. Multi-word entries come first for exactly this reason.
# Left unmatched on purpose rather than guessed where the name gives no
# real signal (e.g. "Mercier press", "Nim Copper") - same "don't
# fabricate a taxonomy" standard as the rest of this file.
ENGLISH_OBJECT_TYPE_KEYWORDS = (
    ("four poster bed", "Bed"), ("pleated bed", "Bed"),
    ("sofa system", "Sofa"), ("slipcover sofa", "Sofa"),
    ("wingback armchair", "Armchair"), ("low back armchair", "Armchair"),
    ("pod pendant light", "Pendant"), ("crown pendant light", "Pendant"),
    ("pendant light", "Pendant"), ("loop pendant", "Pendant"),
    ("table light", "Light"), ("wall light", "Light"), ("wall uplight", "Light"),
    ("cluster light", "Light"), ("globe light", "Light"), ("table lamp", "Table Lamp"),
    ("coffee table", "Coffee Table"), ("dining table", "Dining Table"),
    ("bedside table", "Bedside Table"), ("dressing table", "Dressing Table"),
    ("side table", "Side Table"), ("lamp table", "Side Table"),
    ("chest of drawers", "Chest of Drawers"), ("drinks cabinet", "Cabinet"),
    ("counter stool", "Stool"), ("bench with pad", "Bench"),
    ("cheval mirror", "Mirror"), ("tall mirror", "Mirror"),
    ("dining chair", "Dining Chair"), ("blanket box", "Storage"),
    ("sofa", "Sofa"), ("armchair", "Armchair"), ("footstool", "Footstool"),
    ("chaise", "Chaise"), ("bed", "Bed"), ("sideboard", "Sideboard"),
    ("dresser", "Dresser"), ("armoire", "Armoire"), ("cabinet", "Cabinet"),
    ("console", "Console"), ("bench", "Bench"), ("stool", "Stool"),
    ("shelving", "Shelving"), ("vitrine", "Vitrine"), ("daybed", "Daybed"),
    ("mirror", "Mirror"), ("desk", "Desk"), ("chair", "Chair"), ("rug", "Rug"),
    ("sidechair", "Chair"), ("swivel", "Chair"), ("tray", "Tray"), ("mill", "Mill"),
    ("sconce", "Sconce"), ("pouf", "Ottoman"), ("credenza", "Credenza"), ("box", "Box"),
    ("bowl", "Bowl"), ("vase", "Vase"), ("plate", "Plate"), ("boxes", "Box"),
    ("screen", "Screen"), ("cup", "Cup"), ("glass", "Glass"), ("vessel", "Vessel"),
    ("coat rack", "Coat Stand"), ("coat stand", "Coat Stand"), ("winerack", "Wine Rack"),
    ("bookend", "Bookend"), ("candle holder", "Candle Holder"), ("candleholder", "Candle Holder"),
    ("ottoman", "Ottoman"), ("seater", "Sofa"), ("shelf", "Shelving"), ("urn", "Urn"),
    ("coupe", "Coupe"), ("grinder", "Mill"), ("bottle opener", "Bottle Opener"),
    ("runner", "Rug"), ("mat", "Rug"), ("hook", "Coat Hook"), ("flush mount", "Flush Mount"),
    ("cushion", "Cushion"), ("day bed", "Daybed"), ("bergere", "Armchair"),
    ("bookshelves", "Shelving"), ("bookshelf", "Shelving"), ("shelves", "Shelving"),
    ("table", "Table"), ("chandelier", "Chandelier"), ("pendant", "Pendant"),
    ("uplight", "Light"), ("lamp", "Lamp"), ("light", "Light"),
)

# Brands piloting the English keyword fallback above - deliberately an
# allowlist, not applied to every blank/junk category across the board,
# since a keyword scan like this has bitten this project before with
# false positives on other brands (Minimalux, Ingo Maurer - see project
# memory). Widen only after checking a brand's own real product names
# against ENGLISH_OBJECT_TYPE_KEYWORDS the same way Pinch's were.
CATEGORY_KEYWORD_FALLBACK_BRANDS = {
    "Pinch", "Mater", "H. Bigeleisen", "Jon Goulder", "Oven Editions", "Mercoeur Editions",
    "Sizar Alexis", "Mass Productions", "Kin and Co", "Buro Berger", "Grain",
    "New Works DK", "Workstead", "Rubn", "Maruni", "AY Illuminate", "Ghidini 1961",
    "GATOMIKIO",
}


# A handful of real products give the keyword/name-based inference
# above nothing to work with at all - no object-type word anywhere in
# the name. Confirmed by checking each one against the brand's own
# site rather than guessed: Pinch's "Nim Copper"/"Nim Dune" are both
# cast Jesmonite coffee tables (per pinchdesign.com's own product page,
# "Copper"/"Dune" are just the two finish names), and "Mercier press"
# is a press - an older cabinetmaking term for a cupboard, confirmed by
# its own product description ("full timber exterior... central
# cupboard"). Applied in run()'s save loop, not in an extractor, so it
# reaches every brand/extractor the same way and survives a re-scrape
# instead of reverting to blank every run - add to this as more
# uncapturable names are found, per-product, only after checking the
# real thing.
MANUAL_CATEGORY_OVERRIDES = {
    ("Pinch", "Nim Copper"): "Coffee Table",
    ("Pinch", "Nim Dune"): "Coffee Table",
    ("Pinch", "Mercier press"): "Cabinet",
    # A solid cube, no object-type word in the name or anywhere in
    # Mater's own product data - confirmed by checking its real product
    # photo (materdesign.com): a simple stool-height block sized/shaped
    # to work as either, so tagged as both rather than guessing one.
    ("Mater", "Mater Cube | Wood Waste Grey"): "Stool, Side Table",
    ("Mater", "Mater Cube | Coffee Waste Black"): "Stool, Side Table",
    ("Mater", "Mater Cube | Coffee Waste Light"): "Stool, Side Table",
    # The rest of this dict (added 2026-09-21, part of the broader
    # "every brand should have real category data" pass) are all
    # single-straggler brands - extractors that work correctly for
    # every other product, with one or two names that give the
    # keyword-based inference nothing to go on. Each checked against
    # the brand's own real site before being hardcoded here, same
    # standard as the Pinch/Mater entries above.
    ("A. Petersen", "Bookkeeper"): "Shelving",  # apetersen.dk: "ideal for books... organizing your vinyl collection"
    ("Anna Löwenhielm Ceramics", "Ljusstake"): "Candle Holder",  # Swedish for "candle holder"; URL confirms "carol-candle-holder"
    ("De La Espada", "SIDEKICKS COFFEE TABLE WITH TERRAZZO TOP"): "Coffee Table",
    ("De La Espada", "SOLO STORAGE TRAY"): "Tray",
    ("Esther Knopfler", "Strata bench"): "Bench",
    ("Esther Knopfler", "Strata console"): "Console",
    ("Esther Knopfler", "Strata stool"): "Stool",
    ("Esther Knopfler", "Strata coffee table"): "Coffee Table",
    ("Jonas Lindholm", "Stapelbar kopp av Jonas Lindholm"): "Cup",  # Swedish "stackable cup"
    ("Joy Objects", "TUBBY TUMBLER"): "Tumbler",
    ("Joy Objects", "Åsa Jungnelius for JOY OBJECTS"): "Tumbler",  # same listing, designer name scraped as product_name
    ("Louise Roe", "PISU 15 PITCHER"): "Pitcher",
    ("Louise Roe", "PISU 14 PITCHER"): "Pitcher",
    ("Luke Hope", "Craters plate & bowl set in sycamore"): "Plate, Bowl",
    ("Northern", "Oslo Wood Anniversary Edition"): "Lamp",  # northern.no: "en av Northerns mest gjenkjennelige lamper"
    ("Northern", "Hifive tambur og glasskapssett 200"): "Sideboard",
    ("Northern", "Hifive Glass-vitrineskap 200"): "Sideboard",
    ("Northern", "Tradition gulvlampe"): "Floor Lamp",  # URL confirms "tradition-floor-lamp"
    ("Raawii", "George Sowden"): "Table",  # product_name is the designer's name; real product is the "Thing Table"
    ("Silcohaus", "Arno Tall"): "Floor Lamp",  # silcohaus.com: "Arno Tall is more than a floor lamp"
    ("Silcohaus", "Arno Short"): "Lamp",  # companion piece to Arno Tall, own tags confirm "Category: Lighting"
    ("Silcohaus", "Luno Side"): "Side Table",  # URL confirms "luna-side-table"
    ("Wendelbo", "Edge V1 Sofa"): "Sofa",
    ("Birgit Severin", "Alteration"): "Lamp",  # "counter-weight lamp allowing to adjust the light temperature"
    ("Birgit Severin", "Ashes"): "Vase",  # "rubber vases embracing the transience of life"
    ("Birgit Severin", "Heimat"): "Lamp",  # "burned in fire - lampshade exploring memories"
    ("Birgit Severin", "Vanitas"): "Vase",  # "rubber vases exploring the beauty of decay"
    # "Design Impressionism" and "Kirei" (a jewelry-cleaning object) left
    # uncategorized on purpose - checked both live, neither maps to a
    # real furniture/lighting/ceramics/object type.
    ("Utilitario Mexicano", "GANCHO"): "Coat Hook",  # "GANCHO / PERCHERO PELTRE" - a pewter wall coat hook
    ("Utilitario Mexicano", "LLAVERO HOTEL LAS BRISAS"): "Keychain",  # same product line as its other real, categorized keychains
    # Dutch names giving the English keyword list nothing to go on -
    # checked against pietheineek.nl's own product photos/descriptions.
    ("Piet Hein Eek", "Oude buizen zithoek"): "Sofa",  # "old tubes seating corner" - a tube-frame sectional
    ("Piet Hein Eek", "Enorme balken salonblok"): "Coffee Table",  # checked its real photo: a low block with drawers
    ("Piet Hein Eek", "Oudetapijtentapijttegeltapijt"): "Rug",  # "old carpets carpet tile carpet"
    ("Piet Hein Eek", "Keuken Mavaleix"): "Kitchen",
    ("Piet Hein Eek", "Tray aluminium medium"): "Tray",
    ("Piet Hein Eek", "Canteen bench in scrapwood"): "Bench",
    ("Piet Hein Eek", "Kröller-Müller chair"): "Chair",
    ("Piet Hein Eek", "Keuken voor particulier"): "Kitchen",
    # Will Choui's own site groups several distinct pieces (a chair, a
    # lamp, a table...) under one named "collection", and its own
    # /collections/collectibles gallery already treats each collection
    # as a single "piece" (see extract_will_choui's docstring) - so a
    # single-category tag would be inaccurate for a design that's both
    # e.g. a console and a lamp. Tagged with every real product type in
    # the collection instead, checked live against willchoui.com's own
    # per-collection product breakdown.
    ("Will Choui", "per.for.(H)ated"): "Sofa, Armchair, Coffee Table",
    ("Will Choui", "1980"): "Pendant",
    ("Will Choui", "Alu Side Table"): "Side Table",
    ("Will Choui", "WCL"): "Chair",
    ("Will Choui", "Squarehead Mirror"): "Mirror",
    ("Will Choui", "1979"): "Side Table, Pendant, Mirror, Lamp",
    ("Will Choui", "Solimar"): "Console, Table, Stool",
    ("Will Choui", "Drum"): "Console, Lamp, Coffee Table",
    # Polish names, translated and checked against the product photo/
    # page - the English keyword list has nothing to match here.
    ("Łukasz Korol", "Kredens z jesionu"): "Sideboard",  # "ash-wood sideboard/cupboard"
    ("Łukasz Korol", "Biurko z jawora"): "Desk",  # "sycamore desk"
    ("Łukasz Korol", "Stolik kawowy z jawora"): "Coffee Table",  # "sycamore coffee table"
    ("Łukasz Korol", "Ławka z jawora"): "Bench",  # "sycamore bench"
    ("Łukasz Korol", "Komoda z czereśni"): "Chest of Drawers",  # "cherry-wood chest of drawers"
    ("Łukasz Korol", "Szafka nocna z czereśni"): "Bedside Table",  # "cherry-wood nightstand"
    ("Łukasz Korol", "Stolik kawowy z orzecha"): "Coffee Table",  # "walnut coffee table"
    ("Łukasz Korol", "Stolik z orzecha"): "Side Table",  # "walnut small table"
    ("Łukasz Korol", "Kredens z gruszy"): "Sideboard",  # "pear-wood sideboard/cupboard"
    ("Another Country", "Atlas Works Tall Wine Glass (Set )"): "Glass",
    ("Another Country", "Winnow Rug by Armadillo"): "Rug",
    # Shibui's entire catalog is named with one-word evocative product
    # names (crash, float, spice...) - none give the English keyword
    # list anything to match, checked one by one against shibui.ch's
    # own real product descriptions.
    ("Shibui", "Crash"): "Crusher",  # "palm sized crusher/cracker... mortar and pestle... nutcracker"
    ("Shibui", "float"): "Shelving",  # "book shelves that appear to float"
    ("Shibui", "spice"): "Salt and Pepper Set",
    ("Shibui", "linelight"): "Desk Lamp",  # "led task light for home or office use"
    ("Shibui", "pinch"): "Container",  # "spice containers with a lid"
    ("Shibui", "Plume"): "Desk Organiser",
    ("Shibui", "Pino"): "Crusher",  # same description as Crash, different finish
    ("Shibui", "bOx"): "Box",  # "modular jewel/watch box"
    ("Shibui", "iceCube"): "Wine Cooler, Bowl",  # "wine and champagne cooler with a secondary use as a fruit bowl"
    ("Shibui", "pirouette"): "Toy, Ornament",  # "double function Christmas decorations... great spin tops"
    ("Shibui", "Apeiro (set of 2)"): "Coat Hook",  # "coat hanger in the shape of infinity"
    ("Shibui", "O bottle opener"): "Bottle Opener",
    ("Jon Goulder", "Innate - Coffee Table + Side Table"): "Coffee Table, Side Table",
    ("Jon Goulder", "Catalogue - Terrain"): "Table",  # jongoulder.com: a real 3m collaborative table piece, not a downloadable catalogue despite the title
    ("Mercoeur Editions", "Komorebi Steles"): "Stele",  # a real, specific design term (a standing sculptural panel) - kept as its own word rather than forced into a broader bucket
    ("Sizar Alexis", "Lahmu Low Console/Bench"): "Console, Bench",  # name explicitly names both functions
    # B-Line Italia's product names are all evocative (Boby, Ring,
    # Spinny...), giving the English keyword list nothing to match -
    # b-line.it's own site has 3 real object-type category pages
    # (/category/complementi-en/, sedute-en, tavoli-en - a "timeless"
    # 4th category is a collection line, not an object type, confirmed
    # by cross-checking its members against the other three), which
    # covered 14 of 20; the other 6 were checked against their own
    # real product photos.
    ("B-Line Italia", "Boby"): "Accessories",
    ("B-Line Italia", "Ring"): "Accessories",
    ("B-Line Italia", "Spinny"): "Accessories",
    ("B-Line Italia", "Bix"): "Seating",
    ("B-Line Italia", "Boomerang"): "Seating",
    ("B-Line Italia", "Crossed"): "Seating",
    ("B-Line Italia", "Esa"): "Seating",
    ("B-Line Italia", "Multichair"): "Seating",
    ("B-Line Italia", "Supercomfort"): "Seating",
    ("B-Line Italia", "Toro"): "Seating",
    ("B-Line Italia", "4/4"): "Table",
    ("B-Line Italia", "AD.DA"): "Table",
    ("B-Line Italia", "Fonda"): "Table",
    ("B-Line Italia", "Tran Tran"): "Table",
    ("B-Line Italia", "Velasca"): "Mirror",  # checked its real product photo
    ("B-Line Italia", "Fill"): "Desk Organiser",  # checked its real product photo
    ("B-Line Italia", "Ping Pong"): "Plate",  # checked its real product photo
    ("B-Line Italia", "Bob"): "Desk Organiser",  # checked its real product photo
    ("B-Line Italia", "Aki Jr"): "Container",  # checked its real product photo - a multi-slot holder, no more specific real use confirmed
    ("B-Line Italia", "Aki"): "Container",
    # Evocative Mass Productions names, checked against
    # massproductions.se's own real product descriptions.
    ("Mass Productions", "Universal Door Wedge"): "Door Wedge",
    ("Mass Productions", "Woodi"): "Mill",  # "Woodi - Salt & Pepper Grinder"
    ("Mass Productions", "Trippy"): "Vase",  # "a large-scale vase, produced with a combination of glassblowing techniques"
    ("Mass Productions", "Harry"): "Stool",  # "The Harry stool draws its visual language from..."
    ("Mass Productions", "Hercule"): "Coat Hook",  # URL confirms "hercule-wall-hook"
    ("Mass Productions", "4PM"): "Chaise",  # "the design language of the chaise..."
    ("Mass Productions", "Patch Config. A"): "Sofa",  # a configuration of the modular "Patch Sofa System"
    ("Mass Productions", "Patch Config. B"): "Sofa",
    ("Mass Productions", "Patch Config. C"): "Sofa",
    ("Mass Productions", "Patch Config. D"): "Sofa",
    # Editions Midi names every product in Occitan/Provençal (its own
    # regional-heritage identity - "Midi" is the South of France), so
    # none give the English keyword list anything to match. Checked
    # each of the 23 against editions-midi.com's own real English
    # product descriptions (2026-09-21), which usually translate the
    # name outright (e.g. "Cadiero, means chair in Provençal").
    ("Editions Midi", "Ageinouiadou"): "Chair",  # "inspired by the wet nurse's chair... could also serve as Prie-Dieu"
    ("Editions Midi", "Alòngui pèr dous"): "Chaise",  # "this 2-seater deckchair"
    ("Editions Midi", "Alòngui pèr un"): "Chaise",  # 1-seater version of the same deckchair
    ("Editions Midi", "Banc"): "Bench",
    ("Editions Midi", "Bancoun"): "Bench",  # "Bancoun 2-seater" per Banc's own description
    ("Editions Midi", "Bancounet"): "Bench",  # "Bancounet 1-seater" per Banc's own description
    ("Editions Midi", "Bergierio"): "Armchair",  # "Bergerio, shepherdess in Provencal" - a bergère-style low armchair
    ("Editions Midi", "Bugadiero"): "Bowl",  # "the enamelled bowl resting on a terracotta base"
    ("Editions Midi", "Burèu"): "Desk",  # "The Burèu desk..."
    ("Editions Midi", "Cadieras"): "Chair",  # "The Cadieras chair is a reinterpretation of the Provence chair"
    ("Editions Midi", "Cadiero"): "Chair",  # "Cadiero, means chair in Provençal"
    ("Editions Midi", "Chaminèio"): "Armchair",  # "nicknamed the fireplace armchair"
    ("Editions Midi", "Counsciènci"): "Vessel",  # a slender ceramic olive-oil storage/transport vessel
    ("Editions Midi", "Fautuei"): "Armchair",  # "Fautuei, means armchair in Provençal"
    ("Editions Midi", "Gargouleto"): "Pitcher",  # "this jug is very emblematic of the South of France... this water jug"
    ("Editions Midi", "Maloun"): "Tile",  # "these enameled terracotta tiles"
    ("Editions Midi", "Penequet"): "Sofa",  # "a generously sized sofa" - upholstered version of Radassié
    ("Editions Midi", "Radassié"): "Sofa",  # the base (non-upholstered) version of Penequet
    ("Editions Midi", "Ramo"): "Side Table, Stool",  # "used as a side table or a stool"
    ("Editions Midi", "Roucaio"): "Coffee Table",  # "the table, Roucaio... revisits the concrete faux bois"
    ("Editions Midi", "Roujo"): "Coffee Table",  # "for this coffee table..."
    ("Editions Midi", "Tabouret"): "Stool",  # "each MIDI stool is made of..."
    ("Editions Midi", "Taulo"): "Dining Table",  # "Taulo means table in Provençal... large farm tables"
    # Källemo names every product with a standalone name/word (no
    # object-type word), giving the English keyword list nothing to
    # match. Checked each of the 26 against kallemo.se's own real
    # product descriptions, which name the object type outright
    # ("The Aluminium armchair was designed in 1986...").
    ("Källemo", "ALUMINIUM"): "Armchair",
    ("Källemo", "BRUNO"): "Armchair",
    ("Källemo", "VILAN"): "Armchair",
    ("Källemo", "INGO"): "Armchair",
    ("Källemo", "AVEC"): "Armchair",
    ("Källemo", "AMBASSAD"): "Armchair",
    ("Källemo", "STAR"): "Armchair",
    ("Källemo", "GA-2"): "Armchair",
    ("Källemo", "CHESTER"): "Armchair",
    ("Källemo", "CHESTER SOFA"): "Sofa",
    ("Källemo", "BEATRIX ARMCHAIR"): "Armchair",
    ("Källemo", "BEATRIX SOFA"): "Sofa",
    ("Källemo", "SOFA BOTERO"): "Sofa",
    ("Källemo", "AL DENTE"): "Coat Hook",  # "the Al Dente wall hanger"
    ("Källemo", "BABE"): "Coat Stand",  # "the Babe clothes hanger" - checked its real photo, a floor-standing tripod stand
    ("Källemo", "NON bench"): "Bench",
    ("Källemo", "BRUNO footstool"): "Footstool",
    ("Källemo", "BJÖRKSKÅPET"): "Cabinet",  # "the Björkskåpet cabinet"
    ("Källemo", "GRACE"): "Armchair",
    ("Källemo", "LJUS FÄRG SVART KABEL"): "Light",  # "the illuminating object..."
    ("Källemo", "NATIONAL GEOGRAPHIC 25TH ANNIVERSARY"): "Cabinet",  # "the yellow cabinet National Geographic"
    ("Källemo", "NATIONALPALLEN"): "Stool",  # "pallen" = "the stool" in Swedish, confirmed by its own description
    ("Källemo", "PIMPIM"): "Chair",
    ("Källemo", "STAR PÄRLEMOR"): "Armchair",  # the same Star armchair's limited mother-of-pearl edition, per Star's own description
    ("Källemo", "WOWMOM"): "Shelving",  # a pure art piece with no stated function - checked its real photo, a tiered shelf-like tower structure
    ("Källemo", "ÄNTLIGEN ETT FULLGOTT ALTERNATIV"): "Light",  # "the illuminating object..."
    # Kin and Co's 4 non-obvious names, checked against
    # kinandcompany.com's own real product descriptions/photos.
    ("Kin and Co", "Ripple Series"): "Table",  # "a volumetric cylindrical column... gently holding a floating top"
    ("Kin and Co", "Veil Series"): "Mirror",  # "an evolution of the Drape Series, the Veil Mirrors..."
    ("Kin and Co", "Step Stair"): "Bench",  # "an ambiguous object to accommodate lounging, seating or display"
    ("Kin and Co", "Thin Tete-a-Tete"): "Bench",  # checked its real photo: a two-seat S-shaped bench, the classic tête-à-tête form
    ("Kin and Co", "Thin Check Double Chaise and Table Set"): "Chaise, Table",  # name explicitly names both
    ("Buro Berger", "The Crib Nativity Scene"): "Ornament",  # checked live: 14 decorative wooden figurines + stable, "an object to exhibit... during the Christmas season"
    # La Chambre d'Ami names its entire catalog in French, giving the
    # English keyword list nothing to match at all. Checked against
    # lachambredami.com's own real French product descriptions
    # (2026-09-21) - "abat-jour/suspension" is lampshade/pendant,
    # "lampe" is lamp, both un-matchable by an English-only keyword
    # list regardless of how many keywords it grows.
    ("La Chambre d'Ami", "1960 - Abat-jour / Suspension"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Azote"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Bob"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Boudoir"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Fleur"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Hélium"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Moderne"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Métro"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Oxygène"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Rivage"): "Pendant",
    ("La Chambre d'Ami", "Abat-jour / Suspension Tea-Time"): "Pendant",
    ("La Chambre d'Ami", "Base de Lampe Classique"): "Lamp",
    ("La Chambre d'Ami", "Bougeoir Pivoine"): "Candle Holder",  # "bougeoir" = candlestick
    ("La Chambre d'Ami", "Cache Douille / 1"): "Light",  # a decorative cord/socket cover accessory for an existing pendant
    ("La Chambre d'Ami", "Cache Douille / 2"): "Light",
    ("La Chambre d'Ami", "Cache Douille / 3"): "Light",
    ("La Chambre d'Ami", "Duos de Vases Totem"): "Vase",
    ("La Chambre d'Ami", "Grande base de Lampe"): "Lamp",
    ("La Chambre d'Ami", "Lampe 1960"): "Lamp",
    ("La Chambre d'Ami", "Lampe Azote"): "Lamp",
    ("La Chambre d'Ami", "Lampe Fleur"): "Lamp",
    ("La Chambre d'Ami", "Lampe Hélium"): "Lamp",
    ("La Chambre d'Ami", "Lampe IGLOO - Glacier"): "Lamp",
    ("La Chambre d'Ami", "Lampe IGLOO - Lavande"): "Lamp",
    ("La Chambre d'Ami", "Lampe IGLOO - Rose"): "Lamp",
    ("La Chambre d'Ami", "Lampe Limonade"): "Lamp",
    ("La Chambre d'Ami", "Lampe Moderne"): "Lamp",
    ("La Chambre d'Ami", "Lampe Oxygène"): "Lamp",
    ("La Chambre d'Ami", "Lampe PIVOINE - Lavande"): "Lamp",
    ("La Chambre d'Ami", "Lampe PIVOINE - Rose"): "Lamp",
    ("La Chambre d'Ami", "Lampe Rivage"): "Lamp",
    ("La Chambre d'Ami", "Lampe Tea-Time"): "Lamp",
    ("La Chambre d'Ami", "Le Porte-Photo"): "Photo Holder",
    ("La Chambre d'Ami", "MÉDUSE - Blanche"): "Lamp",  # "cette lampe méduse blanche" - "this white jellyfish lamp"
    ("La Chambre d'Ami", "MÉDUSE - Glacier"): "Lamp",
    ("La Chambre d'Ami", "MÉDUSE - Lavande"): "Lamp",
    ("La Chambre d'Ami", "MÉDUSE - Menthe"): "Lamp",
    ("La Chambre d'Ami", "MÉDUSE - Mimosa"): "Lamp",
    ("La Chambre d'Ami", "MÉDUSE - Rose"): "Lamp",
    ("La Chambre d'Ami", "MÉDUSE - noire"): "Lamp",
    ("La Chambre d'Ami", "Organisateur de Bureau - Grand"): "Desk Organiser",
    ("La Chambre d'Ami", "Organisateur de Bureau - Petit"): "Desk Organiser",
    ("La Chambre d'Ami", "PROTOTYPE - 013"): "Lamp",  # "cette lampe fait partie d'une recherche..."
    ("La Chambre d'Ami", "PROTOTYPE - 073"): "Lamp",  # same prototype-lamp series as PROTOTYPE - 013
    # "PROTOTYPE - FLOWER 1" removed 2026-09-21 - confirmed retired
    # (see LA_CHAMBRE_DAMI_SKIP_SLUGS), not a category gap.
    ("La Chambre d'Ami", "Pique-Fleur Séchées"): "Flower Frog",  # "11 trous pour placer vos fleurs séchées"
    ("La Chambre d'Ami", "Porte Savon Classique"): "Soap Dish",
    ("La Chambre d'Ami", "Porte Savon Vertical"): "Soap Dish",
    ("La Chambre d'Ami", "Soliflores Figures"): "Vase",  # "soliflore" = a single-stem bud vase
    ("La Chambre d'Ami", "Vide-poche"): "Catchall",  # "déposer vos petites affaires dans l'entrée" - an entryway tray
    ("La Chambre d'Ami", "le-grand-vase-totem"): "Vase",
    # New Works DK's "Coda Configuration N" names give no furniture word
    # at all, but each one's own URL slug says "coda-modular-sofa-
    # configuration-N" - confirmed real. "Shore Dining..." modules are
    # confirmed live: "The Shore Modular Dining Sofa brings a thoughtful
    # approach to banquette seating" - a curved modular dining bench/
    # sofa system, not a table despite "Dining" in the name.
    ("New Works DK", "Coda Configuration 1"): "Sofa",
    ("New Works DK", "Coda Configuration 2"): "Sofa",
    ("New Works DK", "Coda Configuration 3"): "Sofa",
    ("New Works DK", "Coda Configuration 4"): "Sofa",
    ("New Works DK", "Coda Configuration 5"): "Sofa",
    ("New Works DK", "Coda Configuration 6"): "Sofa",
    ("New Works DK", "Coda Configuration 7"): "Sofa",
    ("New Works DK", "Coda Configuration 8"): "Sofa",
    ("New Works DK", "Shore Dining Curved Corner Outward, Plinth, Module 30"): "Sofa",
    ("New Works DK", "Shore Dining Curved Corner Inward, Plinth, Module 31"): "Sofa",
    ("New Works DK", "Shore Dining Curved End Left, Plinth, Module 41"): "Sofa",
    ("New Works DK", "Shore Dining Curved Center, Plinth, Module 40"): "Sofa",
    ("New Works DK", "Shore Dining Curved End Right, Plinth, Module 42"): "Sofa",
    # Workstead's abstract product-line names (Brick, Park, Tinsel,
    # Orbit Solo/Satellite, Signal Solo) give no lighting word at all,
    # but every one is confirmed a wall/ceiling fixture on its own real
    # workstead.com product page (e.g. Park I: "usable as a sconce or
    # flush mount"; Tinsel: "can be used as both a wall sconce and
    # flush mount").
    ("Workstead", "Brick I"): "Sconce",
    ("Workstead", "Brick III"): "Sconce",
    ("Workstead", "Park I"): "Sconce",
    ("Workstead", "Park II"): "Sconce",
    ("Workstead", "Park III"): "Sconce",
    ("Workstead", "Park IV"): "Sconce",
    ("Workstead", "Tinsel"): "Sconce",
    ("Workstead", "Orbit Solo"): "Sconce",
    ("Workstead", "Orbit Satellite"): "Sconce",
    ("Workstead", "Signal Solo"): "Sconce",
    ("Rubn", "The Palazzo"): "Light",  # "fully dimmable... light that shapes the mood" - no stated mount type
    ("Rubn", "Ceiling Cup"): "Light",  # a mounting/canopy accessory for pendant lights, not a standalone fixture
    ("Rubn", "Lord X"): "Chandelier",  # "adjustable rods... change the lamp's appearance", sibling of Lord 3 Chandelier
    ("Rubn", "Lord Diva"): "Chandelier",  # referenced by Lord Ballroom's own description as a sibling design
    ("Rubn", "Lord Ballroom"): "Chandelier",  # "12 glass globes... suspended from a solid metal fixture"
    ("Rubn", "Lord Asymmetric"): "Chandelier",  # "mounts directly to the ceiling... six glass globes"
    # GATOMIKIO's KARMI collection is named with a single, unrelated
    # kanji per item and no per-product description - checked its real
    # collection photo instead (gatomikio-store.com/collections/karmi):
    # most are tall turned-wood vase/bottle forms (all priced ¥22,000),
    # with 3 shorter, wider forms priced lower (¥13,200) - "重" is
    # confirmed a tiered box shape from TSUMUGI's own "丸重" (round
    # tiered box), so its KARMI namesake gets the same tag; the other
    # two lower-priced ones read as shallow bowl forms in the photo.
    ("GATOMIKIO", "KARMI 元"): "Vase",
    ("GATOMIKIO", "KARMI 樽"): "Vase",
    ("GATOMIKIO", "KARMI 実"): "Vase",
    ("GATOMIKIO", "KARMI 帽"): "Vase",
    ("GATOMIKIO", "KARMI 瓶"): "Vase",
    ("GATOMIKIO", "KARMI 塔"): "Vase",
    ("GATOMIKIO", "KARMI 頸"): "Vase",
    ("GATOMIKIO", "KARMI 菱"): "Vase",
    ("GATOMIKIO", "KARMI 俵"): "Vase",
    ("GATOMIKIO", "KARMI 徳"): "Vase",
    ("GATOMIKIO", "KARMI 釜"): "Vase",
    ("GATOMIKIO", "KARMI 礎"): "Bowl",
    ("GATOMIKIO", "KARMI 座"): "Bowl",
    ("GATOMIKIO", "KARMI 重"): "Box",
    # AEKA's "Object Round"/"Object Slim" (no Bowl/Vase/Plate suffix,
    # unlike its siblings) are the two round, bulbous vase-shaped
    # pieces shown on its own real collection photo, distinct from the
    # flat plate-shaped pieces also in that collection.
    ("GATOMIKIO", "AEKA Object  Round（180×90）"): "Vase",
    ("GATOMIKIO", "AEKA Object  Round（210×110）"): "Vase",
    ("GATOMIKIO", "AEKA Object Round（240×120）"): "Vase",
    ("GATOMIKIO", "AEKA Object Slim（150×50）"): "Vase",
    ("GATOMIKIO", "AEKA Object Slim（210×70）"): "Vase",
    # TOHKA's other real items are all traditional Japanese sake
    # vessels (杯/片口/猪口) - Champagne/Cocktail/Wine are the same
    # collection's Western-style drinkware equivalents.
    ("GATOMIKIO", "TOHKA Champagne"): "Glass",
    ("GATOMIKIO", "TOHKA Cocktail"): "Glass",
    ("GATOMIKIO", "TOHKA WINE"): "Glass",
    # KOTON's own real description: "a simple wooden container...
    # 椀・鉢・皿としてもお使い頂けます" ("can also be used as a bowl/
    # hachi/plate") - U/V/Y are just its shape variants.
    ("GATOMIKIO", "KOTON U Type"): "Bowl",
    ("GATOMIKIO", "KOTON V Type"): "Bowl",
    ("GATOMIKIO", "KOTON Y Type"): "Bowl",
    # MATEVARI's own real description: "MATEVARI is named as abbreviated
    # from 'Material Variation.' Choose any bowls you like from five
    # kinds of wood" - the 5 names are just tree species (zelkova, oak,
    # beech, maple, cherry), not object types.
    ("GATOMIKIO", "MATEVARI 欅"): "Bowl",
    ("GATOMIKIO", "MATEVARI 楢"): "Bowl",
    ("GATOMIKIO", "MATEVARI 橅"): "Bowl",
    ("GATOMIKIO", "MATEVARI 楓"): "Bowl",
    ("GATOMIKIO", "MATEVARI 桜"): "Bowl",
    # Established & Sons: 32 confirmed via the site's own real category
    # pages (/collection/categories/{name}), 7 more checked against
    # their own real "Description:" field since they're current
    # products the category pages don't happen to list (2026-09-21).
    ("Established & Sons", "Font Clock"): "Accessories",
    ("Established & Sons", "Wrongwoods Tray"): "Accessories",
    ("Established & Sons", "Drift"): "Bench",  # "Description: Bench"
    ("Established & Sons", "Drift Concrete"): "Bench",  # "Description: Bench"
    ("Established & Sons", "Drift-In Drift-Out"): "Bench",  # "Description: Flexible seating segments"
    ("Established & Sons", "Nekton"): "Bench",  # "Description: Flexible seating segments"
    ("Established & Sons", "Gridwork"): "Flooring",
    ("Established & Sons", "Wall To Wall"): "Flooring",
    ("Established & Sons", "Grid"): "Furniture Systems",
    ("Established & Sons", "Island"): "Furniture Systems",
    ("Established & Sons", "Aura Light"): "Lighting",
    ("Established & Sons", "Cho Light"): "Lighting",
    ("Established & Sons", "Filigrana Light"): "Lighting",
    ("Established & Sons", "Filigrana Light, Table"): "Lighting",
    ("Established & Sons", "Filigrana Light, Wall / Ceiling"): "Lighting",
    ("Established & Sons", "Gelato"): "Lighting",
    ("Established & Sons", "Medusa"): "Lighting",
    ("Established & Sons", "The Original Maya"): "Lighting",
    ("Established & Sons", "Tiki"): "Lighting",
    ("Established & Sons", "Torch Light"): "Lighting",
    ("Established & Sons", "Butt"): "Seating",
    ("Established & Sons", "Heidi"): "Seating",
    ("Established & Sons", "Layup"): "Seating",
    ("Established & Sons", "Mauro Chair"): "Seating",
    ("Established & Sons", "Crate Series"): "Storage",
    ("Established & Sons", "Plates Shelving"): "Storage",
    ("Established & Sons", "Side Stack"): "Storage",
    ("Established & Sons", "Stack"): "Storage",
    ("Established & Sons", "Wrongwoods"): "Storage",
    ("Established & Sons", "Aqua Table"): "Table",  # "Description: Display or dining table"
    ("Established & Sons", "Surface Table"): "Table",  # "Description: Meeting, display or dining table"
    ("Established & Sons", "Udukuri"): "Table",  # "Description: Meeting, display or dining table"
    ("Established & Sons", "Beam Table"): "Table",
    ("Established & Sons", "Bloc"): "Table",
    ("Established & Sons", "Fez"): "Table",
    ("Established & Sons", "Crate Daybed"): "Upholstery",
    ("Established & Sons", "Lucio"): "Upholstery",
    ("Established & Sons", "Mollo"): "Upholstery",
    ("Established & Sons", "Quilt"): "Upholstery",
}


def _infer_category_from_english_keywords(product_name):
    text = product_name.lower()
    for phrase, category in ENGLISH_OBJECT_TYPE_KEYWORDS:
        if phrase in ("light", "uplight") and "waste light" in text:
            # Mater's own recycled-material finish name ("Coffee Waste
            # Light"/"Wood Waste Light", alongside "...Dark"/"...Black")
            # collides with the generic "light" keyword - confirmed
            # live 2026-09-21: several chair/stool variants finished in
            # "Coffee Waste Light" were wrongly tagged as lighting.
            # "waste light" never means an actual light fixture
            # anywhere in this catalog.
            continue
        # Optional trailing "s" - confirmed live 2026-09-21: "Ondine
        # Set of 3 boxes" (Mercoeur Editions) didn't match "box" at all
        # without this, since a bare \b-anchored pattern requires an
        # exact word match. Same "s?" approach as query_engine.py's own
        # _category_matches. Irregular plurals (box -> boxes, not
        # "boxs") get their own explicit keyword entry instead of a
        # more complex pluralizer.
        if re.search(rf"\b{re.escape(phrase)}s?\b", text):
            return category
    return None


# Rubn is a pure lighting brand whose product names encode mount type
# as a bare word (Floor/Table/Wall/Ceiling/Desk) rather than saying
# "lamp" at all - confirmed live 2026-09-21 by checking several
# ambiguous-looking names against their own real product descriptions
# (e.g. "Chairman Table" is a table lamp with "a soft, warm glow, "not
# a piece of furniture despite the name). Kept brand-scoped rather
# than added to the shared English keyword list - "table"/"desk"/
# "wall"/"floor"/"ceiling" as bare words would badly misclassify real
# furniture at every other brand (a real desk is not a desk lamp).
RUBN_MOUNT_TYPE_KEYWORDS = (
    ("floor with table", "Floor Lamp, Table Lamp"),
    ("tripod table", "Table Lamp"),
    ("table spot", "Table Lamp"),
    ("spot with cup", "Light"),
    ("spot with plate", "Light"),
    ("suspension", "Pendant"),
    ("candle", "Candle Holder"),
    ("floor", "Floor Lamp"),
    ("wall", "Wall Lamp"),
    ("ceiling", "Ceiling Lamp"),
    ("desk", "Desk Lamp"),
    ("table", "Table Lamp"),
)


def _infer_rubn_category(product_name):
    text = product_name.lower()
    for phrase, category in RUBN_MOUNT_TYPE_KEYWORDS:
        if re.search(rf"\b{re.escape(phrase)}\b", text):
            return category
    return None


# GATOMIKIO names many products in Japanese - kanji/katakana script has
# no spaces, so the shared keyword matcher's \b-anchored regex (built
# for English) never matches a CJK term embedded in a longer string
# (confirmed live 2026-09-21: \b杯\b does NOT match "酒杯", since
# Python's word-boundary logic treats consecutive CJK characters as one
# continuous word with no internal boundary) - checked via plain
# substring search instead, safe here since these are specific,
# multi-character Japanese ceramics/tea-ware terms, not standalone
# words that could collide with something unrelated.
GATOMIKIO_JAPANESE_KEYWORDS = (
    ("高台盛器", "Bowl"), ("一輪挿し", "Vase"), ("金輪寺", "Tea Caddy"), ("中次", "Tea Caddy"),
    ("中棗", "Tea Caddy"), ("平棗", "Tea Caddy"), ("茶筒", "Tea Caddy"), ("吹雪", "Tea Caddy"),
    ("丸重", "Box"), ("chabako", "Box"), ("片口", "Pitcher"), ("猪口", "Cup"), ("湯呑", "Cup"),
    ("杯", "Cup"), ("椀", "Bowl"), ("鉢", "Bowl"), ("ボウル", "Bowl"), ("皿", "Plate"),
    ("プレート", "Plate"), ("カップ", "Cup"),
)


def _infer_gatomikio_category(product_name):
    for phrase, category in GATOMIKIO_JAPANESE_KEYWORDS:
        if phrase in product_name:
            return category
    return None


def _infer_category_from_name(product_name, current_category, brand_name=None):
    if current_category.strip().lower() not in UNHELPFUL_CATEGORIES:
        return current_category
    first_word = product_name.strip().split(" ")[0].lower().rstrip(",.")
    italian = ITALIAN_OBJECT_TYPES.get(first_word)
    if italian:
        return italian
    if brand_name == "Rubn":
        rubn_match = _infer_rubn_category(product_name)
        if rubn_match:
            return rubn_match
    if brand_name == "GATOMIKIO":
        gatomikio_match = _infer_gatomikio_category(product_name)
        if gatomikio_match:
            return gatomikio_match
    if brand_name in CATEGORY_KEYWORD_FALLBACK_BRANDS:
        keyword_match = _infer_category_from_english_keywords(product_name)
        if keyword_match:
            return keyword_match
    return current_category


def _looks_like_a_class_listing(title):
    """
    Some brands sell studio classes/workshops through the same Shopify
    catalog as their real ceramic/design objects, with no structural way
    to tell them apart (confirmed on Anna Löwenhielm Ceramics: "Ljusstake"
    - a real candlestick - sits alongside "Keramikstudio kväll, alla
    tekniker, egna projekt, tisdagar" and three other class bookings,
    none of which have a distinguishing product_type, tag, price range,
    or image count - only the title reveals what they are). A class
    listing isn't a design object Formground exists to surface, so these
    are excluded. Keyed on Swedish class/session vocabulary since that's
    the only real signal available for this brand; harmless no-op for
    every other (English-titled) Shopify brand currently in scope.
    """
    keywords = (
        "kurs", "kväll", "helg", "dagar",  # course, evening, weekend, "-days" (weekday plurals)
    )
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords)


def _looks_like_a_maintenance_item(title):
    """
    Some brands list assembly/cleaning kits and other upkeep accessories
    in the same catalog as their real design objects (confirmed on Pulkra:
    "Pulkra assembly kit" and "Pulkra cleaning kit"/"Kit di pulizia
    Pulkra" sit alongside real furniture, tagged "Accessories"/"Accessori"
    - a category too broad to blanket-exclude generically since other
    brands have genuine design accessories under that same word). Gift
    cards are the same shape (confirmed on Minimalux and Raawii: each
    sells one alongside real products, with no real category value of
    its own, showing up as an unfixable blank rather than a
    misclassified one). These aren't design objects Formground exists
    to surface, so they're excluded by name instead - harmless no-op
    for any brand that doesn't happen to sell one.
    """
    keywords = (
        "assembly kit", "cleaning kit", "kit di pulizia", "gift card",
        # Utilitario Mexicano also sells polarized sunglasses through
        # this same catalog (confirmed live: "Lentes Filtro
        # Polarizador") - not a home design object either, and its own
        # tags ("accesorio"/"accesorios") are too broad a signal to
        # exclude generically without also excluding real design
        # accessories like its coat hooks.
        "filtro polarizador",
        # Another Country runs a charity checkout item ("Heal
        # Rewilding Donation") through the same WooCommerce catalog as
        # its real products, with a real image - unlike its other junk
        # listings ("test 3", "Product", "AC Catalogue"), which already
        # have no image and are invisible to search regardless.
        "donation",
        # Mass Productions sells "4PM Self Build" for 0 SEK - free
        # downloadable DIY instructions for building your own version
        # of the real "4PM" chaise, not a purchasable physical object
        # ("does not include materials or tools", confirmed live).
        "self build",
        # Rubn's "Sample Set" is a finish/cable swatch set, not a
        # design object - same shape as the sample-swatch exclusions
        # already made for other brands.
        "sample set",
    )
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords)


def _base_name(title):
    """
    Several Shopify and WooCommerce brands don't use real variants - they
    list every finish/size combination as its own separate top-level
    product instead (confirmed on Pinch, Bitossi Ceramiche, GATOMIKIO,
    101cph, and most severely In Common With, where finish AND size are
    both baked into the title, producing 22k+ near-duplicate "products"
    for what's really a few hundred distinct designs; also confirmed on
    Another Country - WooCommerce - with titles like "Gallon Side Table,
    Low" / "Gallon Side Table, Tall"). This strips a trailing " - finish",
    " / finish", " – finish", or ", finish" so those collapse back into
    one entry per design, consistent with the "brand/design is the unit,
    not every SKU" model the rest of the schema already assumes. Shared
    by extract_shopify and extract_woocommerce.

    Also translates a trailing Japanese "型" ("type"/"shape") into
    " Type" - confirmed on GATOMIKIO's KOTON container line ("KOTON<br>
    Y型" -> "KOTON Y型" after the <br> fix above, an otherwise-readable
    English name with one stray untranslated kanji at the end since the
    site itself never gives these three variants an English name). A
    real, meaningful shape distinction (U/Y/V), not noise - translating
    it beats stripping it outright, which would lose that distinction
    with no signal left behind. Harmless no-op for every other brand's
    titles, which don't contain this character.
    """
    title = re.sub(r"<br\s*/?>", " ", title)
    title = re.sub(r"型\s*$", " Type", title.strip())
    match = re.search(r"\s[/–—-]\s|,\s", title)
    return title[: match.start()].strip() if match else title.strip()


def extract_shopify(brand):
    """
    Generic extractor for any brand running a standard Shopify store.
    Shopify exposes a public /products.json endpoint on every store by
    default - no need for brand-specific HTML parsing. Confirmed working
    for: Minimalux, Pinch, Bitossi Ceramiche, GATOMIKIO, 101cph,
    In Common With, Anna Löwenhielm Ceramics.
    """
    base = brand["url"].rstrip("/")
    raw_products = []
    page = 1
    brand_start = time.monotonic()
    while page <= MAX_PAGES_PER_BRAND:
        if time.monotonic() - brand_start > MAX_SECONDS_PER_BRAND:
            print(f"  Hit the {MAX_SECONDS_PER_BRAND // 60}-minute safety limit for "
                  f"{brand['name']} - stopping early with what was fetched so far.")
            break

        url = f"{base}/products.json?limit=250&page={page}"
        data = _fetch_json(url)
        if data is None:
            break

        batch = data.get("products", [])
        if not batch:
            break
        raw_products.extend(batch)

        page += 1
        time.sleep(1)  # be polite - don't hammer the site
    else:
        print(f"  Hit the {MAX_PAGES_PER_BRAND}-page safety limit for {brand['name']} - "
              f"stopping early with what was fetched so far.")

    raw_products = [p for p in raw_products if not _looks_like_a_class_listing(p["title"])]
    raw_products = [p for p in raw_products if not _looks_like_a_maintenance_item(p["title"])]
    raw_products = [
        p for p in raw_products
        if (p.get("product_type") or "").strip().lower() not in EXCLUDED_CATEGORIES
    ]
    raw_products = [
        p for p in raw_products
        if not {t.strip().lower() for t in (p.get("tags") or [])} & EXCLUDED_TAGS
    ]
    # A product name with zero Roman-alphabet characters (confirmed on
    # GATOMIKIO - 40 of 175 titles are Japanese-only, e.g. "その他の椀
    # 高台椀（大）") gives a non-Japanese-reading visitor nothing legible to
    # go on - excluded rather than shown as an unreadable card. Harmless
    # for every other Shopify brand here, all of which name products in
    # English. Must check the <br>-stripped title, not the raw one - the
    # literal "<br>" tag GATOMIKIO uses as a category/name separator
    # contains the Roman letters "b" and "r", which silently satisfied
    # this regex for every title regardless of its real content until
    # this was caught (2026-09-10).
    raw_products = [p for p in raw_products if re.search(r"[A-Za-z]", _base_name(p["title"]))]

    # Group same-design variant-as-separate-product listings back into one
    # entry (see _base_name), merging their distinguishing suffixes into
    # material_options so that information isn't lost, just collapsed.
    # product_type is normalized first (see _clean_product_type) since a
    # few brands use it for something other than a real category, which
    # would otherwise wrongly split one real design into duplicates.
    grouped = {}
    for p in raw_products:
        key = (_clean_product_type(p.get("product_type")), _base_name(p["title"]))
        grouped.setdefault(key, []).append(p)

    products = []
    for (product_type, base_name), group in grouped.items():
        first = group[0]
        material_options = set()
        for option in first.get("options", []):
            if option.get("name", "").lower() in ("material", "materials", "finish", "color", "colour"):
                material_options.update(option.get("values", []))

        if len(group) > 1:
            for p in group:
                suffix = p["title"][len(_base_name(p["title"])):].lstrip(" /–—-,")
                if suffix:
                    material_options.add(suffix)

        images = first.get("images", [])

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": base_name,
            "product_url": f"{base}/products/{first['handle']}",
            "category": _infer_category_from_name(base_name, product_type, brand["name"]),
            "material_options": sorted(material_options),
            "dimensions": "",
            # No longer a bare variant count here (2026-09-09) - some
            # In Common With fixtures merge 1000+ raw color/length SKUs
            # into one entry (e.g. Gemma Pendant: 1680), making a literal
            # count meaningless noise regardless of the number. Confirming
            # a specific searched-for material instead is handled at
            # query time (see filter_products()'s matched_material).
            "notes": "",
            "image_url": images[0]["src"] if images else "",
        })

    # A few brands sell a "build your own" configurator as its own listing
    # rather than a fixed design (confirmed on De La Espada: "Albireo Sofa
    # System", "Sirius Sofa System", "Frame Sofa System", "Belle Reeve Sofa
    # System" all group down to a single "CREATE YOUR OWN" material option
    # and nothing else - a link to a builder tool, not a specific piece).
    # Only excluded when that's the *entire* material_options list, not
    # just present alongside real variant names (e.g. "Sofa Eight Modular"
    # also carries "CREATE YOUR OWN" plus real ones like "Daybed"/"No
    # Arms" - those are real configurations, kept).
    products = [p for p in products if p["material_options"] != ["CREATE YOUR OWN"]]

    return products


def extract_woocommerce(brand):
    """
    Generic extractor for any brand running WooCommerce with its public
    Store API exposed (the default in current WooCommerce versions).
    Confirmed working for: Verk, Another Country.

    Another Country lists finish/size variants as separate top-level
    listings too, same pattern as several Shopify brands (e.g. "Gallon
    Side Table, Low" / "Gallon Side Table, Tall") - grouped back into one
    entry per design via the shared _base_name() helper, same as Shopify.

    Optional brand["woocommerce_category"]: for a maker who sells through
    a shared multi-maker association shop rather than their own site
    (confirmed on Konsthantverkarna.se - individual Swedish craft makers
    each get a real per-maker product_cat taxonomy term on the shared
    shop, e.g. "jonas-lindholm"), this scopes the Store API query to just
    that one maker's own products via the API's own `category` filter,
    rather than pulling the whole association's shop. "Brand" here means
    the individual maker, not the association - each such maker gets
    their own brands.json entry with this field set, all pointing at the
    same underlying site URL.
    """
    base = brand["url"].rstrip("/")
    category_filter = f"&category={brand['woocommerce_category']}" if brand.get("woocommerce_category") else ""
    raw_products = []
    page = 1
    brand_start = time.monotonic()
    while page <= MAX_PAGES_PER_BRAND:
        if time.monotonic() - brand_start > MAX_SECONDS_PER_BRAND:
            print(f"  Hit the {MAX_SECONDS_PER_BRAND // 60}-minute safety limit for "
                  f"{brand['name']} - stopping early with what was fetched so far.")
            break

        url = f"{base}/wp-json/wc/store/v1/products?per_page=100&page={page}{category_filter}"
        batch = _fetch_json(url)
        if batch is None or not batch:
            break
        # The Store API returns names/categories HTML-entity-encoded
        # (e.g. "Ash &amp; Walnut") - decode once, here, so nothing
        # downstream (grouping, display) has to think about it again.
        for p in batch:
            p["name"] = html.unescape(p["name"])
            for c in p.get("categories", []):
                c["name"] = html.unescape(c["name"])
        raw_products.extend(batch)

        page += 1
        time.sleep(1)  # be polite - don't hammer the site
    else:
        print(f"  Hit the {MAX_PAGES_PER_BRAND}-page safety limit for {brand['name']} - "
              f"stopping early with what was fetched so far.")

    # A blank name is a real, permanent state on some sites, not a fetch
    # glitch - confirmed on Piet Hein Eek's own Store API (product id
    # 52558, a real listing with a real description and photos of "Paarse
    # antieke vazen" but "name": "" at the source, itself, every time).
    # An unnamed "product" can't be shown as a meaningful search result
    # regardless of brand, so it's dropped here rather than downstream.
    raw_products = [p for p in raw_products if p["name"].strip()]

    raw_products = [
        p for p in raw_products
        if not any(c["name"].strip().lower() in EXCLUDED_CATEGORIES for c in p.get("categories", []))
    ]
    raw_products = [p for p in raw_products if not _looks_like_a_maintenance_item(p["name"])]

    # Grouped on name alone, not (categories, name) - the same real design
    # can carry inconsistent category tags across its own listed variants
    # on the source site (confirmed on Another Country: one "Coffee Table
    # Two" variant is tagged with "Tables" and "All Series", another isn't),
    # so requiring an exact category match would wrongly keep them separate.
    grouped = {}
    for p in raw_products:
        grouped.setdefault(_base_name(p["name"]), []).append(p)

    products = []
    for base_name, group in grouped.items():
        first = group[0]
        # Union of categories across the whole group, not just the first
        # item - covers the same inconsistent-tagging case above. A maker
        # who sells through a shared association shop (see
        # woocommerce_category) is filed under their own name as a
        # WooCommerce category too, alongside real ones like "Keramik" -
        # dropped here since the brand name already says that, same
        # "don't repeat the brand/category context" principle as
        # materialDuplicatesCategory in the frontend.
        categories = sorted({
            c["name"] for p in group for c in p.get("categories", [])
            if c["name"].strip().lower() != brand["name"].strip().lower()
        })
        material_options = set()
        for attr in first.get("attributes", []):
            if attr.get("name", "").lower() in ("material", "materials", "finish"):
                material_options.update(t.get("name", "") for t in attr.get("terms", []))

        if len(group) > 1:
            for p in group:
                suffix = p["name"][len(_base_name(p["name"])):].lstrip(" /–—-,")
                if suffix:
                    material_options.add(suffix)

        images = first.get("images", [])
        # Prefer the pre-sized "thumbnail" WooCommerce already generates
        # over the full-size "src" - a smaller image is all a search
        # result card needs.
        image_url = (images[0].get("thumbnail") or images[0].get("src")) if images else ""

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": base_name,
            "product_url": first.get("permalink", base),
            "category": ", ".join(categories),
            "material_options": sorted(material_options),
            "dimensions": "",
            # No longer a bare variant count here (2026-09-09) - some
            # In Common With fixtures merge 1000+ raw color/length SKUs
            # into one entry (e.g. Gemma Pendant: 1680), making a literal
            # count meaningless noise regardless of the number. Confirming
            # a specific searched-for material instead is handled at
            # query time (see filter_products()'s matched_material).
            "notes": "",
            "image_url": image_url,
        })

    return products


def extract_bigcartel(brand):
    """
    Generic extractor for any brand running Big Cartel, which exposes a
    clean public /products.json on every store by default (confirmed
    live: Patrick de Glo de Besses). No pagination needed - Big Cartel
    catalogs are small by design (it's built for independent artists/
    makers, per the resources page), and the endpoint returns every
    active + sold-out product in one response. Sold-out items are kept,
    not filtered - a design doesn't stop being real just because it's
    currently unavailable, same treatment as Yird Ceramics' sold-out
    pieces.
    """
    base = brand["url"].rstrip("/")
    data = _fetch_json(f"{base}/products.json")
    if not data:
        return []

    products = []
    for p in data:
        categories = sorted({c.get("name", "").strip() for c in p.get("categories", []) if c.get("name")})
        images = p.get("images", [])

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": p.get("name", ""),
            "product_url": f"{base}{p['url']}" if p.get("url", "").startswith("/") else p.get("url", base),
            "category": ", ".join(c.title() for c in categories),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": images[0]["url"] if images else "",
        })

    return products


def extract_bline(brand):
    """
    b-line.it (custom platform, no product API) server-renders its full
    21-item catalog on one /en/prodotti/ listing page - name (h2) and
    image (CSS background-image on the card, not an <img> tag) for
    every product, one fetch. No category on the listing itself and
    left blank rather than fetching all 21 product pages just for that -
    same tradeoff already made for H. Bigeleisen/Yird Ceramics.
    """
    domain = brand["url"].rstrip("/")
    url = f"{domain}/en/prodotti/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    for article in soup.find_all("article", class_="post"):
        link_el = article.find_parent("a", href=True)
        title_el = article.find("h2")
        image_div = article.find(class_="image-container")
        if not link_el or not title_el:
            continue

        image_url = ""
        if image_div and image_div.get("style"):
            match = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", image_div["style"])
            if match:
                image_url = match.group(1)

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": title_el.get_text(strip=True),
            "product_url": link_el["href"],
            "category": "",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_url,
        })

    return products


# omeletteeditions.com's own English URLs mix Spanish and English
# category segments (confirmed live) - a small translation map rather
# than showing the raw Spanish word on an English-language card.
OMELETTE_CATEGORIES = {
    "accesorios": "Accessories", "butacas": "Armchair", "taburetes": "Stool",
    "chairs": "Chair", "poufs": "Pouf", "side-table": "Side table",
    "sofas": "Sofa", "tables": "Table",
}


def extract_omelette_editions(brand):
    """
    omeletteeditions.com (WordPress/WooCommerce, but the Store API
    isn't exposed) has no single listing page with the full catalog -
    confirmed live, /en/productos/ itself shows category tiles, not
    products. Its own SEO sitemap (productos-sitemap.xml) is the only
    place the real per-product URLs are enumerated, so this fetches
    that instead, keeps only the English "/en/productos/{category}/
    {slug}/" URLs (dropping the parallel Spanish-language duplicates
    and the bare category-index entries), and fetches each product
    page directly for name/image (og:title/og:image) - real title/
    dimensions/materials would need more per-page parsing than 37
    products' worth of "name + image" seemed worth building for now.
    Category comes from the URL path segment itself, not a per-page
    fetch.
    """
    domain = brand["url"].rstrip("/")
    try:
        resp = requests.get(f"{domain}/productos-sitemap.xml", headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch sitemap for {brand['name']}: {e}")
        return []

    urls = re.findall(
        r"<loc>(https://[^<]+/en/productos/[a-z0-9-]+/[a-z0-9-]+/)</loc>", resp.text
    )
    urls = sorted(set(urls))

    products = []
    for url in urls:
        match = re.search(r"/en/productos/([a-z0-9-]+)/", url)
        category = OMELETTE_CATEGORIES.get(match.group(1), "") if match else ""

        try:
            page = requests.get(url, headers=HEADERS, timeout=15)
            page.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        title_match = re.search(r'<meta property="og:title" content="([^"]*)"', page.text)
        image_match = re.search(r'<meta property="og:image" content="([^"]*)"', page.text)
        if not title_match:
            continue
        name = re.sub(r"\s*-\s*Ommelette\s*$", "", title_match.group(1), flags=re.IGNORECASE)

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": category,
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_match.group(1) if image_match else "",
        })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


def extract_parenpar_ar(brand):
    """
    parenpar.com.ar runs on Tiendanube (a Latin American e-commerce
    platform, confirmed via robots.txt's own comment) - no Shopify-style
    products.json (confirmed live: returns invalid JSON), so this
    fetches the platform's own gzipped sitemap (its real location is
    published directly in robots.txt's Sitemap: line, not a guessable
    path) for the 80 real /productos/{slug}/ URLs, then fetches each
    product page directly. Every page embeds a real WebPage JSON-LD
    block with a breadcrumb trail - the second-to-last breadcrumb item
    is the real category (e.g. "Bancos y banquetas"), the last is the
    product's own name; og:image gives the real photo. Not to be
    confused with the unrelated US resort-wear brand at the plain
    ".com" domain of the same name - confirmed live this is a genuinely
    different, real furniture/lighting/ceramics maker in Argentina.
    """
    domain = brand["url"].rstrip("/")
    try:
        sitemap_index = requests.get(f"{domain}/robots.txt", headers=HEADERS, timeout=15).text
        sitemap_url_match = re.search(r"Sitemap:\s*(\S+)", sitemap_index)
        if not sitemap_url_match:
            print(f"  No sitemap declared in robots.txt for {brand['name']}")
            return []
        gz_resp = requests.get(sitemap_url_match.group(1), headers=HEADERS, timeout=15)
        gz_resp.raise_for_status()
        sitemap_xml = gzip.decompress(gz_resp.content).decode("utf-8")
    except (requests.RequestException, OSError) as e:
        print(f"  Could not fetch sitemap for {brand['name']}: {e}")
        return []

    urls = sorted(set(re.findall(rf"<loc>({re.escape(domain)}/productos/[a-z0-9-]+/)</loc>", sitemap_xml)))

    products = []
    for url in urls:
        try:
            page = requests.get(url, headers=HEADERS, timeout=15)
            page.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        webpage_data = None
        for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page.text, re.S):
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                continue
            if parsed.get("@type") == "WebPage":
                webpage_data = parsed
                break
        if not webpage_data:
            continue

        crumbs = webpage_data.get("breadcrumb", {}).get("itemListElement", [])
        name = crumbs[-1]["name"] if crumbs else webpage_data.get("name", "")
        category = crumbs[-2]["name"] if len(crumbs) >= 2 else ""

        image_match = re.search(r'<meta property="og:image" content="([^"]*)"', page.text)

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": category,
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_match.group(1) if image_match else "",
        })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


# Eric Schmitt's own category folders under /realisations_{slug} - the
# "editeurs_*" ones are the same objects re-grouped by which gallery
# represents them (would just duplicate everything already caught
# here), and "in-situ"/"projets" are installation photography, not
# standalone purchasable objects - both deliberately excluded.
ERIC_SCHMITT_CATEGORIES = {
    "assises": "Seating", "autres": "Other", "bijoux": "Jewelry",
    "bijoux-jane-schmitt": "Jewelry", "consoles": "Console",
    "elements-darchitecture": "Architectural element", "lumieres": "Lighting",
    "objets": "Object", "rangements": "Storage", "tables-basses": "Coffee table",
    "tables-dappoint": "Side table", "tables-hautes": "Table",
    "vases": "Vase",
}


def extract_eric_schmitt(brand):
    """
    ericschmitt.com (a dated custom/PHP site, confirmed permissive
    robots.txt) has no product API, but each of its 13 real category
    listing pages server-renders every item's name, designer credit,
    and image in one fetch - no per-product fetch needed, confirmed by
    checking one individual product page separately (it has real
    material/dimension detail this listing doesn't, but that's a
    smaller gap than the ~50+ extra fetches getting it would cost).
    """
    domain = brand["url"].rstrip("/")
    products = []

    for slug, category_label in ERIC_SCHMITT_CATEGORIES.items():
        url = f"{domain}/realisations_{slug}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for title_el in soup.find_all("h2", class_="b-card__title"):
            # The link is a sibling of the title's wrapper div, not an
            # ancestor - both live inside the shared ".b-card" card.
            card = title_el.find_parent(class_="b-card")
            if not card:
                continue
            link_el = card.find("a", class_="b-card__link", href=True)
            img = card.find("img")
            if not link_el:
                continue

            image_url = img.get("src", "") if img else ""
            if image_url.startswith("/"):
                image_url = f"{domain}{image_url}"
            elif image_url and not image_url.startswith("http"):
                image_url = f"{domain}/{image_url}"

            product_url = link_el["href"]
            if not product_url.startswith("http"):
                product_url = f"{domain}/{product_url}"

            products.append({
                "brand": brand["name"],
                "brand_url": brand["url"],
                "product_name": title_el.get_text(strip=True),
                "product_url": product_url,
                "category": category_label,
                "material_options": [],
                "dimensions": "",
                "notes": "",
                "image_url": image_url,
            })

        time.sleep(1)  # be polite - don't hammer the site

    return products


def extract_new_works_dk(brand):
    """
    newworks.dk was deferred on 2026-09-07 as a client-rendered Nuxt
    SPA (/en/shop's category pages returned only nav links server-
    side). Rechecked 2026-09-11 at the user's prompt and that's no
    longer true - the site now server-renders its full 150-item /en/
    shop grid directly (name, material/color, price, and a real <img
    src>, not just a lazy-load placeholder), confirmed live. No
    category signal on this listing page, left blank rather than
    fetching all 150 product pages just for that.

    Same color-variant-as-separate-listing pattern seen on several
    other brands (confirmed live: "Rand Side Table" has two separate
    product URLs, one per color/finish) - grouped by exact product
    name with the color/material line folded into material_options.
    """
    domain = brand["url"].rstrip("/")
    url = f"{domain}/en/shop"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    raw_products = []
    seen_urls = set()
    for a in soup.find_all("a", href=lambda h: h and h.startswith("/en/product/")):
        product_url = f"{domain}{a['href']}"
        if product_url in seen_urls:
            continue
        seen_urls.add(product_url)

        img = a.find("img")
        ps = a.find_all("p")
        if not ps:
            continue

        raw_products.append({
            "name": ps[0].get_text(strip=True),
            "material": ps[1].get_text(strip=True) if len(ps) > 1 else "",
            "product_url": product_url,
            "image_url": (img.get("src") or img.get("data-src") or "") if img else "",
        })

    grouped = {}
    for p in raw_products:
        grouped.setdefault(p["name"], []).append(p)

    products = []
    for name, group in grouped.items():
        first = group[0]
        materials = sorted({p["material"] for p in group if p["material"]})
        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": first["product_url"],
            "category": _infer_category_from_name(name, "", brand["name"]),
            "material_options": materials,
            "dimensions": "",
            "notes": "",
            "image_url": first["image_url"],
        })

    return products


def extract_eine_kleine_furniture(brand):
    """
    ek-furniture.com is a genuinely old, small-scale site (a 1990s-
    style HTML frameset, no real robots.txt - the request itself 404s
    at the host level) for a tiny Seoul-based white-oak furniture
    maker - exactly the "smallest, least-resourced maker" tier this
    project targets. Real catalog lives on a Korean forum/board CMS
    (Gnuboard-style, confirmed live), split across two boards
    ("original" ready-made pieces, "order_made" custom pieces). Each
    listing page already server-renders every item's name and
    thumbnail as a pair of <a> tags sharing the same wr_id (one wraps
    the image, one wraps the text) - no per-post fetch needed, just
    the two board listing pages.
    """
    domain = brand["url"].rstrip("/")
    boards = {"original": "Furniture (original)", "order_made": "Furniture (made to order)"}
    products = []

    for bo_table, category_label in boards.items():
        url = f"{domain}/board/bbs/board.php?bo_table={bo_table}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        by_wr_id = {}
        for a in soup.find_all("a", href=lambda h: h and "wr_id=" in h):
            match = re.search(r"wr_id=(\d+)", a["href"])
            if not match:
                continue
            wr_id = match.group(1)
            entry = by_wr_id.setdefault(wr_id, {"name": "", "image_url": ""})

            text = a.get_text(strip=True)
            if text:
                entry["name"] = text

            img = a.find("img")
            if img and img.get("src"):
                src = img["src"].lstrip("./")
                entry["image_url"] = f"{domain}/board/{src}"

        for wr_id, entry in by_wr_id.items():
            if not entry["name"] or not entry["image_url"]:
                continue
            products.append({
                "brand": brand["name"],
                "brand_url": brand["url"],
                "product_name": entry["name"],
                "product_url": f"{domain}/board/bbs/board.php?bo_table={bo_table}&wr_id={wr_id}",
                "category": category_label,
                "material_options": [],
                "dimensions": "",
                "notes": "",
                "image_url": entry["image_url"],
            })

        time.sleep(1)  # be polite - don't hammer the site

    return products


def extract_jon_goulder(brand):
    """
    jongoulder.com's own /work-... listing page (Squarespace) server-
    renders every product's image and link, but not a visible name -
    it's a pure image gallery, no caption text on the grid itself
    (confirmed live). Each individual product page does have a real
    title (page <title>, prefixed with "Jon Goulder " - stripped here),
    so this fetches the listing once for slugs + images, then each of
    the ~17 real product pages once for its title - a small, bounded
    number of extra fetches for real names instead of guessing from
    the URL slug. "catalogue-*" links on the same listing are separate
    downloadable collection catalogues, not individual products, and
    are skipped.
    """
    domain = brand["url"].rstrip("/")
    listing_url = f"{domain}/work-furniture-objects-lighting"
    try:
        resp = requests.get(listing_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {listing_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    skip_slugs = {"", "about-workshop-design-studo", "cart", "commission", "work-furniture-objects-lighting"}
    slugs = []
    for a in soup.find_all("a", href=True):
        slug = a["href"].strip("/")
        if slug.startswith("catalogue-") or slug in skip_slugs or slug in slugs:
            continue
        if a.find("img"):
            slugs.append(slug)

    products = []
    for slug in slugs:
        product_url = f"{domain}/{slug}"
        try:
            page = requests.get(product_url, headers=HEADERS, timeout=15)
            page.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {product_url}: {e}")
            continue

        title_match = re.search(r"<title>([^<]*)</title>", page.text)
        name = re.sub(r"^Jon Goulder\s*-?\s*", "", title_match.group(1).strip()) if title_match else slug

        img = None
        for a in soup.find_all("a", href=lambda h: h and h.strip("/") == slug):
            img = a.find("img")
            if img:
                break
        image_url = (img.get("data-src") or img.get("src", "")) if img else ""

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": product_url,
            "category": _infer_category_from_name(name, "", brand["name"]),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_url,
        })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


# Slugs on lachambredami.com's own product sitemap that are consumables/
# accessories, not durable design objects: room-fragrance refills/samples
# (parfum-d-ambiance), a plain lightbulb, a generic electrical fitting, and
# a tote bag.
LA_CHAMBRE_DAMI_SKIP_SLUGS = {
    "automne-parfum-d-ambiance-intervalles-studio",
    "hiver-parfum-d-ambiance-intervalles-studio",
    "pritemps-parfum-d-ambiance-intervalles-studio",
    "ete-parfum-d-ambiance-intervalles-studio",
    "echantillon-parfum-d-ambiance",
    "pack-découverte-parfum-d-ambiance",
    "ampoule-e27",
    "suspension-électrique-e27",
    "tote-bag-cadeau",
    # A genuinely retired listing, not a category gap - its own sitemap
    # URL still 200s, but the page itself says "Cet article est
    # introuvable" (this article can't be found), confirmed live
    # 2026-09-21 while auditing other brands for Established & Sons'
    # same "discontinued but still listed" pattern.
    "prototype-flower-1",
}


def extract_la_chambre_dami(brand):
    """
    lachambredami.com (Wix Stores) exposes a real store-products-sitemap.xml
    with every product URL, and each /product-page/{slug} server-renders
    reliable og:title/og:image tags - no price/category available though
    (color/material is a buyer-chosen option, not fixed per listing). A
    handful of sitemap entries are consumables/
    accessories rather than design objects (room-fragrance refills, a bare
    lightbulb, a generic electrical fitting, a tote bag) - skipped via
    LA_CHAMBRE_DAMI_SKIP_SLUGS since there's no category field to filter on.
    """
    sitemap_url = f"{brand['url'].rstrip('/')}/store-products-sitemap.xml"
    try:
        sitemap_resp = requests.get(sitemap_url, headers=HEADERS, timeout=15)
        sitemap_resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {sitemap_url}: {e}")
        return []

    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap_resp.text)
    products = []
    for url in urls:
        slug = url.rstrip("/").split("/")[-1]
        if slug in LA_CHAMBRE_DAMI_SKIP_SLUGS:
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        og_title = soup.find("meta", property="og:title")
        name = og_title["content"].split(" | ")[0].strip() if og_title and og_title.get("content") else slug
        og_image = soup.find("meta", property="og:image")

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": "",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": og_image["content"] if og_image and og_image.get("content") else "",
        })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


def extract_esther_knopfler(brand):
    """
    estherknopfler.com (Wix Portfolio) exposes every piece on
    portfolio-projects-sitemap.xml as /portfolio-collections/{collection}/
    {slug} - a clean, all-real 24-item list of marble furniture (checked:
    no consumables/junk, unlike lachambredami.com). The collection segment
    in the URL doubles as a free category signal (e.g. "burger-collection"
    -> "Burger Collection") with no extra fetch. Each product page's
    og:title is server-rendered and reliable, but og:image is broken on
    9 of the 24 pieces (confirmed live, e.g. "Lilly dining table") -
    those specific pages' og:image points at a plain-UUID Wix media asset
    with no "~mv2" suffix, which 404s/403s when actually fetched, while
    the same page's own real gallery photos (proper "~mv2"-suffixed
    assets) load fine. Detected by checking for "~mv2" in og:image's own
    URL; when missing, falls back to the first non-logo "~mv2" image
    found in the page's own <img> tags (skipping the shared site-logo
    asset by its own fixed ID, and skipping each asset's tiny "w_1,h_1"
    placeholder duplicate for the same reason) - confirmed this lands on
    the correct per-piece hero photo on both a working-og:image page and
    a broken one.
    """
    ESTHER_KNOPFLER_LOGO_ASSET = "6f70b2_7ecbc972b36e4e43a7f53610c2801295"
    sitemap_url = f"{brand['url'].rstrip('/')}/portfolio-projects-sitemap.xml"
    try:
        sitemap_resp = requests.get(sitemap_url, headers=HEADERS, timeout=15)
        sitemap_resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {sitemap_url}: {e}")
        return []

    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap_resp.text)
    products = []
    for url in urls:
        parts = url.rstrip("/").split("/")
        collection_slug = parts[-2] if len(parts) >= 2 else ""
        category = collection_slug.replace("-collection", "").replace("-", " ").title()
        if collection_slug == "untitled-collection":
            category = ""

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        og_title = soup.find("meta", property="og:title")
        name = og_title["content"].split(" | ")[0].strip() if og_title and og_title.get("content") else parts[-1]
        og_image = soup.find("meta", property="og:image")
        image_url = og_image["content"] if og_image and og_image.get("content") else ""
        if "~mv2" not in image_url:
            fallback = soup.find(
                "img",
                src=lambda s: s and "~mv2" in s and "w_1,h_1" not in s and ESTHER_KNOPFLER_LOGO_ASSET not in s,
            )
            image_url = fallback["src"] if fallback else ""

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": category,
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_url,
        })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


def extract_mercoeur_editions(brand):
    """
    mercoeur-edition.com (Webflow) server-renders its full 18-item catalog
    on one /all-products listing page - name, link, and image for every
    product in one fetch, no per-product pages needed. Each name is really
    two separate text nodes (collection name, then object type, e.g.
    "Ondine" + "Set of 3 boxes") with no space between them in the
    markup - get_text(strip=True) was concatenating them straight
    together ("OndineSet of 3 boxes"), a real display-name bug caught
    while investigating why this brand had no category data at all, not
    just a categorization gap (confirmed live 2026-09-21: every one of
    its 18 products was affected). get_text(" ", strip=True) joins them
    with the space the markup itself doesn't have, which also makes the
    object type in each name matchable by the shared English keyword
    inference below.
    """
    domain = brand["url"].rstrip("/")
    url = f"{domain}/all-products"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    for a in soup.find_all("a", href=True):
        if "/products/" not in a["href"]:
            continue
        img = a.find("img")
        name = a.get_text(" ", strip=True)
        if not img or not name:
            continue

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": f"{domain}{a['href']}" if a["href"].startswith("/") else a["href"],
            "category": _infer_category_from_name(name, "", brand["name"]),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img.get("src", ""),
        })

    return products


def extract_wastberg(brand):
    """
    wastberg.com is a custom catalog (checkout is a separate connected
    Shopify backend, but the browsable site itself is not Shopify - no
    /products.json) - the /en/products listing server-renders every
    product link + a grid thumbnail, but names live one level down. Each
    product page's <h1>/<h2> cleanly split into collection name ("FARO")
    and mount type ("TABLE") - combined as the display name. The bare
    mount type alone (Ceiling/Wall/Floor/Table/Suspended/Track/Base/
    Bracket/Clamp/Pin/Semi-Recessed) doesn't contain a lighting word, so
    it silently failed both the umbrella classifier and the search
    backend's category matcher (confirmed live 2026-09-20 - Wästberg
    never surfaced under Lighting anywhere on the site, and "Table" even
    misclassified as Furniture - see project memory); WASTBERG_CATEGORY_
    SUFFIX below appends the real product-type word ("Table" -> "Table
    Lamp") while keeping the mount type as the tag's own leading word.
    The listing page's own thumbnail isn't reliably paired per-product (a shared
    lifestyle-photo carousel intermixes with the real product shot), so
    each product page's own primary image is found by matching its PIM
    asset path against the product's own URL slug with the trailing model
    code stripped (e.g. "faro-table-w241" -> "faro-table") - confirmed
    against two different real PIM path shapes this site actually uses
    (one embeds the full name+model code in the folder name, the other
    just a numeric asset id, but both always embed the kebab-case name in
    the filename itself).
    """
    domain = brand["url"].rstrip("/")
    listing_url = f"{domain}/en/products"
    try:
        resp = requests.get(listing_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {listing_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    slugs = []
    for a in soup.find_all("a", href=True):
        match = re.match(r"^/en/products/([a-z0-9-]+)(\?|$)", a["href"])
        if match and match.group(1) not in slugs:
            slugs.append(match.group(1))

    products = []
    for slug in slugs:
        product_url = f"{domain}/en/products/{slug}"
        try:
            page = requests.get(product_url, headers=HEADERS, timeout=15)
            page.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {product_url}: {e}")
            continue

        page_soup = BeautifulSoup(page.text, "html.parser")
        h1 = page_soup.find("h1")
        h2 = page_soup.find("h2")
        if not h1 or not h2:
            continue
        collection = h1.get_text(strip=True)
        mount_type = h2.get_text(strip=True)
        name = f"{collection.title()} {mount_type.title()}"

        # Bare mount type ("Table", "Wall", "Suspended"...) never
        # contains a lighting word itself, so both the static-page
        # umbrella classifier (generate_brand_pages.py) and the search
        # backend's category matcher (query_engine.py, same keyword
        # list) silently miss every Wästberg product - confirmed live
        # 2026-09-20: Wästberg never appeared for a "lighting" search or
        # under Lighting anywhere on the site, and "Table" even got
        # misclassified as Furniture. Appending the actual product-type
        # word fixes both without losing the real mount-type distinction
        # ("Table" vs "Wall" vs "Suspended" stays the tag's own leading
        # word - see project memory).
        WASTBERG_CATEGORY_SUFFIX = {
            "Suspended": "Suspension Lamp",
            "Table": "Table Lamp",
            "Wall": "Wall Lamp",
            "Floor": "Floor Lamp",
            "Ceiling": "Ceiling Lamp",
            "Track": "Track Lamp",
            "Semi-Recessed": "Semi-Recessed Lamp",
            "Base": "Base Lamp",
            "Bracket": "Bracket Lamp",
            "Clamp": "Clamp Lamp",
            "Pin": "Pin Lamp",
        }
        category = WASTBERG_CATEGORY_SUFFIX.get(mount_type.title(), f"{mount_type.title()} Lamp")

        base_key = re.sub(r"-w\d+[a-z0-9]*$", "", slug)
        image_url = ""
        img = page_soup.find("img", src=re.compile(rf"/pim/.*{re.escape(base_key)}", re.IGNORECASE))
        if img:
            image_url = img["src"]
            if image_url.startswith("/"):
                image_url = f"{domain}{image_url}"
            # A missing source asset on Wästberg's own PIM (confirmed
            # live 2026-09-21 on "Alma Ceiling"/asset id 4200 - broke
            # makers.html's hero thumbnail for the whole brand) doesn't
            # 404: the URL still 200s and still ends in .png, but the
            # real response is a tiny placeholder SVG. Checked via a
            # HEAD request rather than trusting the src attribute alone.
            try:
                head = requests.head(image_url, headers=HEADERS, timeout=10)
                if "svg" in head.headers.get("Content-Type", "").lower():
                    image_url = ""
            except requests.RequestException:
                pass

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": product_url,
            "category": category,
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_url,
        })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


SE_COLLECTIONS_CATEGORIES = [
    "cabinets", "chairs", "lighting", "mirrors",
    "sofas-and-armchairs", "tables", "decorative",
]


def extract_se_collections(brand):
    """
    se-collections.com is a Next.js site whose product-grid <img> tags are
    lazy-loaded (initial src is a base64 placeholder, real image swapped in
    by JS) - but each one has a <noscript><img alt="{name}" src="{real
    image}"> fallback already server-rendered right alongside it, which
    conveniently gives both a clean name and a real image with zero extra
    fetches. One listing page per of the site's own 7 top-level categories
    (SE_COLLECTIONS_CATEGORIES) covers the whole catalog.
    """
    domain = brand["url"].rstrip("/")
    products = []
    seen_urls = set()

    for category in SE_COLLECTIONS_CATEGORIES:
        url = f"{domain}/products/{category}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        prefix = f"/products/{category}/"
        for a in soup.find_all("a", href=True):
            if not a["href"].startswith(prefix):
                continue
            product_url = f"{domain}{a['href']}"
            if product_url in seen_urls:
                continue
            noscript = a.find("noscript")
            if not noscript:
                continue
            img = BeautifulSoup(noscript.decode_contents(), "html.parser").find("img")
            if not img or not img.get("src"):
                continue
            seen_urls.add(product_url)

            products.append({
                "brand": brand["name"],
                "brand_url": brand["url"],
                "product_name": img.get("alt", "").strip() or a["href"].rsplit("/", 1)[-1],
                "product_url": product_url,
                "category": category.replace("-", " ").title(),
                "material_options": [],
                "dimensions": "",
                "notes": "",
                "image_url": img["src"],
            })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


GUBI_CATEGORIES = [
    "lighting", "seating", "tables", "desk-storages", "rugs",
    "mirrors-2", "outdoor", "accessories",
]


def extract_gubi(brand):
    """
    gubi.com is a Next.js App Router site - unlike se-collections.com's
    lazy-loaded images, these have no static src/srcset/noscript fallback
    at all (confirmed: the <img> tag in each category-grid card is empty
    until client JS runs), and there's no products.json/API. Name + URL
    are still real text in the server-rendered card though, so those come
    from GUBI_CATEGORIES' 8 listing pages (site's own top-level categories
    from its own sitemap.xml, minus spare-parts/upholstery-swatches/news -
    not real products) with zero extra fetches - name specifically comes
    from the "product_info" div's span, not just the card's first span,
    since a "News" badge (its own separate span, elsewhere in the card)
    would otherwise get grabbed instead for newly-launched products. The
    listing a product is
    found under also gives category for free. Images need one fetch per
    product (each product page's own og:image is reliable) - bounded by
    the same MAX_SECONDS_PER_BRAND ceiling every other brand respects, so
    a slow day yields partial-but-correct coverage rather than blowing the
    whole run's time budget.
    """
    domain = brand["url"].rstrip("/")
    seen = {}
    for category in GUBI_CATEGORIES:
        url = f"{domain}/en/se/categories/{category}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            if "/products/" not in a["href"]:
                continue
            info_div = a.find("div", class_=lambda c: c and "product_info" in c)
            span = info_div.find("span") if info_div else None
            if not span:
                continue
            product_url = f"{domain}{a['href']}" if a["href"].startswith("/") else a["href"]
            if product_url not in seen:
                seen[product_url] = (span.get_text(strip=True), category.replace("-2", "").replace("-", " ").title())
        time.sleep(0.5)  # be polite - don't hammer the site

    products = []
    brand_start = time.monotonic()
    for product_url, (name, category) in seen.items():
        if time.monotonic() - brand_start > MAX_SECONDS_PER_BRAND:
            print(f"  Hit the {MAX_SECONDS_PER_BRAND // 60}-minute safety limit for "
                  f"Gubi's per-product image fetches - stopping with {len(products)} done.")
            break
        try:
            page = requests.get(product_url, headers=HEADERS, timeout=15)
            page.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {product_url}: {e}")
            continue

        page_soup = BeautifulSoup(page.text, "html.parser")
        og_image = page_soup.find("meta", property="og:image")

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": product_url,
            "category": category,
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": og_image["content"] if og_image and og_image.get("content") else "",
        })
        time.sleep(0.3)  # be polite - don't hammer the site

    return products


# The real per-product taxonomy this brand's own site uses (confirmed
# live 2026-09-21) is already present right on the /product/ listing
# page, just not where the original version of this extractor looked -
# each result sits inside an <article> whose class list carries a flat
# set of "filcat-*" filter tags mixing several different taxonomies
# together (subfunction/object-type, material, room/use, designer, and
# collection/family - e.g. "360" or "cyborg-family" name a design line,
# not an object type). Built by reading every real filcat-* value
# across the full live catalog (98 distinct values) and keeping only
# the ones that are genuinely an object type, not a material/room/
# designer/collection name. "magis-me-too"/"animal-factory" are Magis's
# own children's lines (confirmed: none of their real products carry
# any of the object-type tags below either, since a toy isn't a chair
# or table) - tagged "Toy" rather than left blank or forced into a
# furniture category that doesn't fit.
MAGIS_SUBFUNCTION_TO_CATEGORY = {
    "chairs-and-small-armchairs": "Chair",
    "armchair-and-lounge": "Armchair",
    "bar-tables": "Bar Table",
    "low-tables": "Coffee Table",
    "tables": "Table",
    "benches": "Bench",
    "stools": "Stool",
    "ottomans": "Ottoman",
    "sofas-and-modular-sofas": "Sofa",
    "storage-and-shelving-systems": "Shelving",
    "coat-stand-hanger": "Coat Stand",
    "carpets": "Rug",
    "mirrors": "Mirror",
    "lighting": "Light",
    "accessories": "Accessories",
    "public-seating-system": "Seating",
    "magis-me-too": "Toy",
    "animal-factory": "Toy",
}


def extract_magis(brand):
    """
    magisdesign.com (WordPress) server-renders its entire ~250-item catalog
    on one /product/ listing page - name (h2), designer + price (p), and
    image all inline per card (a.load), no per-product fetch needed. Real
    category comes from each result's own <article> wrapper (see
    MAGIS_SUBFUNCTION_TO_CATEGORY), not the <a class="load"> itself.
    """
    domain = brand["url"].rstrip("/")
    url = f"{domain}/product/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    for article in soup.find_all("article"):
        a = article.find("a", class_="load", href=True)
        h2 = article.find("h2")
        img = article.find("img")
        if not a or not h2 or not img:
            continue

        filcats = {c[len("filcat-"):] for c in article.get("class", []) if c.startswith("filcat-")}
        categories = sorted({
            MAGIS_SUBFUNCTION_TO_CATEGORY[f] for f in filcats if f in MAGIS_SUBFUNCTION_TO_CATEGORY
        })

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": h2.get_text(strip=True),
            "product_url": a["href"],
            "category": ", ".join(categories),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img.get("src", ""),
        })

    return products


def extract_grain(brand):
    """
    graindesign.com's Squarespace Commerce /shop page server-renders its
    full 88-item catalog on one listing (name via a's aria-label, image via
    img's data-image/src) - no per-product fetch needed, and its own
    ?format=json fallback is explicitly disallowed in robots.txt here
    (unlike other Squarespace brands in this project), so the HTML listing
    is the only option anyway. Excludes anything with "sample" in the name
    (confirmed: 4 real material-swatch listings mixed into the main /shop
    grid, $1 each - not design objects), and "utility card" (confirmed
    live 2026-09-21: a letterpress-printed paper greeting card, not a
    design object either) since there's no separate category field to
    filter on generically.
    """
    domain = brand["url"].rstrip("/")
    url = f"{domain}/shop"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    seen_urls = set()
    for a in soup.find_all("a", class_="product-list-item-link", href=True):
        name = a.get("aria-label", "").strip()
        if not name or "sample" in name.lower() or "utility card" in name.lower():
            continue
        product_url = f"{domain}{a['href']}" if a["href"].startswith("/") else a["href"]
        if product_url in seen_urls:
            continue
        seen_urls.add(product_url)
        img = a.find("img")
        image_url = (img.get("data-image") or img.get("src", "")) if img else ""

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": product_url,
            "category": _infer_category_from_name(name, "", brand["name"]),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": image_url,
        })

    return products


def extract_will_choui(brand):
    """
    willchoui.com (Framer) is a small Montreal furniture designer's site -
    /collections/collectibles server-renders all 8 real pieces (2 more than
    the homepage itself shows, which only teases 6), each as a plain image
    link with the product name as its own parent element's text (no alt
    text on the <img> itself) - one fetch, no per-product pages needed.
    "commissions" is bespoke/custom work with no fixed catalog, correctly
    excluded (not a product link, a different kind of page entirely).
    """
    domain = brand["url"].rstrip("/")
    url = f"{domain}/collections/collectibles"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.match(r"^\./[a-z0-9-]+$", href) or href in ("./collectibles", "./commissions"):
            continue
        img = a.find("img")
        if not img or href in seen:
            continue
        seen.add(href)
        name = a.parent.get_text(strip=True) if a.parent else href.lstrip("./")

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": f"{domain}/collections/{href.lstrip('./')}",
            "category": "",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img.get("src", ""),
        })

    return products


SIZAR_ALEXIS_COLLECTIONS = ["itooraba", "lahmu", "ode", "pilier", "ousia", "amal", "bel"]
SIZAR_ALEXIS_SKIP_STRONGS = {
    "materials", "edition details", "delivery time", "dimensions", "enquire",
    "contact", "about", "collections", "exhibitions", "press",
}


def extract_sizar_alexis(brand):
    """
    sizaralexis.se was previously excluded (2026-09-01) for a JS-rendered
    homepage gallery - re-checked 2026-09-11 and its actual catalog pages
    have since turned out to be plain, fully server-rendered WordPress
    content (confirmed live: /ode/ renders real prose, dimensions,
    materials). Each of the site's own 7 named collections
    (SIZAR_ALEXIS_COLLECTIONS, from its /collection/ index) is a single
    page holding several individual pieces with no product-card markup -
    each real piece's name is a <strong> tag reading "{Collection} {Type}"
    (e.g. "Ode Chair"), interspersed with skippable metadata labels
    (Materials/Edition details/etc, in SIZAR_ALEXIS_SKIP_STRONGS) and the
    bare collection title itself. Walked in document order, tracking the
    most recent real <img> src seen, since each piece's own photos appear
    directly before its name rather than after. One collection ("bel") has
    no such per-piece breakdown at all - it's a single design object, so
    the whole page is treated as one product using its own <title>.
    """
    domain = brand["url"].rstrip("/")
    products = []

    for slug in SIZAR_ALEXIS_COLLECTIONS:
        url = f"{domain}/{slug}/"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        body = soup.body or soup
        last_image = ""
        found_any = False
        for el in body.find_all(["img", "strong"]):
            if el.name == "img":
                src = el.get("src") or el.get("data-src") or ""
                if src and "loggan" not in src.lower():
                    last_image = src
                continue

            text = el.get_text(strip=True)
            if not text or len(text) > 60:
                continue
            if text.lower() in SIZAR_ALEXIS_SKIP_STRONGS:
                continue
            if text.upper() == text and text.split() == [slug.upper()]:
                continue  # the bare collection title itself, not a piece

            found_any = True
            products.append({
                "brand": brand["name"],
                "brand_url": brand["url"],
                "product_name": text,
                "product_url": url,
                "category": _infer_category_from_name(text, "", brand["name"]),
                "material_options": [],
                "dimensions": "",
                "notes": "",
                "image_url": last_image,
            })

        if not found_any:
            title = soup.find("title")
            name = title.get_text(strip=True).split(" – ")[0].strip() if title else slug.title()
            first_img = next(
                (img.get("src") or img.get("data-src", "")
                 for img in body.find_all("img")
                 if "loggan" not in (img.get("src") or "").lower()),
                "",
            )
            products.append({
                "brand": brand["name"],
                "brand_url": brand["url"],
                "product_name": name,
                "product_url": url,
                "category": _infer_category_from_name(name, "", brand["name"]),
                "material_options": [],
                "dimensions": "",
                "notes": "",
                "image_url": first_img,
            })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


def extract_monsieur_cailloux(brand):
    """
    monsieurcailloux.com was previously excluded for a client-rendered
    collection/cart template - re-checked 2026-09-11 against the user's
    own /shop/products link and that turned out wrong: it's a Webflow CMS
    "collection list" that does server-render real data (dimensions, name,
    price), just structured unusually - each piece is a div.collection-item
    holding a metadata block, an aria-label-only link overlay (no name/
    image inside the <a> itself), and a separate div.product-description
    sibling with the real name and price, plus an <img> in a repeater
    block. No pagination controls found (checked), so the ~28 items on
    this one page are treated as the full catalog for this single-artist
    ceramics practice. The site's own categories are color swatches -
    /category/white, /category/black, etc - not object types, and every
    piece is named just "Specimen N°XXX" with no distinguishing word of
    any kind. But every one really is the same object type - checked
    several of the real product photos (2026-09-21): small, non-
    functional decorative ceramic sculptures, not vessels - so
    hardcoded as "Sculpture, Ceramics" here rather than left blank.
    "Ceramics" is added explicitly since the material itself is real
    clay even though the form isn't a vessel - neither UMBRELLA_KEYWORDS
    nor HYPERNYM_WORDS's Ceramics lists would infer that on their own
    (both are vessel-shaped words - vase/bowl/plate/...). At query time
    this makes both a "ceramics" and an "objects" search find these
    (see query_engine.py's own "objects" hypernym, which already
    includes real ceramics items); the brand-page umbrella pill shows
    "Ceramics" specifically rather than "Objects" too, since a literal
    category match short-circuits that logic (see
    _umbrellas_for_product) - a cosmetic difference, not a search gap.
    """
    domain = brand["url"].rstrip("/")
    url = f"{domain}/shop/products"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    for item in soup.find_all("div", class_="collection-item"):
        link = item.find("a", href=True)
        name_el = item.find("div", class_="product-name-text")
        img = item.find("img")
        if not link or not name_el:
            continue

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name_el.get_text(strip=True),
            "product_url": f"{domain}{link['href']}" if link["href"].startswith("/") else link["href"],
            "category": "Sculpture, Ceramics",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img.get("src", "") if img else "",
        })

    return products


def extract_established_and_sons(brand):
    """
    establishedandsons.com has no robots.txt at all (returns the site's
    own 404 page for the path, not a block) and a real XML sitemap index
    with a dedicated products sitemap (138 URLs) - no per-category
    crawling needed. Each product page is server-rendered with a real
    "Design / Description / Dimensions / Materials / ..." free-text block
    (a <div class="block"> of <p> tags, each starting with a <strong>
    label), not clean structured fields - confirmed on Medusa (a lamp
    family sold as pendant/wall/table variants across 3 sizes, all under
    one URL, same "family, not per-SKU" shape as a Shopify product with
    variants). Dimensions/materials are kept as the label's own raw
    multi-line text (line breaks joined with " / ") rather than trying to
    parse per-variant numbers out of it - still far more informative than
    leaving it blank, without guessing which variant a shopper meant.
    Category is now hardcoded per product as a manual override (see
    MANUAL_CATEGORY_OVERRIDES) - checked live 2026-09-21 against the
    site's own 8 real category pages at /collection/categories/{name}
    (found via its sitemaps-1-categorygroup-productType sitemap), which
    together cover only ~40 of the 138 sitemap URLs. The other ~85 are
    discontinued stub pages that still 200 but carry none of the real
    <strong>-labeled Design/Description/Dimensions/Materials content
    every current product has (confirmed live: 0 of 32 category-page-
    confirmed products lack it, vs. 85 of the remaining 92 that do) -
    and their real gallery is empty too (og:image is the only image
    reference left, a stale fallback pointing at an old asset that
    still resolves but is no longer shown on the live page - confirmed
    on "Axis," "Bend"). Rather than surface those as a "visit source"
    link to an empty page, they're skipped entirely here. The 7
    genuinely current products the category pages don't cover (Drift,
    Aqua Table, ...) were each checked against their own real
    "Description:" field instead.
    """
    domain = brand["url"].rstrip("/")
    try:
        resp = requests.get(f"{domain}/sitemaps-1-section-products-1-sitemap.xml", headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch products sitemap for {brand['name']}: {e}")
        return []

    urls = re.findall(r"<loc>([^<]+)</loc>", resp.text)

    def _label_text(soup, label):
        for strong in soup.find_all("strong"):
            if label.lower() in strong.get_text(strip=True).lower():
                parts = []
                for sib in strong.next_siblings:
                    if getattr(sib, "name", None) == "strong":
                        break
                    text = sib if isinstance(sib, str) else sib.get_text()
                    parts.append(text.strip())
                joined = " / ".join(p for p in parts if p)
                return re.sub(r"\s*/\s*/\s*", " / ", joined).strip(" /")
        return ""

    products = []
    brand_start = time.monotonic()
    for url in urls:
        if time.monotonic() - brand_start > MAX_SECONDS_PER_BRAND:
            print(f"  Hit the {MAX_SECONDS_PER_BRAND // 60}-minute safety limit for "
                  f"{brand['name']} - stopping early with what was fetched so far.")
            break
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        h1 = soup.find("h1")
        og_image = soup.find("meta", property="og:image")
        if not h1:
            continue

        # A discontinued stub page (confirmed live on "Axis"/"Bend"):
        # no <strong>-labeled content block at all, and its real
        # gallery is gone - the only image reference left is a stale
        # og:image fallback that still resolves as a file but is no
        # longer shown on the page itself. Skipped entirely rather
        # than sending a "visit source" link to an empty page.
        if not soup.find_all("strong"):
            continue

        materials_text = _label_text(soup, "Materials")
        materials = [m.strip() for m in materials_text.split(" / ") if m.strip()] if materials_text else []
        name = h1.get_text(strip=True).title()

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": MANUAL_CATEGORY_OVERRIDES.get((brand["name"], name), ""),
            "material_options": materials,
            "dimensions": _label_text(soup, "Dimensions"),
            "notes": "",
            "image_url": og_image.get("content", "") if og_image else "",
        })
        time.sleep(1)  # be polite - don't hammer the site

    return products


def extract_galerie_kreo(brand):
    """
    galeriekreo.com has no robots.txt restrictions and, unusually, its
    entire 985-piece catalog is server-rendered on one single listing
    page (/en/pieces/, ~1.2MB) rather than paginated - confirmed live,
    no "page 2" link exists and the raw HTML already contains all 985
    unique /en/piece/ links. This is a deliberate choice, not a fallback:
    fetching 985 individual piece pages would blow well past
    MAX_SECONDS_PER_BRAND for a site with no real time-saving API, while
    the one listing page already carries everything a search result
    needs (name, designer, image).

    The page is an Elementor export and only ONE of the 985 cards
    (confirmed live) uses a clean self-contained <a> with pieceName/
    designerName classes - that was the first card checked during
    triage and wrongly assumed to be the standard shape. The other 984
    split the image into its own `<a class="piece-img">` and the name/
    designer text into a sibling `.x-text` block within the same
    container <div>, with no shared class naming between cards. Handled
    by anchoring on the one reliably-repeated element (`a.piece-img`),
    then reading its parent container for the second <a> (same href,
    the name) and the first <p> (the designer) - confirmed to resolve
    all 985 cards, not just the one outlier. No dimensions/materials are
    available at this level - same tradeoff already accepted for
    several Shopify/WooCommerce brands here.
    """
    domain = brand["url"].rstrip("/")
    url = f"{domain}/en/pieces/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []
    seen_urls = set()
    for img_a in soup.find_all("a", class_="piece-img", href=True):
        href = img_a["href"]
        if href in seen_urls:
            continue
        seen_urls.add(href)

        container = img_a.parent
        name_link = next(
            (l for l in container.find_all("a", href=href) if l is not img_a), None
        )
        designer_el = container.find("p")
        img = img_a.find("img")
        if not name_link or not name_link.get_text(strip=True):
            continue

        name = name_link.get_text(strip=True)
        designer = designer_el.get_text(strip=True) if designer_el else ""
        img_src = img.get("src", "") if img else ""
        if img_src.startswith("/"):
            img_src = f"{domain}{img_src}"

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": f"{name} ({designer})" if designer else name,
            "product_url": f"{domain}{href}",
            "category": "",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img_src,
        })

    return products


def extract_workstead(brand):
    """
    workstead.com has a real XML sitemap with 90 /shop/ product URLs
    (server-rendered despite the site's heavy Alpine.js cart widget -
    confirmed live, the actual product name/description/images are
    plain HTML, only the "add to cart" interaction is JS). The bare
    "/shop/" listing URL itself is excluded (it's the category root, not
    a product). Each product page's real name is only reliably found in
    the page <title> (before " | Workstead") - the visible on-page
    heading duplicates the full nav on this theme, not just the name.
    """
    domain = brand["url"].rstrip("/")
    try:
        resp = requests.get(f"{domain}/sitemap.xml", headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch sitemap for {brand['name']}: {e}")
        return []

    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", resp.text)
            if re.search(r"/shop/[^/]+/?$", u) and not u.rstrip("/").endswith("/shop")]

    products = []
    brand_start = time.monotonic()
    for url in urls:
        if time.monotonic() - brand_start > MAX_SECONDS_PER_BRAND:
            print(f"  Hit the {MAX_SECONDS_PER_BRAND // 60}-minute safety limit for "
                  f"{brand['name']} - stopping early with what was fetched so far.")
            break
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.find("title")
        if not title:
            continue
        name = title.get_text(strip=True).split("|")[0].strip()
        if not name:
            continue

        # No og:image on this site. Every product page opens its gallery
        # with the same shared, non-product-specific hardware reference
        # shot (a ceiling-canopy detail photo hosted on a distinct
        # "tff-ws3.imgix.net" subdomain) before the real per-product
        # photos - confirmed on Bole Sconce, Mega ADA Sconce, House
        # Sconce, Orbit Sconce, all four opening with that identical
        # image. The genuine per-product gallery is reliably hosted on
        # "m-workstead.imgix.net" instead (confirmed across every product
        # checked, including ones that also carry a differently-folder-
        # named "featured" PNG) - so that subdomain specifically is
        # matched, rather than the first image on the page or any src
        # containing "featured", both of which picked up the shared
        # filler photo on roughly half the catalog during testing.
        img = soup.find("img", src=re.compile(r"m-workstead\.imgix\.net/"))
        img_src = img.get("src", "") if img else ""

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": _infer_category_from_name(name, "", brand["name"]),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img_src,
        })
        time.sleep(1)  # be polite - don't hammer the site

    return products


def extract_maruni(brand):
    """
    maruni.com has no robots.txt restrictions and its full
    product catalog - 223 items - is listed with real, server-rendered
    links on the single /en/product/ page, no pagination needed
    (confirmed live). Each product's own page has no clean <h1> (that
    slot holds the site logo on this theme) - the real name is in the
    page <title> ("NAME | Products | Maruni Wood Industry") - and its
    main image lives under a distinct /img/pages/products/{slug}/Product/
    path (not the usual wp-content/uploads used elsewhere on the site),
    so that path is matched specifically rather than grabbing the first
    image on the page (which would pick up nav/logo images instead).
    """
    domain = brand["url"].rstrip("/")
    listing_url = f"{domain}/en/product/"
    try:
        resp = requests.get(listing_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {listing_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    urls = sorted({
        a["href"] for a in soup.find_all("a", href=re.compile(r"^https://www\.maruni\.com/en/product/[a-z0-9_]+/$"))
        # "catalogs" is a downloads page, not a product - it lives at
        # /en/product/catalogs/ (same URL shape as a real product slug)
        # and slipped through this regex during testing (2026-09-13).
        if a["href"].rstrip("/").rsplit("/", 1)[-1] != "catalogs"
    })

    products = []
    brand_start = time.monotonic()
    for url in urls:
        if time.monotonic() - brand_start > MAX_SECONDS_PER_BRAND:
            print(f"  Hit the {MAX_SECONDS_PER_BRAND // 60}-minute safety limit for "
                  f"{brand['name']} - stopping early with what was fetched so far.")
            break
        try:
            presp = requests.get(url, headers=HEADERS, timeout=15)
            presp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        psoup = BeautifulSoup(presp.text, "html.parser")
        title = psoup.find("title")
        if not title:
            continue
        name = title.get_text(strip=True).split("|")[0].strip()
        if not name:
            continue

        img = psoup.find("img", src=re.compile(r"/img/pages/products/[a-z0-9_]+/Product/"))

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": _infer_category_from_name(name, "", brand["name"]),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img.get("src", "") if img else "",
        })
        time.sleep(1)  # be polite - don't hammer the site

    return products


# petitefriture.com (PrestaShop, France) - same "color/size is its own
# top-level product" pattern already handled for moustache.fr, and the
# same "no single category is a true superset" caveat applies (its own
# nav mixes a few pure aggregators - "new arrivals", "archives" - with
# the real per-type categories below, which is why those two aren't
# included here). Category labels are a light-touch translation of the
# French slugs, not an attempt at a full taxonomy.
PETITE_FRITURE_CATEGORIES = {
    "4022-lampes-a-poser": "Table lamp", "4023-appliques": "Wall light",
    "4024-suspensions": "Pendant light", "4095-lampadaires": "Floor lamp",
    "4108-lampes-nomades-et-lampes-exterieures-a-poser": "Outdoor lamp",
    "4136-lampes-d-exterieur": "Outdoor lamp",
    "4030-chaises-et-fauteuils": "Chair", "4031-tables-basses": "Coffee table",
    "4032-tables": "Table", "4147-table-de-bistrot": "Table",
    "4129-bancs-et-tabourets-": "Bench",
    "4034-tables-de-jardin": "Outdoor table", "4035-fauteuils-de-jardin": "Outdoor armchair",
    "4110-bancs-et-canapes-de-jardin": "Outdoor bench",
    "4033-accessoires-de-jardin": "Outdoor accessory",
    "4038-coussins": "Cushion", "4039-arts-de-la-table": "Tableware",
    "4041-miroirs": "Mirror", "4040-accessoires": "Accessory",
}


def extract_petite_friture(brand):
    """
    Each color/size is its own top-level PrestaShop product here too
    (confirmed: "Neotenic" alone has separate product IDs per size and
    colour) - same base pattern as extract_moustache, fold the variant
    text into material_options. Grouped by (category, name), not name
    alone, unlike moustache - confirmed live that the same design line
    here genuinely spans multiple real product types under one shared
    name ("Vertigo Nova" is sold as both a wall light and a floor lamp,
    not just a colour variant of one fixture), so a name-only group
    would silently collapse a floor lamp into whichever category that
    name was first scraped under. The card markup differs from
    moustache's theme too (product name lives in
    <p class="product-title"><a>, not product-miniature-name, and the
    real image is in the lazy-loaded data-src attribute, not src - the
    src itself is just a shared loading spinner placeholder image on
    every card here). Deduped by PrestaShop's own data-id-product,
    stable across whichever category a product is fetched from.
    """
    domain = brand["url"].rstrip("/")
    seen_ids = set()
    raw_products = []

    for category_slug, category_label in PETITE_FRITURE_CATEGORIES.items():
        page = 1
        while page <= MAX_PAGES_PER_BRAND:
            url = f"{domain}/fr/{category_slug}"
            if page > 1:
                url += f"?page={page}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  Could not fetch {url}: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.find_all("article", class_="product-miniature")
            if not articles:
                break

            for article in articles:
                product_id = article.get("data-id-product")
                if not product_id or product_id in seen_ids:
                    continue
                seen_ids.add(product_id)

                title_el = article.find(class_="product-title")
                title_link = title_el.find("a", href=True) if title_el else None
                short_desc = article.find(class_="short-desc")
                img = article.find("img")
                if not title_link:
                    continue

                name = title_link.get_text(strip=True)
                variant = ""
                if short_desc:
                    desc_text = short_desc.get_text(strip=True)
                    if desc_text.lower().startswith(name.lower()):
                        variant = desc_text[len(name):].lstrip(" -").strip()

                raw_products.append({
                    "name": name,
                    "product_url": title_link["href"].split("#")[0],
                    "category": category_label,
                    "variant": variant,
                    "image_url": (img.get("data-src") or img.get("src") or "") if img else "",
                })

            page_links = soup.find_all("a", href=re.compile(r"[?&]page=" + str(page + 1)))
            if not page_links:
                break
            page += 1
            time.sleep(1)  # be polite - don't hammer the site

    # Grouped by (category, name), not name alone - the same design line
    # here genuinely spans multiple real product types (confirmed live:
    # "Vertigo Nova" is sold as both a wall light and a floor lamp, not
    # just a color variant of one fixture), so a name-only group would
    # silently collapse a floor lamp into whichever category that name
    # was first seen under.
    grouped = {}
    for p in raw_products:
        grouped.setdefault((p["category"], p["name"]), []).append(p)

    products = []
    for (category, name), group in grouped.items():
        first = group[0]
        variants = sorted({p["variant"] for p in group if p["variant"]})
        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": first["product_url"],
            "category": category,
            "material_options": variants,
            "dimensions": "",
            "notes": "",
            "image_url": first["image_url"],
        })

    return products


def extract_ay_illuminate(brand):
    """
    ayilluminate.com (Netherlands - "Ay illuminate B.V." per its own
    footer) is WordPress, but not WooCommerce - its actual catalog lives
    under a generic "portfolio" custom-post-type that ALSO holds unrelated
    press-mention posts (e.g. "Elle Decoration", full of Lorem Ipsum
    placeholder text) - confirmed live, so the full wp-sitemap for that
    post type isn't used as the product source. Instead, the site's own
    /authentics/ page (its real "shop the collection" page, given
    directly by the user) links to exactly the 113 real product pages,
    which is used as the product list instead of the noisy full sitemap.
    Each product page is unusually rich for a small brand - real labeled
    Size/Reference/Material/Color fields as plain text, no markup to hang
    a selector on, so they're pulled out by finding each label string and
    taking the text up to the next known label. This page builder (Tatsu)
    lazy-loads every real photo - its `src` is a shared 1x1 base64
    placeholder pixel on every image, including the site logo, and the
    real URL only exists in `data-src` - confirmed live, the page has no
    reliable og:image either. The *first* `data-src` image on a product
    page is a "related item" thumbnail from a suggestions widget (not
    that page's own product), confirmed on Figo (whose first data-src
    was Hozuki's photo) and Topi (same) - the page's own real photo is
    reliably the *last* data-src image instead.
    """
    domain = brand["url"].rstrip("/")
    listing_url = f"{domain}/authentics/"
    try:
        resp = requests.get(listing_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {listing_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    urls = sorted({
        a["href"] for a in soup.find_all("a", href=re.compile(r"^https://www\.ayilluminate\.com/portfolio/[a-z0-9-]+/$"))
    })

    label_order = ["Size", "Reference", "Material", "Color", "Available sizes", "Fitting size"]

    def _labeled_fields(text):
        # For the last label in label_order, the joined lookahead
        # alternation used to come out empty ("Fitting size:\s*(.*?)
        # (?=|$)") - an empty alternative in a regex matches
        # immediately at zero width, so the lazy .*? always stopped
        # having consumed nothing and "Fitting size" silently came back
        # blank on every real product (confirmed live 2026-09-21: every
        # page's own text clearly has "Fitting size: E-27 Max. 60
        # WATT", but this always parsed to ""). Each product page
        # reliably repeats the same labels a second time afterward
        # (with the values shifted, likely a duplicate responsive
        # layout), immediately followed by "BACK TO AUTHENTICS" - used
        # as the stop marker for the one label with nothing after it.
        fields = {}
        for i, label in enumerate(label_order):
            next_labels = label_order[i + 1:]
            lookahead = "|".join(re.escape(l) + ":" for l in next_labels) if next_labels else "BACK TO AUTHENTICS"
            pattern = re.escape(label) + r":\s*(.*?)(?=" + lookahead + r"|$)"
            m = re.search(pattern, text, re.S)
            if m:
                fields[label] = m.group(1).strip(" \n\t-")
        return fields

    products = []
    brand_start = time.monotonic()
    for url in urls:
        if time.monotonic() - brand_start > MAX_SECONDS_PER_BRAND:
            print(f"  Hit the {MAX_SECONDS_PER_BRAND // 60}-minute safety limit for "
                  f"{brand['name']} - stopping early with what was fetched so far.")
            break
        try:
            presp = requests.get(url, headers=HEADERS, timeout=15)
            presp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        psoup = BeautifulSoup(presp.text, "html.parser")
        title = psoup.find("title")
        if not title:
            continue
        name = title.get_text(strip=True).split("&#8211;")[0].split("–")[0].strip()
        if not name:
            continue

        text = psoup.get_text(" ", strip=True)
        fields = _labeled_fields(text)
        materials = [m.strip() for m in re.split(r",|/", fields.get("Material", "")) if m.strip()]

        imgs = psoup.find_all("img", attrs={"data-src": re.compile(r"wp-content/uploads/")})
        img = imgs[-1] if imgs else None

        # Names are almost entirely evocative (Figo, Hozuki, Z1 Black...)
        # with no lighting word to match - but every real lamp's own
        # page carries a real "Fitting size" (e.g. "E-27 Max. 60 WATT"),
        # confirmed absent on the one non-lamp item in this catalog
        # ("Poffer Cushion," a woven rush seat cushion, only 3cm tall -
        # no light fitting at all). That field is a far more reliable
        # signal here than the name. Mount type (table/wall) is still
        # named explicitly on the few pieces that have one ("Twiggy AW
        # Table", "Pebble white wall") - defaults to Pendant otherwise,
        # since every fitted piece checked live is a hanging fixture.
        name_lower = name.lower()
        if fields.get("Fitting size"):
            if "table" in name_lower:
                category = "Table Lamp"
            elif "wall" in name_lower:
                category = "Wall Lamp"
            else:
                category = "Pendant"
        else:
            category = _infer_category_from_name(name, "", brand["name"])

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": category,
            "material_options": materials,
            "dimensions": fields.get("Size", ""),
            "notes": "",
            "image_url": img.get("data-src", "") if img else "",
        })
        time.sleep(1)  # be polite - don't hammer the site

    return products


# Real work items on kinandcompany.com's /work page, filtered out of the
# full link list (confirmed live) because they aren't sellable pieces:
# project write-ups, sample-sale/press posts, and material-process
# essays sit in the same /work/ URL space as the actual furniture pieces.
KIN_AND_CO_EXCLUDED_SLUGS = {
    "concept-house", "fabrication", "inside-out", "sample-sale",
    "wallpaper-projects", "material-leading-design-at-vsop-projects",
}


def extract_kin_and_co(brand):
    """
    kinandcompany.com runs GravCMS (a flat-file, fully server-rendered
    CMS - no JS needed for content) with no robots.txt restrictions.
    Every real piece and non-piece entry alike lives under /work/slug -
    KIN_AND_CO_EXCLUDED_SLUGS drops the ones confirmed to be projects/
    press/process writeups rather than actual designed objects, the same
    "brand's own listing mixes non-product entries" situation handled
    per-brand elsewhere in this file (e.g. Piet Hein Eek's excluded
    categories).
    """
    domain = brand["url"].rstrip("/")
    listing_url = f"{domain}/work"
    try:
        resp = requests.get(listing_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch {listing_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    slugs = sorted({
        a["href"].rsplit("/", 1)[-1]
        for a in soup.find_all("a", href=re.compile(r"^/work/[a-zA-Z0-9_-]+$"))
    } - KIN_AND_CO_EXCLUDED_SLUGS)

    products = []
    brand_start = time.monotonic()
    for slug in slugs:
        if time.monotonic() - brand_start > MAX_SECONDS_PER_BRAND:
            print(f"  Hit the {MAX_SECONDS_PER_BRAND // 60}-minute safety limit for "
                  f"{brand['name']} - stopping early with what was fetched so far.")
            break
        url = f"{domain}/work/{slug}"
        try:
            presp = requests.get(url, headers=HEADERS, timeout=15)
            presp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        psoup = BeautifulSoup(presp.text, "html.parser")
        title = psoup.find("title")
        if not title:
            continue
        name = title.get_text(strip=True).split("|")[0].strip()
        if not name:
            continue

        img = psoup.find("img", src=re.compile(r"/user/pages/01\.work/"))
        img_src = img.get("src", "") if img else ""
        if img_src.startswith("/"):
            img_src = f"{domain}{img_src}"

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": _infer_category_from_name(name, "", brand["name"]),
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img_src,
        })
        time.sleep(1)  # be polite - don't hammer the site

    return products


# The real catalog on studiobseverin.com is 6 named design pieces linked
# directly from the homepage, each its own single-page writeup (Cargo
# CMS, server-rendered, real prose) rather than a shop with individual
# SKUs - same "index at the coarser real level" exception used for Paola
# Paronetto. Hardcoded rather than crawled since the homepage nav mixes
# these in with WORK/ABOUT/CONTACT/SHOP navigation links with no shared
# structural marker to filter on.
BIRGIT_SEVERIN_PIECES = ["ALTERATION", "ASHES", "DESIGN-IMPRESSIONISM-1", "HEIMAT", "KIREI", "VANITAS"]


def extract_birgit_severin(brand):
    """
    studiobseverin.com's robots.txt (Crawl-delay: 2, User-agent: * Allow:
    /) only blocks a list of generic SEO/scraper bots by name (rogerbot,
    dotbot, MJ12bot, Semrush variants, etc.) - no AI-crawler exclusion,
    unlike bocci.com/brdr-kruger.com's Cloudflare-managed robots.txt.
    Crawl-delay honored via the standard 1s politeness sleep between
    fetches (already well above 2s given there are only 6 pages here).
    """
    domain = brand["url"].rstrip("/")
    products = []
    for slug in BIRGIT_SEVERIN_PIECES:
        url = f"{domain}/{slug}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        og_image = soup.find("meta", property="og:image")

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": slug.replace("-1", "").replace("-", " ").title(),
            "product_url": url,
            "category": "",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": og_image.get("content", "") if og_image else "",
        })
        time.sleep(2)  # Crawl-delay: 2 in this site's own robots.txt

    return products


def extract_shibui(brand):
    """
    shibui.ch is Wix, whose storefront is normally too
    client-rendered to scrape - but Wix Stores publishes a real
    store-products-sitemap.xml regardless (confirmed live: 12 products),
    and each product page itself is server-rendered with the real name,
    price, and description present in the initial HTML (Wix hydrates
    onto existing markup rather than injecting it from nothing). Small
    catalog - genuinely a small studio, not a sign anything was missed.
    """
    domain = brand["url"].rstrip("/")
    try:
        resp = requests.get(f"{domain}/store-products-sitemap.xml", headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Could not fetch product sitemap for {brand['name']}: {e}")
        return []

    urls = re.findall(r"<loc>([^<]+)</loc>", resp.text)

    products = []
    for url in urls:
        try:
            presp = requests.get(url, headers=HEADERS, timeout=15)
            presp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Could not fetch {url}: {e}")
            continue

        psoup = BeautifulSoup(presp.text, "html.parser")
        title_el = psoup.find(attrs={"data-hook": "product-title"})
        og_image = psoup.find("meta", property="og:image")
        if not title_el:
            continue

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": title_el.get_text(strip=True),
            "product_url": url,
            "category": "",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": og_image.get("content", "") if og_image else "",
        })
        time.sleep(1)  # be polite - don't hammer the site

    return products


# ghidini1961.com/shop (Italy - Ghidini Giuseppe Bosco S.p.A, Via Gabriele
# D'Annunzio 27, 25069 Villa Carcina (BS), confirmed via its own product
# page footer). PrestaShop, but a different theme than moustache.fr/
# petitefriture.com - no robots.txt restrictions and no page has ever
# 404'd. 3 of the site's 11 shop categories (Lighting, Complements,
# Furniture Accessories) consistently render zero product cards despite
# returning 200 and the same page shell - a real caching quirk on the
# site's own end (a plain re-fetch of the exact same URL, no header
# changes, reliably returns the real cards the second time), not a bot
# block - confirmed by re-fetching one of the three ~10 times in a row
# and seeing it flip from empty to populated with nothing about the
# request changed. GHIDINI_CATEGORIES is every category found in the
# site's own nav; each is retried once after a short pause if the first
# fetch comes back with no cards at all, rather than trusting a single
# empty result.
GHIDINI_CATEGORIES = [
    "13-brass-lamps", "14-chairs-ottoman", "15-brass-tables", "16-brass-complements",
    "17-brass-furniture-accessories", "18-cabinets-bookshelves", "19-art-pieces",
    "20-sofas", "21-armchairs", "22-night-collections", "23-rugs",
]

# The category this brand's own site already sorts each product into
# (the slug is right there in GHIDINI_CATEGORIES/each product's own
# URL) was being fetched and then thrown away - only used as a crawl
# target, never stored as this project's own category field. Used only
# as a fallback here, since most real names already carry a specific
# object-type word the shared English keyword list resolves more
# precisely (e.g. "Frame Bed" -> Bed, not the coarser "Night
# Collections" -> Bed a name-less fallback would give it) - confirmed
# live 2026-09-21: only 11 of 133 products needed this fallback at all.
GHIDINI_CATEGORY_LABELS = {
    "13-brass-lamps": "Lamp", "14-chairs-ottoman": "Chair", "15-brass-tables": "Table",
    "16-brass-complements": "Accessories", "17-brass-furniture-accessories": "Accessories",
    "18-cabinets-bookshelves": "Cabinet", "19-art-pieces": "Sculpture", "20-sofas": "Sofa",
    "21-armchairs": "Armchair", "22-night-collections": "Bed", "23-rugs": "Rug",
}


def extract_ghidini_1961(brand):
    """
    Every product's real name, designer, image, and page link are already
    on each category's own listing page (<div class="prodotto"> ->
    <p class="nomargin"><a><strong>Name</strong></a></p> for the name,
    the very next <p class="center"> sibling for the designer, and the
    image's data-src, not its placeholder src) - no per-product fetch
    needed, same shape as extract_galerie_kreo. Product pages themselves
    were checked and don't carry a clean numeric "Dimensions:" field (just
    a long prose "Technical Features" section plus a huge shared finish/
    upholstery swatch list, not real per-item material_options), so
    dimensions/materials are left blank rather than fetching 133 extra
    pages for data that isn't there. Deduped by product URL since a piece
    can be cross-listed in more than one category (e.g. Night Collections
    overlaps with Armchairs/Sofas).
    """
    domain = brand["url"].rstrip("/")
    seen_urls = set()
    products = []

    for category_slug in GHIDINI_CATEGORIES:
        url = f"{domain}/shop/en/{category_slug}"
        cards = []
        for attempt in range(2):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  Could not fetch {url}: {e}")
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="prodotto")
            if cards:
                break
            time.sleep(2)  # real cards sometimes only show up on a re-fetch - see docstring

        for card in cards:
            name_p = card.find("p", class_="nomargin")
            name_link = name_p.find("a", href=True) if name_p else None
            if not name_link or name_link["href"] in seen_urls:
                continue
            seen_urls.add(name_link["href"])

            designer_p = name_p.find_next_sibling("p", class_="center")
            img = card.find("img")
            name = name_link.get_text(strip=True)
            category = (
                _infer_category_from_name(name, "", brand["name"])
                or GHIDINI_CATEGORY_LABELS.get(category_slug, "")
            )

            products.append({
                "brand": brand["name"],
                "brand_url": brand["url"],
                "product_name": name,
                "product_url": name_link["href"],
                "category": category,
                "material_options": [],
                "dimensions": "",
                "notes": "",
                "image_url": img.get("data-src", "") if img else "",
            })

        time.sleep(1)  # be polite - don't hammer the site

    return products


# Map brand name -> extractor function. Add new brands here as extractors
# get built for them.
EXTRACTORS = {
    "Kieran Kinsella": extract_kieran_kinsella,
    "H. Bigeleisen": extract_hbigeleisen,
    "Yird Ceramics": extract_yird_ceramics,
    "Ingo Maurer": extract_ingo_maurer,
    "Källemo": extract_kallemo,
    "Joris Poggioli": extract_joris_poggioli,
    "Moustache": extract_moustache,
    "Baleri Italia": extract_baleri_italia,
    "Paola Paronetto": extract_paola_paronetto,
    "Minimalux": extract_shopify,
    "Pinch": extract_shopify,
    "Bitossi Ceramiche": extract_shopify,
    "GATOMIKIO": extract_shopify,
    "101cph": extract_shopify,
    "In Common With": extract_shopify,
    "Anna Löwenhielm Ceramics": extract_shopify,
    "A. Petersen": extract_shopify,
    "De La Espada": extract_shopify,
    "Luke Hope": extract_shopify,
    "Buro Berger": extract_shopify,
    "Silcohaus": extract_shopify,
    "Designbythem": extract_shopify,
    "Raawii": extract_shopify,
    "Utilitario Mexicano": extract_shopify,
    "Galvin Brothers": extract_shopify,
    "Verk": extract_woocommerce,
    "Another Country": extract_woocommerce,
    "Piet Hein Eek": extract_woocommerce,
    "Mati Sipiora": extract_woocommerce,
    "Patrick de Glo de Besses": extract_bigcartel,
    "B-Line Italia": extract_bline,
    "Omelette Editions": extract_omelette_editions,
    "Par en Par": extract_parenpar_ar,
    "Łukasz Korol": extract_shopify,
    "Eric Schmitt Studio": extract_eric_schmitt,
    "New Works DK": extract_new_works_dk,
    "Eine Kleine Furniture": extract_eine_kleine_furniture,
    "Jon Goulder": extract_jon_goulder,
    "La Chambre d'Ami": extract_la_chambre_dami,
    "Esther Knopfler": extract_esther_knopfler,
    "Mercoeur Editions": extract_mercoeur_editions,
    "Oven Editions": extract_shopify,
    "Mass Productions": extract_shopify,
    "Joy Objects": extract_shopify,
    "Wästberg": extract_wastberg,
    "Pulkra": extract_woocommerce,
    "Sé Collections": extract_se_collections,
    "Gubi": extract_gubi,
    "Magis": extract_magis,
    "Grain": extract_grain,
    "Will Choui": extract_will_choui,
    "Sizar Alexis": extract_sizar_alexis,
    "Monsieur Cailloux": extract_monsieur_cailloux,
    "Jonas Lindholm": extract_woocommerce,
    "Northern": extract_shopify,
    "Louise Roe": extract_shopify,
    "Tolix": extract_shopify,
    "Rubn": extract_shopify,
    "Apparatus": extract_shopify,
    "Wendelbo": extract_shopify,
    "Pholc": extract_shopify,
    "Mater": extract_shopify,
    "Mabeo Furniture": extract_woocommerce,
    "Editions Midi": extract_woocommerce,
    "Established & Sons": extract_established_and_sons,
    "Galerie Kreo": extract_galerie_kreo,
    "Workstead": extract_workstead,
    "Maruni": extract_maruni,
    "Petite Friture": extract_petite_friture,
    "AY Illuminate": extract_ay_illuminate,
    "Kin and Co": extract_kin_and_co,
    "Birgit Severin": extract_birgit_severin,
    "Shibui": extract_shibui,
    "Ghidini 1961": extract_ghidini_1961,
}


def _scrape_one_brand(brand, extractor):
    """
    Runs in a worker thread (see run()) - touches no shared state, only
    returns what it found, so the database write itself (not thread-safe
    across concurrent SQLite connections/writers) can stay serialized on
    the main thread. Almost all of a real extractor's time is spent
    waiting on that one brand's own HTTP responses, which is exactly the
    kind of work threads parallelize well in Python despite the GIL (the
    GIL releases during I/O waits).
    """
    print(f"Scraping {brand['name']}...")
    brand_start = time.monotonic()
    try:
        products = extractor(brand)
    except Exception as e:
        return brand, None, round(time.monotonic() - brand_start, 1), str(e)
    return brand, products, round(time.monotonic() - brand_start, 1), None


def run(brand_name=None):
    """
    brand_name: if given, scrapes only that one brand (case-insensitive
    exact match) instead of the full catalog - for testing/adding a
    single new brand locally without waiting on the ~5-minute full run
    (dominated by In Common With's pagination), without needing to skip
    any of the same per-brand delete-then-insert/safety-limit logic.

    Scrapes up to MAX_CONCURRENT_BRANDS brands at once (see that
    constant's own comment) - the old fully-sequential version meant one
    slow brand delayed every brand listed after it, and at a few hundred
    brands that stopped being a rounding error and started silently
    starving brands late in brands.json of ever running within
    MAX_TOTAL_RUNTIME_SECONDS. Database writes stay on this one thread
    regardless, in whatever order each brand's scrape actually finishes -
    SQLite isn't safe for concurrent writers, and the write itself is
    fast; it's the network I/O inside each extractor that parallelizing
    here actually speeds up.
    """
    with open(BRANDS_PATH) as f:
        brands = json.load(f)

    if brand_name:
        brands = [b for b in brands if b["name"].lower() == brand_name.lower()]
        if not brands:
            print(f"No brand named '{brand_name}' found in {BRANDS_PATH}.")
            return

    conn = setup_database()
    start_time = time.monotonic()

    # Per-brand timing/counts, kept for the resource-effectiveness summary
    # printed and saved at the end - this is what would have made the
    # ~149-hour runaway-scrape incident visible immediately instead of only
    # after the fact.
    brand_reports = []
    stopped_early = False

    runnable = []
    for brand in brands:
        if not brand.get("scrapable", True):
            print(f"Skipping {brand['name']} - marked not scrapable ({brand.get('notes', '')})")
            continue
        extractor = EXTRACTORS.get(brand["name"])
        if not extractor:
            print(f"No extractor built yet for {brand['name']} - skipping for now.")
            continue
        runnable.append((brand, extractor))

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BRANDS) as pool:
        futures = []
        for brand, extractor in runnable:
            if time.monotonic() - start_time > MAX_TOTAL_RUNTIME_SECONDS:
                print(f"Hit the {MAX_TOTAL_RUNTIME_SECONDS // 60}-minute total run time limit before "
                      f"starting {brand['name']} - stopping here. Remaining brands will just run "
                      f"next scheduled scrape.")
                stopped_early = True
                break
            futures.append(pool.submit(_scrape_one_brand, brand, extractor))

        for future in concurrent.futures.as_completed(futures):
            brand, products, brand_seconds, error = future.result()

            if error:
                print(f"  Error scraping {brand['name']}: {error}")
                brand_reports.append({
                    "brand": brand["name"], "products_saved": 0,
                    "seconds": brand_seconds, "error": error,
                })
                continue

            if not products:
                # A brand's extractor succeeding but returning nothing is more
                # likely a transient scrape hiccup (site hiccup, layout change)
                # than the brand genuinely having zero products - don't wipe
                # its existing good data over that; a real "brand pulled every
                # product" case gets caught the next run this keeps returning 0.
                print(f"  Got 0 products for {brand['name']} - keeping previous data, not overwriting.")
                brand_reports.append({
                    "brand": brand["name"], "products_saved": 0,
                    "seconds": brand_seconds, "error": "0 products returned - kept previous data",
                })
                continue

            # Carry each product's real first_seen forward across the
            # delete-then-insert below, keyed by product_url (the one
            # stable identifier across scrapes) - captured *before* the
            # delete, since the old row (and its real date) is gone the
            # moment that runs. A url missing from this mapping is
            # genuinely new to this brand since the last scrape and gets
            # today's date; a url present keeps whatever it already had,
            # including NULL (a pre-existing product with an unknown real
            # add-date must never be re-stamped as "new today").
            old_first_seen = dict(conn.execute(
                "SELECT product_url, first_seen FROM products WHERE brand = ?",
                (brand["name"],),
            ).fetchall())
            today = datetime.date.today().isoformat()

            # Replace this brand's rows wholesale rather than appending -
            # otherwise a product still live gets re-inserted as a duplicate
            # every run, and a product genuinely removed from the brand's site
            # (see the Luke Hope "tanned walnut" paddle, 2026-09-09) never gets
            # cleared since nothing ever deletes old rows. Scoped to one brand
            # at a time (not a full-table wipe) so a mid-run stop leaves
            # brands not yet reached untouched.
            conn.execute("DELETE FROM products WHERE brand = ?", (brand["name"],))
            conn.commit()
            for product in products:
                url = product["product_url"]
                product["first_seen"] = old_first_seen[url] if url in old_first_seen else today
                override = MANUAL_CATEGORY_OVERRIDES.get((brand["name"], product["product_name"]))
                if override:
                    product["category"] = override
                save_product(conn, product)
            print(f"  Saved {len(products)} products in {brand_seconds}s.")
            brand_reports.append({
                "brand": brand["name"], "products_saved": len(products),
                "seconds": brand_seconds, "error": None,
            })

    conn.close()
    total_seconds = round(time.monotonic() - start_time, 1)
    print_summary(brand_reports, total_seconds, stopped_early)
    print("Done.")


def print_summary(brand_reports, total_seconds, stopped_early):
    """
    Resource-effectiveness summary: how long the run took overall and per
    brand, and total products saved - printed to the console (visible in
    the GitHub Actions log) and saved to data/last_scrape_report.json so
    it's checkable after the fact without having to catch it live. This is
    the visibility that would have surfaced the ~149-hour runaway-scrape
    incident immediately instead of only after the fact.
    """
    total_products = sum(b["products_saved"] for b in brand_reports)
    slowest = sorted(brand_reports, key=lambda b: b["seconds"], reverse=True)[:3]
    errors = [b for b in brand_reports if b["error"]]

    print("\n--- Run summary ---")
    print(f"Total time: {total_seconds}s ({total_seconds / 60:.1f} min)")
    print(f"Total products saved: {total_products} across {len(brand_reports)} brands")
    if stopped_early:
        print("NOTE: stopped early due to the total-runtime safety limit - not all brands ran.")
    if slowest:
        print("Slowest brands: " + ", ".join(f"{b['brand']} ({b['seconds']}s)" for b in slowest))
    if errors:
        print("Brands with errors: " + ", ".join(b["brand"] for b in errors))

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_seconds": total_seconds,
        "total_products_saved": total_products,
        "stopped_early_due_to_time_limit": stopped_early,
        "brands": brand_reports,
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--brand", default=None,
        help="Scrape only this one brand (exact name from brands.json), instead of the full catalog.",
    )
    args = parser.parse_args()
    run(brand_name=args.brand)
