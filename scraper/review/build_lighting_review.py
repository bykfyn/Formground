"""Build the review list for lighting: pieces whose type pages do not match what their name says.

    python3 scraper/review/build_lighting_review.py     # writes review/lighting_items.json next to this script

Shown at http://localhost:8094/?family=lighting; answers go to data/category_review_lighting.json (see apply_lighting_review.py).
No photo labels exist for lighting, so the name is the only signal.
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

FAMILY = ["table-lamps", "pendant-lamps", "wall-lamps", "ceiling-lamps", "chandeliers", "floor-lamps"]
TYPES = [("table-lamps", "Table lamp"), ("floor-lamps", "Floor lamp"), ("pendant-lamps", "Pendant lamp"), ("wall-lamps", "Wall lamp"),
         ("ceiling-lamps", "Ceiling lamp"), ("chandeliers", "Chandelier")]
NAME_TYPES = [
    ("chandeliers", r"chandelier"),
    ("pendant-lamps", r"pendant|suspension|suspended|hanging lamp|hanging light"),
    ("wall-lamps", r"wall (lamp|light|sconce|mounted)|sconce|\bapplique"),
    ("ceiling-lamps", r"ceiling (lamp|light|fixture)|flush ?mount|semi-flush|surface mount|plafonnier"),
    ("floor-lamps", r"floor (lamp|light|standing)|standing lamp|floor standard|torch[iè]re|reading lamp"),
    ("table-lamps", r"table (lamp|light)|desk lamp|bedside lamp|bedside light|\btable lamp"),
    ("part", r"lamp ?shade|\bshade only\b|\bcanopy\b|\bcable\b|\bdimmer\b|\bplug\b(?!-in)|\bsocket\b|\bdriver\b|transformer|\bremote\b|\bspare\b|replacement|\bglass for\b|\bdiffuser\b"),
    ("not-a-lamp", r"^(?!.*(lamp|light|pendant|sconce|chandelier|lantern)).*(\bchair\b|\bstool\b|\bvase\b|\bmirror\b|\brug\b|\bcandle ?holder|\bplanter\b)"),
]
NEAR = {("table-lamps", "floor-lamps"), ("floor-lamps", "table-lamps"), ("wall-lamps", "ceiling-lamps"), ("ceiling-lamps", "wall-lamps"),
        ("pendant-lamps", "chandeliers"), ("chandeliers", "pendant-lamps"), ("pendant-lamps", "ceiling-lamps"), ("ceiling-lamps", "pendant-lamps"),
        ("chandeliers", "ceiling-lamps"), ("ceiling-lamps", "chandeliers")}
LABELS = {"part": "a bulb, shade, cable or other part", "not-a-lamp": "not a lamp"}


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
        types_in_name = [t for t in nt if t not in ("part", "not-a-lamp")]
        reasons, suggest = [], []
        for t in nt:
            if t in ("part", "not-a-lamp"):
                reasons.append("The name looks like " + LABELS[t])
                suggest.append(t)
            elif t not in have and not any((t, h) in NEAR for h in have):
                reasons.append(f"The name says {t.replace('-', ' ')}, but it is not on that page")
                suggest.append(t)
        wrong = [s for s in have if types_in_name and not any(s == t or (s, t) in NEAR for t in types_in_name)]
        if wrong and not suggest:
            reasons.append("It is on " + ", ".join(w.replace("-", " ") for w in wrong) + ", but the name points elsewhere")
            suggest += [t for t in types_in_name if t not in have]
        if reasons:
            out.append({"id": pid, "brand": p["brand"], "name": p["product_name"], "tag": p["category"] or "", "url": p["product_url"],
                        "image": p["image_url"], "pages": sorted(have), "reasons": reasons, "suggest": sorted(set(suggest))})
    out.sort(key=lambda r: (r["suggest"][:1] not in (["part"], ["not-a-lamp"]), r["brand"].lower(), r["name"].lower()))
    payload = {"title": "Lighting review", "types": TYPES, "none": "Not a lamp", "acc": "Part (bulb, shade, cable)",
               "labels": {**dict(TYPES), "part": "Part (bulb, shade, cable)", "not-a-lamp": "Not a lamp"}, "items": out}
    (HERE / "lighting_items.json").write_text(json.dumps(payload, ensure_ascii=False))
    print(len(byid), "pieces in the family;", len(out), "to review")
    print(collections.Counter(s for r in out for s in r["suggest"]).most_common())


if __name__ == "__main__":
    build()
