"""How many maker pages show a "Where to buy" section, and how that changes with the minimum (2026-11-21).

Counts visible makers (products in the database, not hidden, not portfolio) by number of stockist chains listed in
data/retailers.json, and says which makers are one stockist short of the current minimum
(MIN_STOCKISTS_SHOWN in generate_brand_pages.py). Re-run after adding makers or retailer entries.

    python3 scraper/stockist_coverage.py
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
import generate_brand_pages as g  # noqa: E402


def main():
    stockists = {g.slugify(k): v for k, v in g.load_stockists_by_brand().items()}
    raw = json.load(open(ROOT / "scraper/brands.json"))
    brands = raw if isinstance(raw, list) else raw["brands"]
    visible = {b["name"] for b in brands if not b.get("hidden") and not b.get("portfolio")}
    db = sqlite3.connect(ROOT / "data/formground.db")
    have = {r[0] for r in db.execute("select distinct brand from products")} & visible
    counts = {b: len(stockists.get(g.slugify(b), [])) for b in have}
    dist = Counter(counts.values())
    shown = sum(1 for n in counts.values() if n >= g.MIN_STOCKISTS_SHOWN)
    print(f"{len(have)} visible makers; minimum is {g.MIN_STOCKISTS_SHOWN}, so {shown} pages show 'Where to buy'.")
    for n in range(0, 6):
        print(f"  {n} stockist{'s' if n != 1 else ''}: {dist.get(n, 0)}")
    print(f"  6+: {sum(v for k, v in dist.items() if k >= 6)}")
    one = sorted(b for b, n in counts.items() if n == g.MIN_STOCKISTS_SHOWN - 1)
    print(f"\n{len(one)} makers are one stockist short of showing it (first 25): " + ", ".join(one[:25]))


if __name__ == "__main__":
    main()
