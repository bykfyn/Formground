"""
Finds real candidates for the "maker bundle" Promotions idea (see project
memory maker_bundle_promotions_and_new_maker_leads.md) - a product that's
sold both as a single unit AND as a multi-buy bundle of the exact same
item, the pattern behind both MOR's "6x FRAME" chair set and Tala's
"Knuckle Table Lamp in Walnut + Sphere IV Set" (confirmed live 2026-09-25:
a genuine 10% discount for buying the pair).

WHY THIS APPROACH, NOT A KEYWORD SCAN:
  A plain scan for words like "Duo"/"Pair"/"Twin"/"Set" in product names
  is mostly noise - checked live 2026-09-25: most hits are just a design's
  own name ("Duo Rug", "Twin Kelpie Bench") or a naturally-plural item
  ("Pair of serving spoons") with no separate single-unit sibling at all,
  so there's no real "which one do I buy" bundle decision being offered.
  The real signal is a MATCHING PAIR: one product whose name is another
  real product's name plus a trailing bundle-quantity marker, both from
  the same brand - that's the only shape that indicates a genuine "buy
  more than one" choice, which is what makes it promotable at all.

WHAT THIS CANNOT DO:
  This only finds bundles already sitting in the DB with a matching
  single-unit sibling. MOR's own bundle pattern ("{N}x " prefix) is
  filtered out before it ever reaches the DB (see
  _looks_like_a_maintenance_item in scrape.py) precisely because it's
  excluded from normal search - finding MORE of that specific shape
  would need new, separate scraping, not a scan of already-stored data.
  This also can't confirm a real discount exists - only a live check of
  each candidate's own page can do that (see Tala's real 10% cut, found
  by hand). Treat this script's output as a candidate list to spot-check,
  not a finished promotions list.

RUN:
    python3 scraper/find_bundle_promotion_candidates.py
"""

import re
import sqlite3
from collections import defaultdict

from scrape import DB_PATH

# Each pattern captures nothing - it's stripped wholesale from the end of
# the name (after lowercasing) to recover the base product name. Ordered
# and anchored to the end ($) so a pattern doesn't fire on a design's own
# mid-name word (e.g. "Duo Desk" - "duo" isn't at the end, so it's never
# stripped, so it's never mistaken for a bundle of some other product).
BUNDLE_SUFFIX_PATTERNS = [
    re.compile(r"\s*\(?set of \d+\)?\s*$", re.IGNORECASE),
    re.compile(r"\s*\(?pack of \d+\)?\s*$", re.IGNORECASE),
    re.compile(r"\s*\(?\d+[- ]pack\)?\s*$", re.IGNORECASE),
    re.compile(r"\s*\(?x\d+\)?\s*$", re.IGNORECASE),
    re.compile(r"\s+set\s*$", re.IGNORECASE),
]


def _strip_bundle_suffix(name: str):
    for pattern in BUNDLE_SUFFIX_PATTERNS:
        if pattern.search(name):
            return pattern.sub("", name).strip()
    return None


def find_candidates():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT brand, product_name, product_url FROM products WHERE image_url != ''")
    rows = cur.fetchall()
    conn.close()

    by_brand = defaultdict(dict)
    for brand, name, url in rows:
        by_brand[brand].setdefault(name.strip().lower(), []).append((name, url))

    candidates = []
    for brand, names in by_brand.items():
        for name_lower, entries in names.items():
            for name, url in entries:
                base = _strip_bundle_suffix(name)
                if not base:
                    continue
                base_lower = base.strip().lower()
                if base_lower == name_lower:
                    continue
                if base_lower in names:
                    single_name, single_url = names[base_lower][0]
                    candidates.append({
                        "brand": brand,
                        "bundle_name": name,
                        "bundle_url": url,
                        "single_name": single_name,
                        "single_url": single_url,
                    })
    return candidates


if __name__ == "__main__":
    candidates = find_candidates()
    print(f"{len(candidates)} real single+bundle sibling pairs found.\n")
    by_brand = defaultdict(list)
    for c in candidates:
        by_brand[c["brand"]].append(c)
    for brand, items in sorted(by_brand.items()):
        print(f"{brand} ({len(items)}):")
        for c in items:
            print(f"   bundle: {c['bundle_name']}")
            print(f"     -> {c['bundle_url']}")
            print(f"   single: {c['single_name']}")
            print(f"     -> {c['single_url']}")
        print()
