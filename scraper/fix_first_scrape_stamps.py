"""
One-time correction for a real bug in scrape.py's first_seen logic
(fixed 2026-09-28, see run()'s new is_first_scrape_for_brand check):
a brand's very first scrape had no prior rows to carry first_seen
forward from, so its entire back-catalog was wrongly stamped "new
today" - making an established brand's years-old catalog look like a
mass product launch on the "New" page and brand pages' own "News"
sections.

This script corrects the data already written before that fix existed.
It does NOT rely on git history or brands.json addition dates (checked
live: &Tradition was added to brands.json 2026-09-24 but its first
successful scrape didn't land in the database until 2026-09-26 - the
database's own data is the real source of truth, not the config file).

THE RULE: for each brand, find its most common first_seen date among
its current rows. If that one date accounts for at least 95% of the
brand's rows (and at least 3 rows, to avoid a coincidence on a
brand with only 1-2 products), treat every row with that exact date as
a first-scrape artifact and null it out. Only rows matching that exact
(brand, date) pair are touched - a small number of genuinely newer
additions since onboarding (a different date) are correctly left alone.

Run with --dry-run first (the default) to see the report with nothing
written. Pass --apply to actually update the database.
"""

import argparse
import collections
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "formground.db"


def find_first_scrape_stamps(conn):
    rows = conn.execute("SELECT brand, first_seen FROM products").fetchall()
    by_brand = collections.defaultdict(list)
    for brand, first_seen in rows:
        by_brand[brand].append(first_seen)

    flagged = []
    for brand, dates in by_brand.items():
        non_null = [d for d in dates if d]
        if not non_null:
            continue
        counts = collections.Counter(non_null)
        top_date, top_count = counts.most_common(1)[0]
        fraction = top_count / len(dates)
        if fraction >= 0.95 and top_count >= 3:
            flagged.append((brand, top_date, top_count, len(dates)))
    return flagged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually write the correction (default is a dry run)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    flagged = find_first_scrape_stamps(conn)

    by_date = collections.defaultdict(list)
    for brand, date, count, total in flagged:
        by_date[date].append((brand, count, total))

    total_rows = sum(f[2] for f in flagged)
    print(f"{len(flagged)} brands flagged, {total_rows} rows would be corrected\n")
    for date in sorted(by_date):
        entries = by_date[date]
        print(f"{date}: {len(entries)} brands, {sum(c for _, c, _ in entries)} rows")
        for brand, count, total in sorted(entries, key=lambda x: -x[1]):
            print(f"    {brand}: {count}/{total}")

    if not args.apply:
        print("\nDry run only - pass --apply to write this correction.")
        conn.close()
        return

    for brand, date, count, total in flagged:
        conn.execute(
            "UPDATE products SET first_seen = NULL WHERE brand = ? AND first_seen = ?",
            (brand, date),
        )
    conn.commit()
    conn.close()
    print(f"\nApplied: {total_rows} rows corrected across {len(flagged)} brands.")


if __name__ == "__main__":
    main()
