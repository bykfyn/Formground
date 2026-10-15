"""Build the review list for objects and soft furnishings: pieces whose type pages do not match what their name says.

    python3 scraper/review/build_objects_review.py     # writes review/objects_items.json next to this script

Shown at http://localhost:8094/?family=objects; answers go to data/category_review_objects.json (see apply_objects_review.py).
Name is the only signal (no photo labels exist for objects).
"""
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "backend"))
import generate_browse_pages as g  # noqa: E402

FAMILY = ["candle-holders", "candles", "glass", "vases", "bowls", "plates", "trays", "rugs", "cushions", "blankets"]
TYPES = [("vases", "Vase"), ("bowls", "Bowl"), ("plates", "Plate"), ("trays", "Tray"), ("glass", "Glass"), ("candle-holders", "Candle holder"),
         ("candles", "Candle"), ("rugs", "Rug"), ("cushions", "Cushion"), ("blankets", "Blanket / throw")]
# what the name says it is; a type is only suggested when the page does not already carry it
NAME_TYPES = [
    ("candle-holders", r"candle ?holder|candle ?stick|candelabra|tea ?light|votive|lantern"),
    ("vases", r"\bvases?\b|\bvessel\b|\bjug\b|\bcarafe\b|\bewer\b"),
    ("bowls", r"\bbowls?\b|\bsalad bowl\b"),
    ("plates", r"\bplates?\b|\bplatter\b|\bsaucer\b"),
    ("trays", r"\btray\b"),
    ("glass", r"\b(wine|drinking|water|champagne|whisky|tumbler|cocktail) glass(es)?\b|\btumbler\b|\bgoblet\b|\bglasses\b"),
    ("rugs", r"\brugs?\b|\bcarpet\b|\brunner\b|\bdoormat\b"),
    ("cushions", r"\bcushion\b|\bpillow\b"),
    ("blankets", r"\bblanket\b|\bthrow\b|\bplaid\b"),
    ("candles", r"\bcandles?\b(?!.*holder)(?!.*stick)"),
    ("part", r"\bspare\b|replacement|\blid for\b|\bwick\b|\bcandle snuffer\b"),
    ("not-an-object", r"\blamp\b|\bpendant\b|\bchair\b|\bstool\b|\bbench\b|\bsofa\b|\btable\b(?! (lamp|runner|cloth|linen|mat|top))|\bshelf\b|\bmirror\b|\bbed\b"),
]
# pairs that are fine together (a bowl listed as a plate page and so on is judged by the review, but these are normal overlaps)
NEAR = {("bowls", "plates"), ("plates", "bowls"), ("trays", "plates"), ("plates", "trays"), ("vases", "bowls"), ("bowls", "vases"),
        ("candle-holders", "candles"), ("candles", "candle-holders"), ("blankets", "cushions"), ("cushions", "blankets"),
        ("vases", "candle-holders"), ("candle-holders", "vases"), ("trays", "bowls"), ("bowls", "trays"), ("glass", "vases"), ("vases", "glass"),
        ("glass", "candle-holders"), ("candle-holders", "glass"), ("glass", "bowls"), ("bowls", "glass")}
LABELS = {"part": "an accessory or spare part", "not-an-object": "not an object (a lamp, chair, table or similar)"}


def name_types(name):
    t = name.lower()
    return [slug for slug, rx in NAME_TYPES if re.search(rx, t)]


def build():
    byid, pages = {}, collections.defaultdict(set)
    for c in g.BROWSE_CATEGORIES:
        if c["slug"] in FAMILY:
            for p in g._category_products(c):
                byid[p["id"]] = p
                pages[p["id"]].add(c["slug"])
    out = []
    for pid, p in byid.items():
        have = pages[pid]
        nt = name_types(p["product_name"])
        types_in_name = [t for t in nt if t not in ("part", "not-an-object")]
        reasons, suggest = [], []
        for t in nt:
            if t in ("part", "not-an-object"):
                if t == "not-an-object" and types_in_name:
                    continue            # "Vase lamp", "Bowl pendant": the review of the type decides
                reasons.append("The name looks like " + LABELS[t])
                suggest.append(t)
        wrong = [s for s in have if types_in_name and not any(s == t or (s, t) in NEAR for t in types_in_name)]
        if wrong:
            reasons.append("It is on " + ", ".join(w.replace("-", " ") for w in wrong) + ", but the name points to " + ", ".join(t.replace("-", " ") for t in types_in_name))
            suggest += [t for t in types_in_name if t not in have]
        if reasons:
            out.append({"id": pid, "brand": p["brand"], "name": p["product_name"], "tag": p["category"] or "", "url": p["product_url"],
                        "image": p["image_url"], "pages": sorted(have), "reasons": reasons, "suggest": sorted(set(suggest))})
    out.sort(key=lambda r: (r["suggest"][:1] not in (["part"], ["not-an-object"]), r["brand"].lower(), r["name"].lower()))
    payload = {"title": "Objects review", "types": TYPES, "none": "Not an object", "acc": "Accessory (cover, part)",
               "labels": {**dict(TYPES), "part": "Accessory (cover, part)", "not-an-object": "Not an object"}, "items": out}
    (HERE / "objects_items.json").write_text(json.dumps(payload, ensure_ascii=False))
    print(len(byid), "pieces in the family;", len(out), "to review")
    print(collections.Counter(s for r in out for s in r["suggest"]).most_common())


if __name__ == "__main__":
    build()
