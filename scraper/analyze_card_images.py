"""
Measures the photos of one product type so its cards can show off-square studio shots whole (see image_fit.fit_for_card).

    python3 scraper/analyze_card_images.py table-lamps      # slug from generate_browse_pages.CATEGORIES
    python3 scraper/analyze_card_images.py --all            # every browse type (slow)
    python3 scraper/analyze_card_images.py --brand Tecta    # every photo of one brand (its maker page cards)

Results go to data/image_fit.json (cached: only new photos are fetched). Photos are measured at card size, 8 at a time.
"""

import concurrent.futures
import sys

import generate_browse_pages as gb
import image_fit
from image_sizes import CARD, sized


def analyze_type(category):
    urls = sorted({p["image_url"] for p in gb._category_products(category) if p.get("image_url")})
    measure(category["slug"], urls)


def analyze_brand(brand):
    import sqlite3
    db = sqlite3.connect(image_fit.CACHE_PATH.parent / "formground.db")
    urls = sorted({r[0] for r in db.execute("SELECT image_url FROM products WHERE brand = ? AND image_url != ''", (brand,))})
    measure(brand, urls)


def measure(label, urls):
    cache = image_fit._load()
    # measure what is missing; also redo flat-edged entries made before subject boxes existed
    todo = [u for u in urls if u not in cache or ("box" not in cache[u] and cache[u]["edge_std"] <= image_fit.FLAT_EDGE_MAX)]
    for u in todo:
        cache.pop(u, None)
    print(f"{label}: {len(urls)} photos, {len(todo)} to measure")
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda u: image_fit.analyze(u, fetch_url=sized(u, CARD)), todo))
    cache = image_fit._load()
    fitted = sum(1 for u in urls if image_fit.fit_for_card(u)[0])
    print(f"  shown whole: {fitted} of {len(urls)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--brand"] and len(args) > 1:
        for b in args[1:]:
            analyze_brand(b)
        sys.exit(0)
    cats = gb.BROWSE_CATEGORIES if args == ["--all"] else [c for c in gb.BROWSE_CATEGORIES if c["slug"] in args]
    if not cats:
        sys.exit("give a type slug (e.g. table-lamps) or --all")
    for c in cats:
        analyze_type(c)
