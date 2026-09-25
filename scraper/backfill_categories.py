"""
One-time backfill: re-derive a more specific category for existing
products whose stored category is blank or one of a small set of known
too-generic umbrella values (2026-09-25, user: "we need any solution to
correctly tag each existing product so that search results are
accurate").

WHY A SEPARATE SCRIPT, NOT JUST A RE-SCRAPE:
  scrape.py's ENGLISH_OBJECT_TYPE_KEYWORDS fallback only runs live,
  at scrape time, for brands on CATEGORY_KEYWORD_FALLBACK_BRANDS - an
  allowlist kept deliberately narrow after real false positives on
  other brands (Minimalux, Ingo Maurer). Re-running every brand's own
  scraper to pick up the newly-expanded keyword list would take hours
  and isn't necessary: this script applies the same
  _infer_category_from_english_keywords() function directly against
  each existing row's already-stored product_name, for ANY brand, but
  ONLY when the existing category is already known-generic. That's the
  safe subset - it can only ever replace a non-specific placeholder
  with a more specific one, never override a brand's own real,
  already-specific category (which is what caused the Minimalux/Ingo
  Maurer false positives before: overriding a *specific* existing tag
  like "Jewellery" with a keyword match meant for lighting).

SCOPE:
  GENERIC_CATEGORIES below - blank plus a short, deliberately narrow
  list of umbrella/non-specific values confirmed live 2026-09-25 by
  auditing the real category distribution (24,771 products, 1,636
  distinct raw category strings). Values that are merely inconsistent
  in casing/plural ("Chairs" vs "Chair") or untranslated foreign-
  language umbrella terms ("Belysning", "Møbler") are a separate,
  narrower normalization problem, not touched here. Nor are outright
  junk values from specific brand bugs ("Customization", "Replacements",
  "N09 Subproduct") - those need per-brand investigation, not a keyword
  re-guess.

WHAT THIS CANNOT FIX:
  A real fraction of these products have abstract/artistic names with
  no object-type word in them at all ("Zuuk", "TRIPTYCH", "538") - no
  keyword list, however complete, can recover information that was
  never in the name. Confirmed live: no description field is stored
  for any product, so there's no richer text to fall back on either.
  Those rows are left as-is; closing that gap for real would mean
  fetching each product's own page for its description, a much bigger,
  per-brand scraping effort - only worth scoping once this pass shows
  how much is actually left unresolved.

RUN:
    python3 scraper/backfill_categories.py --dry-run   # preview counts only
    python3 scraper/backfill_categories.py              # apply for real
"""

import argparse
import sqlite3
from pathlib import Path

from scrape import DB_PATH, _infer_category_from_english_keywords

GENERIC_CATEGORIES = {
    "", "Lighting", "Furniture", "Objects", "Accessories", "Tableware",
    "Seating", "Chair", "Table", "Lamp", "Light", "Glass", "simple",
    "Ceramics",
}


def run(dry_run=True):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    placeholders = ",".join("?" * len(GENERIC_CATEGORIES))
    cur.execute(
        f"SELECT id, brand, product_name, category FROM products WHERE category IN ({placeholders})",
        list(GENERIC_CATEGORIES),
    )
    rows = cur.fetchall()
    print(f"{len(rows)} products currently in a generic/blank category.")

    resolved = []
    for row_id, brand, name, old_category in rows:
        new_category = _infer_category_from_english_keywords(name)
        # A match that just returns the same generic value the row
        # already had (e.g. category="Chair", name contains only the
        # bare word "chair", no modifier) isn't a real improvement -
        # the name genuinely doesn't offer more specificity than what's
        # already stored, so this doesn't count as resolved.
        if new_category and new_category != old_category:
            resolved.append((row_id, brand, name, old_category, new_category))

    print(f"{len(resolved)} of those resolve to a *more specific* category ({len(rows) - len(resolved)} remain unresolved - either no type word in the name at all, or the name only repeats the same generic word already stored).")

    from collections import Counter
    upgrade_counts = Counter(f"{old or '(blank)'} -> {new}" for _, _, _, old, new in resolved)
    print("\nTop upgrades:")
    for upgrade, n in upgrade_counts.most_common(25):
        print(f"  {n:5d}  {upgrade}")

    if dry_run:
        print("\nDry run - no changes written. Re-run without --dry-run to apply.")
        return

    cur.executemany(
        "UPDATE products SET category = ? WHERE id = ?",
        [(new_category, row_id) for row_id, _, _, _, new_category in resolved],
    )
    conn.commit()
    print(f"\nUpdated {len(resolved)} rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview counts without writing changes.")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
