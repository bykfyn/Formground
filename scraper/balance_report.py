"""
Catalogue balance report (2026-10-17): for every Work type page, how much of it one brand supplies.

A brand's size does not matter on its own (a 2,700-piece tableware house is fine in a type it shares with 20 other makers);
what matters is the share one brand has of a type, because that is what a visitor browsing the type sees.
Flags types where one brand supplies more than THRESHOLD of the pieces, with the brand's own count.

    python3 scraper/balance_report.py                 # print the report
    python3 scraper/balance_report.py --threshold 35  # a different flag line (default 40, in %)
"""
import argparse
import collections
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import generate_browse_pages as gbp  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=float, default=40.0)
    args = ap.parse_args()
    rows = []
    for cat in gbp.BROWSE_CATEGORIES:
        products = gbp._category_products(cat)
        n = len(products)
        if n < 60:
            continue
        counts = collections.Counter(p["brand"] for p in products)
        brand, top = counts.most_common(1)[0]
        share = 100 * top / n
        rows.append((share, cat["title"], n, len(counts), brand, top, counts.most_common(3)))
    rows.sort(reverse=True)
    print(f"{'type':32} {'pieces':>6} {'brands':>6}  top brand (share)")
    for share, title, n, nb, brand, top, top3 in rows:
        flag = "  <-- over the line" if share >= args.threshold else ""
        print(f"{title:32} {n:>6} {nb:>6}  {brand} {top} ({share:.0f}%){flag}")


if __name__ == "__main__":
    main()
