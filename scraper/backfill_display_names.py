"""Apply scrape.py's _display_name() (Ligne Roset finish clauses cut, hand-set names from data/name_overrides.json) to the rows
already in data/formground.db, so the pages are right without re-scraping. The scraper applies the same function on every save.

    python3 scraper/backfill_display_names.py            # dry run: before -> after
    python3 scraper/backfill_display_names.py --apply    # update the database
"""
import argparse
import sqlite3

from scrape import DB_PATH, _display_name


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH)
    changes = [(i, b, n, _display_name(b, n)) for i, b, n in conn.execute("SELECT id, brand, product_name FROM products")]
    changes = [c for c in changes if c[3] != c[2]]
    for _, brand, old, new in changes:
        print(f"{brand} | {old}  ->  {new}")
    print(f"\\n{len(changes)} names change")
    if args.apply:
        conn.executemany("UPDATE products SET product_name = ? WHERE id = ?", [(c[3], c[0]) for c in changes])
        conn.commit()
        print("database updated")
    conn.close()


if __name__ == "__main__":
    main()
