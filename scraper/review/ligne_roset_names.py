"""Ligne Roset titles run the model name, the type and the finish together ("Naia Dining table legs in bronze-stained oak").
This cuts the finish clauses ("legs in ...", "base in ...", "top in ...") so the rest reads "Naia Dining table"; sizes, shapes and
arm options ("Oval", "Large", "with 2 arms") stay, because those are different pieces, not finishes.

    python3 scraper/review/ligne_roset_names.py            # preview: before -> after, and what would merge
"""
import collections
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DB = ROOT / "data" / "formground.db"

PARTS = r"(?:top|tops|base|bases|legs?|feet|foot|frame|structure|seat|shell|cover|covers|upholstery|upholstered|plinth|stand|arms?)"
# "<part> in <finish ...>" and "<part> <finish ...>" runs up to the next clause or the end
CLAUSE = re.compile(rf"\s+(?:{PARTS})\s+in\s+[^+,/]*?(?=\s+(?:{PARTS})\s+in\s+|\s*[+,/]|$)", re.I)
# "marble top white lacquered base": materials/finishes around the word top/base
FINISH_RUN = re.compile(r"\s+(?:[a-z\-]+(?:-effect|-stained|-coloured|-lacquered)?\s+){1,4}(?:top|base)\b(?:\s+[a-z\-]+){0,3}\s+(?:top|base)\b|\s+[a-z\-]+\s+top\s+[a-z\- ]+\s+base\b", re.I)


def clean(name):
    out = CLAUSE.sub("", name)
    out = re.sub(r"\s+", " ", out).strip(" -–,")
    return out


def main():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id, product_name FROM products WHERE brand = 'Ligne Roset'").fetchall()
    changed = [(i, n, clean(n)) for i, n in rows if clean(n) != n]
    before = len({n for _, n in rows})
    after = len({clean(n) for _, n in rows})
    print(f"{len(rows)} Ligne Roset pieces; {len(changed)} names change; distinct names {before} -> {after}")
    merged = collections.defaultdict(list)
    for i, n, c in changed:
        merged[c].append(n)
    for c, ns in sorted(merged.items(), key=lambda kv: -len(kv[1]))[: int(sys.argv[1]) if len(sys.argv) > 1 else 40]:
        print(f"\n{c}   ({len(ns)} listings)")
        for n in ns[:4]:
            print("    from:", n)


if __name__ == "__main__":
    main()
