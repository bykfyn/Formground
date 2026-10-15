"""
One-time backfill (2026-10-15): seat pads, chair/stool/bench/lounger cushions and loose covers
get the type "Furniture Accessory" (scrape.py _normalize_furniture_accessory(), which the
scraper now runs on every save), so the Cushions page keeps only the general cushions.

    python3 scraper/backfill_furniture_accessories.py            # dry run
    python3 scraper/backfill_furniture_accessories.py --apply    # update the database
"""

import argparse
import collections
import sqlite3

from scrape import DB_PATH, _normalize_furniture_accessory


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH)
    changes = []
    for pid, brand, name, category in conn.execute("SELECT id, brand, product_name, category FROM products"):
        new = _normalize_furniture_accessory(name, category)
        if new != category:
            changes.append((pid, brand, name, category, new))
    print(f"{len(changes)} products become Furniture Accessory")
    print("by brand:", collections.Counter(c[1] for c in changes).most_common())
    print("from:", collections.Counter((c[3] or "")[:30] for c in changes).most_common(8))
    for c in changes:
        print("  ", c[1], "|", c[2])
    if args.apply:
        conn.executemany("UPDATE products SET category = ? WHERE id = ?", [(c[4], c[0]) for c in changes])
        conn.commit()
        print(f"updated {len(changes)} rows")
    else:
        print("(dry run - nothing written; add --apply)")
    conn.close()


if __name__ == "__main__":
    main()
