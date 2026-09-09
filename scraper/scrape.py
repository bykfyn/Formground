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
# fisici" (Bitossi's actual physical books). Checked against each
# brand's real category breakdown before adding - e.g. Bitossi's
# "Designers" category was NOT added here despite sounding similarly
# suspicious, because its actual products (Vaso, Bolo) are real ceramic
# pieces just organized by which designer made them.
EXCLUDED_CATEGORIES = {
    "finish samples", "swatches", "spare part", "spare parts", "libri fisici",
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
    # English.
    raw_products = [p for p in raw_products if re.search(r"[A-Za-z]", p["title"])]

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
            "notes": f"{len(group)} variants" if len(group) > 1 else "",
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
            "notes": f"{len(group)} variants" if len(group) > 1 else "",
            "image_url": image_url,
        })

    return products


# Map brand name -> extractor function. Add new brands here as extractors
# get built for them.
EXTRACTORS = {
    "Kieran Kinsella": extract_kieran_kinsella,
    "H. Bigeleisen": extract_hbigeleisen,
    "Yird Ceramics": extract_yird_ceramics,
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
    "Luke Hope": extract_shopify,
    "Verk": extract_woocommerce,
    "Another Country": extract_woocommerce,
}


def run():
    with open(BRANDS_PATH) as f:
        brands = json.load(f)

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
    run()
