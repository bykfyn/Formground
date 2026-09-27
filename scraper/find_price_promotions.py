"""
Finds real, live product-level discounts already sitting in the database
for the Promotions feature (see data/promotions.json and project memory
search_load_more_design.md's sibling doc, monetization notes) - without
visiting any site by hand.

WHY THIS WORKS WITHOUT NEW SCRAPING:
  extract_shopify() and extract_woocommerce() in scrape.py already fetch
  each variant's original price alongside any discounted price on every
  regular catalog scrape (Shopify's compare_at_price, WooCommerce's
  regular_price/sale_price) - added 2026-09-27. That data was always in
  the raw JSON those extractors pull; it just wasn't stored before now.
  This script is nothing more than a query over the products table for
  rows where compare_at_price is genuinely higher than price - real,
  live discounts, straight from each brand's own site, no retailer
  intermediary needed. This is the one detection method that can reach
  Formground's own small/independent makers, not just brands big enough
  to be carried by a multi-brand boutique.

WHAT THIS CANNOT DO / WHY IT'S A CANDIDATE LIST, NOT AN AUTO-PUBLISH:
  - Only covers brands on extract_shopify/extract_woocommerce (most of
    the catalog, but not the bespoke-extractor minority) - see each
    function's own price-extraction helper for exactly what's captured.
  - compare_at_price can be stale on some real Shopify stores (set once,
    never cleared even after a genuine permanent price change) - a
    confirmed live discount today is still worth a human's one-glance
    sanity check (does the product page itself show it as on sale right
    now?) before it goes in data/promotions.json.
  - Different colorways/sizes of the same design often end up as
    separate rows here (see MATERIAL_OPTIONS/_base_name grouping quirks
    per-brand) - if several near-identical entries from the same brand
    show up together, that's usually one real design on sale across its
    whole range, not several distinct promotions; pick one representative
    rather than adding a card per colorway.
  - Shopify's /products.json has no currency field at all - those rows
    print with currency "?"; open the real product page to get the
    actual formatted price/currency before writing a promotions.json
    entry (WooCommerce rows already have a real currency).

RUN:
    python3 scraper/find_price_promotions.py [--min-discount 10]
"""

import argparse
import sqlite3

from scrape import DB_PATH

# Below this, a "discount" reads more like rounding noise than a real
# promotion worth surfacing (see the docstring above) - tunable per
# invocation via --min-discount, matching MAX_RESULTS_PER_BRAND-style
# "easy to retune once there's real usage to test against" precedent in
# backend/query_engine.py.
DEFAULT_MIN_DISCOUNT_PCT = 10


def find_candidates(min_discount_pct=DEFAULT_MIN_DISCOUNT_PCT):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT brand, product_name, product_url, image_url, category,
               price, compare_at_price, currency
        FROM products
        WHERE image_url != ''
          AND compare_at_price IS NOT NULL
          AND price IS NOT NULL
          AND compare_at_price > price
    """).fetchall()
    conn.close()

    candidates = []
    for row in rows:
        pct = round((row["compare_at_price"] - row["price"]) / row["compare_at_price"] * 100)
        if pct < min_discount_pct:
            continue
        candidates.append({
            "brand": row["brand"],
            "product_name": row["product_name"],
            "product_url": row["product_url"],
            "image": row["image_url"],
            "category": row["category"],
            "price_now": row["price"],
            "price_was": row["compare_at_price"],
            "currency": row["currency"] or "?",
            "discount_pct": pct,
        })

    candidates.sort(key=lambda c: c["discount_pct"], reverse=True)
    return candidates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-discount", type=int, default=DEFAULT_MIN_DISCOUNT_PCT,
        help=f"Only show discounts at or above this percentage (default {DEFAULT_MIN_DISCOUNT_PCT}).",
    )
    args = parser.parse_args()

    candidates = find_candidates(args.min_discount)
    print(f"{len(candidates)} live discount(s) of {args.min_discount}%+ found across the catalog.\n")
    for c in candidates:
        print(f"{c['brand']} - {c['product_name']} - {c['discount_pct']}% off")
        print(f"   {c['currency']} {c['price_was']:g} -> {c['currency']} {c['price_now']:g}")
        print(f"   {c['product_url']}")
        print(f"   image: {c['image']}")
        print()
