"""One-off backfill of products.released_at (the maker's own date for a piece) for the catalog already in the
database. Re-runs the generic Shopify / WooCommerce extractors per brand - the same JSON fetches the weekly
scrape makes, nothing else - and writes ONLY released_at, matched on product_url. Brands on other extractors
have no maker date to read and stay NULL. Dry run unless --apply.

    python3 backfill_released_at.py --apply [--only "101cph"]
"""
import argparse
import json
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape  # noqa: E402

DB = Path(__file__).resolve().parent.parent / "data" / "formground.db"
GENERIC = (scrape.extract_shopify, scrape.extract_woocommerce)


def dates_for(brand):
    try:
        products = scrape.EXTRACTORS[brand["name"]](brand)
    except Exception as e:  # one brand failing must not stop the rest
        return brand["name"], None, str(e)[:80]
    return brand["name"], {p["product_url"]: p["released_at"] for p in products if p.get("released_at")}, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    brands = [b for b in json.loads(scrape.BRANDS_PATH.read_text())
              if b.get("scrapable", True) and scrape.EXTRACTORS.get(b["name"]) in GENERIC
              and (not args.only or b["name"].lower() == args.only.lower())]
    print(f"{len(brands)} brands on the Shopify / WooCommerce extractors")
    conn = sqlite3.connect(DB)
    t0 = time.time()
    total_rows = total_dated = 0
    with ThreadPoolExecutor(args.workers) as ex:
        for fut in as_completed([ex.submit(dates_for, b) for b in brands]):
            name, dates, err = fut.result()
            if dates is None:
                print(f"  {name}: FAILED {err}")
                continue
            rows = conn.execute("SELECT id, product_url FROM products WHERE brand=?", (name,)).fetchall()
            hit = [(dates[u], i) for i, u in rows if u in dates]
            total_rows += len(rows)
            total_dated += len(hit)
            if args.apply:
                conn.executemany("UPDATE products SET released_at=? WHERE id=?", hit)
                conn.commit()
            print(f"  {name}: {len(hit)}/{len(rows)} dated  ({time.time() - t0:.0f}s)")
    print(f"{total_dated} of {total_rows} pieces dated" + ("" if args.apply else " (dry run - nothing written)"))


if __name__ == "__main__":
    main()
