"""Apply the answers saved by the storage review page (data/category_review_storage.json). Same flow as apply_chair_review.py.

    python3 scraper/review/apply_storage_review.py            # dry run: prints every change
    python3 scraper/review/apply_storage_review.py --apply    # updates the database and writes data/category_overrides.json

An answer says which types a piece IS. The new tag list keeps the maker's tags that agree with the answer and the generic
ones (Chair, Seating), adds the type tag the answer needs, and drops the maker's seating-type tags the answer rules out.
"Accessory" sets the category to Accessories, "Not seating" strips the seating tags, a typed note sets the category from the
note (see NOTE_TO_CATEGORY). The result is stored in data/category_overrides.json, which scrape.py merges into
MANUAL_CATEGORY_OVERRIDES, so a re-scrape keeps it.
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
DECISIONS = ROOT / "data" / "category_review_storage.json"
OVERRIDES = ROOT / "data" / "category_overrides.json"
EXCLUDED = ROOT / "data" / "excluded_listings.json"
DB = ROOT / "data" / "formground.db"

# What each type page matches on (a substring of the category): a tag "supports" the pages whose term it contains.
SLUG_TAG = {
    "sideboards": r"sideboard", "cabinets": r"cabinet", "shelving": r"shelving", "beds": r"\bbeds?\b|day bed", "mirrors": r"mirror",
    "console-tables": r"console table|console", "bedside-tables": r"bedside table|nightstand", "desks": r"desk",
    "sofas": r"sofa", "armchairs": r"arm ?chair|lounge chair", "benches": r"bench",
}
CANONICAL = {"sideboards": "sideboard", "cabinets": "cabinet", "shelving": "shelving", "beds": "bed", "mirrors": "mirror",
             "console-tables": "console table", "bedside-tables": "bedside table", "desks": "desk", "sofas": "sofa", "armchairs": "lounge chair",
             "benches": "bench"}
IMPLIED = {}
GENERIC = re.compile(r"^(storage|furniture|bedroom|living room|storage & shelving)$", re.I)
NOTE_TYPES = {}
NOTE_REPLACE = {}
NOTE_ACCESSORY = {"parts", "part", "spare part", "spare parts", "accessory"}
KEEP_AS_IS_NOTES = set()


def dedupe(tags):
    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def split(cat):
    return [t.strip() for t in (cat or "").split(",") if t.strip()]


def supports(tag):
    return {sl for sl, rx in SLUG_TAG.items() if re.search(rx, tag, re.I)}


def is_group_tag(tag):
    return bool(re.search(r"&| and ", tag, re.I)) or bool(GENERIC.match(tag))


def with_types(tags, selected):
    keep_for = set(selected)
    for sl in selected:
        keep_for |= IMPLIED.get(sl, set())
    out = [t for t in tags if GENERIC.match(t) or not supports(t) or supports(t) <= keep_for]
    for sl in selected:
        if not any(re.search(SLUG_TAG[sl], t, re.I) for t in out):
            out.insert(0, CANONICAL[sl])
    return out


def new_category(cat, d):
    tags = split(cat)
    note = (d.get("what") or "").strip().lower()
    if d.get("fine"):
        return cat
    if d.get("acc"):
        return "Accessories"
    non_seating = [t for t in tags if is_group_tag(t) is False and not supports(t)]
    if re.search(r"doll bed|\bremove\b|offer for two|two products", note):
        return "EXCLUDE"                                  # a toy or a packaged offer: taken off the site
    if d.get("none") and not note:
        return ", ".join(non_seating) if non_seating else "Objects"
    if d.get("types"):
        note = ""
    if note:
        if re.search(r"^sofa bed", note):
            return ", ".join(with_types(tags, ["sofas", "beds"]))
        if note in ("sofa",):
            return ", ".join(with_types(tags, ["sofas"]))
        if note == "armchair":
            return ", ".join(with_types(tags, ["armchairs"]))
        if note == "bench":
            return ", ".join(with_types(tags, ["benches"]))
        if re.search(r"bunk", note):
            return ", ".join(with_types(tags, ["beds"]))
        if "headboard" in note:
            return cat                                    # stays on Beds
        if re.search(r"\bdogs?\b|\bpet\b", note):
            return "Pet Accessories"
        if "runner" in note:
            return "Rug"
        if re.search(r"canopy|slats|\bpart\b|accessory|add on", note):
            return "Accessories"
        if "sheets" in note:
            return "Bedding"                                         # a type was chosen: the note is only a remark
    if note in NOTE_ACCESSORY or re.search(r"\bparts?\b|snuffer", note):
        return "Accessories"
    if note == "pendant lamp":
        return "pendant"
    if note in KEEP_AS_IS_NOTES:
        return cat
    if note in NOTE_REPLACE:
        return NOTE_REPLACE[note]
    if note in NOTE_TYPES:
        out = with_types(tags, NOTE_TYPES[note])
        if note == "side table and stool":
            out = dedupe(out + ["stool"])
        return ", ".join(out)
    if note and not d.get("types"):
        return None                                       # a note we do not know: reported, not applied
    selected = d.get("types") or []
    return ", ".join(with_types(tags, selected)) if selected else cat


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    decisions = json.loads(DECISIONS.read_text()) if DECISIONS.exists() else {}
    conn = sqlite3.connect(DB)
    changes, skipped, unknown, excluded = [], [], [], []
    for pid, d in decisions.items():
        row = conn.execute("SELECT id, brand, product_name, category FROM products WHERE id=?", (int(pid),)).fetchone()
        if not row:
            continue
        _, brand, name, cat = row
        if not (d.get("fine") or d.get("acc") or d.get("none") or d.get("types") or d.get("what")):
            skipped.append((brand, name, "no answer"))
            continue
        new = new_category(cat, d)
        if new == "EXCLUDE":
            excluded.append((int(pid), brand, name))
            continue
        if new is None:
            unknown.append((brand, name, d.get("what")))
        elif new != (cat or ""):
            changes.append((int(pid), brand, name, cat or "", new))
    for _, brand, name, old, new in changes:
        print(f"{brand} | {name[:46]} | {old[:50]}  ->  {new[:60]}")
    for _, brand, name in excluded:
        print(f"{brand} | {name[:46]}  ->  taken off the site (a bundle or spare part)")
    print(f"\n{len(changes)} changes; {len(excluded)} taken off the site; {len(unknown)} notes not understood: {unknown}; {len(skipped)} with no answer")
    if args.apply:
        conn.executemany("UPDATE products SET category = ? WHERE id = ?", [(c[4], c[0]) for c in changes])
        conn.commit()
        existing = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else []
        by_key = {(e["brand"], e["name"]): e for e in existing}
        for _, brand, name, _old, new in changes:
            by_key[(brand, name)] = {"brand": brand, "name": name, "category": new}
        OVERRIDES.write_text(json.dumps(sorted(by_key.values(), key=lambda e: (e["brand"], e["name"])), ensure_ascii=False, indent=1))
        if excluded:
            have = json.loads(EXCLUDED.read_text()) if EXCLUDED.exists() else []
            have += [{"brand": b, "name": n} for _, b, n in excluded if {"brand": b, "name": n} not in have]
            EXCLUDED.write_text(json.dumps(have, ensure_ascii=False, indent=1))
            conn.executemany("DELETE FROM products WHERE id = ?", [(i,) for i, _, _ in excluded])
            conn.commit()
        print("database updated; overrides written to", OVERRIDES)
    else:
        print("(dry run)")
    conn.close()


if __name__ == "__main__":
    main()
