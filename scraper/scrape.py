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
            last_checked TEXT
        )
    """)
    # ALTER TABLE ADD COLUMN fails if the column already exists - this only
    # matters for a database created before these columns existed, so it's
    # safe to ignore that specific failure.
    for statement in (
        "ALTER TABLE products ADD COLUMN thin INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN image_url TEXT",
        "ALTER TABLE products ADD COLUMN designer TEXT",
        "ALTER TABLE products ADD COLUMN link_dead INTEGER DEFAULT 0",
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
    """
    conn.execute("""
        INSERT INTO products (brand, brand_url, product_name, product_url,
                               category, material_options, dimensions, notes, thin, image_url, designer, last_checked)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
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
            "category": "",
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
    separate-product problem.
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


def _infer_category_from_name(product_name, current_category):
    if current_category.strip().lower() not in UNHELPFUL_CATEGORIES:
        return current_category
    first_word = product_name.strip().split(" ")[0].lower().rstrip(",.")
    return ITALIAN_OBJECT_TYPES.get(first_word, current_category)


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
    """
    title = re.sub(r"<br\s*/?>", " ", title)
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
    raw_products = [
        p for p in raw_products
        if (p.get("product_type") or "").strip().lower() not in EXCLUDED_CATEGORIES
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
            "category": _infer_category_from_name(base_name, product_type),
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

        url = f"{base}/wp-json/wc/store/v1/products?per_page=100&page={page}"
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

    raw_products = [
        p for p in raw_products
        if not any(c["name"].strip().lower() in EXCLUDED_CATEGORIES for c in p.get("categories", []))
    ]

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
        # item - covers the same inconsistent-tagging case above.
        categories = sorted({c["name"] for p in group for c in p.get("categories", [])})
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
            "category": "",
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
            "category": "",
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
    og:title/og:image are server-rendered and reliable.
    """
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

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": url,
            "category": category,
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": og_image["content"] if og_image and og_image.get("content") else "",
        })
        time.sleep(0.5)  # be polite - don't hammer the site

    return products


def extract_mercoeur_editions(brand):
    """
    mercoeur-edition.com (Webflow) server-renders its full 18-item catalog
    on one /all-products listing page - name, link, and image for every
    product in one fetch, no per-product pages needed. No reliable category
    signal (slug and display-name word order don't agree, e.g.
    /products/boxes-ondine is titled "Ondine Set of 3 boxes"), left blank -
    same tradeoff as B-Line Italia/H. Bigeleisen.
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
        name = a.get_text(strip=True)
        if not img or not name:
            continue

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": f"{domain}{a['href']}" if a["href"].startswith("/") else a["href"],
            "category": "",
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
    and mount type ("TABLE") - combined as the display name, and the mount
    type doubles as category (Ceiling/Pendant/Wall/Floor/Table/Track/
    Accessories - all real distinctions for a lighting-only brand, same
    "hardcode the one category" precedent as Ingo Maurer). The listing
    page's own thumbnail isn't reliably paired per-product (a shared
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

        base_key = re.sub(r"-w\d+[a-z0-9]*$", "", slug)
        image_url = ""
        img = page_soup.find("img", src=re.compile(rf"/pim/.*{re.escape(base_key)}", re.IGNORECASE))
        if img:
            image_url = img["src"]
            if image_url.startswith("/"):
                image_url = f"{domain}{image_url}"

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": name,
            "product_url": product_url,
            "category": mount_type.title(),
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


def extract_magis(brand):
    """
    magisdesign.com (WordPress) server-renders its entire ~250-item catalog
    on one /product/ listing page - name (h2), designer + price (p), and
    image all inline per card (a.load), no per-product fetch needed. No
    per-product category (the site's own taxonomy is by function - chairs,
    tables, etc. - as separate landing pages under /function/, not tagged
    per item on this listing), left blank.
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
    for a in soup.find_all("a", class_="load", href=True):
        h2 = a.find("h2")
        img = a.find("img")
        if not h2 or not img:
            continue

        products.append({
            "brand": brand["name"],
            "brand_url": brand["url"],
            "product_name": h2.get_text(strip=True),
            "product_url": a["href"],
            "category": "",
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
    grid, $1 each - not design objects) since there's no separate category
    field to filter on generically.
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
        if not name or "sample" in name.lower():
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
            "category": "",
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
                "category": "",
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
                "category": "",
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
    ceramics practice. No per-piece category (the site's own categories
    are color swatches - /category/white, /category/black, etc - not
    object types), left blank.
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
            "category": "",
            "material_options": [],
            "dimensions": "",
            "notes": "",
            "image_url": img.get("src", "") if img else "",
        })

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
}


def run(brand_name=None):
    """
    brand_name: if given, scrapes only that one brand (case-insensitive
    exact match) instead of the full catalog - for testing/adding a
    single new brand locally without waiting on the ~5-minute full run
    (dominated by In Common With's pagination), without needing to skip
    any of the same per-brand delete-then-insert/safety-limit logic.
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

    for brand in brands:
        elapsed = time.monotonic() - start_time
        if elapsed > MAX_TOTAL_RUNTIME_SECONDS:
            print(f"Hit the {MAX_TOTAL_RUNTIME_SECONDS // 60}-minute total run time limit - "
                  f"stopping here. Remaining brands will just run next scheduled scrape.")
            stopped_early = True
            break

        if not brand.get("scrapable", True):
            print(f"Skipping {brand['name']} - marked not scrapable ({brand.get('notes', '')})")
            continue

        extractor = EXTRACTORS.get(brand["name"])
        if not extractor:
            print(f"No extractor built yet for {brand['name']} - skipping for now.")
            continue

        print(f"Scraping {brand['name']}...")
        brand_start = time.monotonic()
        try:
            products = extractor(brand)
        except Exception as e:
            print(f"  Error scraping {brand['name']}: {e}")
            brand_reports.append({
                "brand": brand["name"], "products_saved": 0,
                "seconds": round(time.monotonic() - brand_start, 1), "error": str(e),
            })
            continue

        if not products:
            # A brand's extractor succeeding but returning nothing is more
            # likely a transient scrape hiccup (site hiccup, layout change)
            # than the brand genuinely having zero products - don't wipe
            # its existing good data over that; a real "brand pulled every
            # product" case gets caught the next run this keeps returning 0.
            brand_seconds = round(time.monotonic() - brand_start, 1)
            print(f"  Got 0 products for {brand['name']} - keeping previous data, not overwriting.")
            brand_reports.append({
                "brand": brand["name"], "products_saved": 0,
                "seconds": brand_seconds, "error": "0 products returned - kept previous data",
            })
            continue

        # Replace this brand's rows wholesale rather than appending -
        # otherwise a product still live gets re-inserted as a duplicate
        # every run, and a product genuinely removed from the brand's site
        # (see the Luke Hope "tanned walnut" paddle, 2026-09-09) never gets
        # cleared since nothing ever deletes old rows. Scoped to one brand
        # at a time (not a full-table wipe) so a mid-run stop from
        # MAX_TOTAL_RUNTIME_SECONDS leaves brands not yet reached untouched.
        conn.execute("DELETE FROM products WHERE brand = ?", (brand["name"],))
        conn.commit()
        for product in products:
            save_product(conn, product)
        brand_seconds = round(time.monotonic() - brand_start, 1)
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
