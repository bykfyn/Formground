"""
One-time backfill (2026-10-04): give chairs that carry only the generic "chair"/"chairs" tag a
sub-type when their NAME says what they are ("ELLIOT DINING CHAIR", "Era Armchair", "Task chair 3").

Applies scrape.py's _refine_chair_subtype() - the same function the scraper now runs on every save, so a
re-scrape keeps these - to the rows already in data/formground.db, so the browse pages are right now
without re-running every brand's scraper. It only ever PREPENDS a tag ("dining chair, Chair"); the
brand's own tags stay.

    python3 scraper/backfill_chair_subtypes.py            # dry run: counts + examples, writes nothing
    python3 scraper/backfill_chair_subtypes.py --apply    # update the database
"""

import argparse
import collections
import sqlite3

from scrape import DB_PATH, _refine_chair_subtype


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, brand, product_name, category FROM products").fetchall()
    changes = []
    for pid, brand, name, category in rows:
        new = _refine_chair_subtype(name, category)
        if new != category:
            changes.append((pid, brand, name, category, new))
    by_tag = collections.Counter(c[4].split(",")[0] for c in changes)
    print(f"{len(changes)} of {len(rows)} products would get a sub-type tag:")
    for tag, n in by_tag.most_common():
        print(f"  {n:>4}  {tag}")
    by_brand = collections.Counter(c[1] for c in changes)
    print("biggest brands:", by_brand.most_common(8))
    for tag in by_tag:
        ex = [c for c in changes if c[4].startswith(tag + ",")][:6]
        print(f"\n  e.g. {tag}:", [f"{c[2][:34]} ({c[1]})" for c in ex])
    if args.apply:
        conn.executemany("UPDATE products SET category = ? WHERE id = ?", [(c[4], c[0]) for c in changes])
        conn.commit()
        print(f"\nupdated {len(changes)} rows")
    else:
        print("\n(dry run - nothing written; add --apply)")
    conn.close()


if __name__ == "__main__":
    main()
