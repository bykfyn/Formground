"""Build the review list for storage, beds and mirrors: pieces whose type pages do not match what their name says.

    python3 scraper/review/build_storage_review.py     # writes review/storage_items.json next to this script

Shown at http://localhost:8094/?family=storage; answers go to data/category_review_storage.json (see apply_storage_review.py).
Name is the only signal (no photo labels exist for these types).
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

FAMILY = ["sideboards", "cabinets", "shelving", "beds", "mirrors"]
TYPES = [("sideboards", "Sideboard"), ("cabinets", "Cabinet / wardrobe"), ("shelving", "Shelving / bookcase"), ("beds", "Bed"), ("mirrors", "Mirror"),
         ("console-tables", "Console table"), ("bedside-tables", "Bedside table"), ("desks", "Desk")]
NAME_TYPES = [
    ("bedside-tables", r"bedside|night ?stand"),
    ("sideboards", r"sideboard|\bbuffet\b|credenza"),
    ("cabinets", r"\bcabinet\b|cupboard|wardrobe|armoire|chest of drawers|highboard|vitrine|\bdresser\b|\blocker\b|\btallboy\b"),
    ("shelving", r"\bshel(f|ves|ving)\b|bookcase|book ?shelf|\brack\b|\bladder\b"),
    ("beds", r"(?<!day)(?<!sofa)(?<!bed ) ?\bbed\b(?! ?side)|\bbunk\b|\bcot\b|\bcrib\b|headboard"),
    ("mirrors", r"\bmirror\b"),
    ("console-tables", r"\bconsole\b"),
    ("desks", r"\bdesk\b"),
    ("bed-extra", r"bed (runner|canopy|expander|end bench|sheet|linen|spread|set)|doll'?s? bed|\bdogs? bed|\bpet bed|\bcat bed|\bbed side table"),
    ("part", r"\bspare\b|replacement|\bmattress\b|bed ?linen|\bbedding\b|\bslats?\b|\bhinge\b|\bhandle\b|\bknob\b|\bmirror (glass|frame only)\b"),
    ("not-storage", r"\blamp\b|\bchair\b|\bstool\b|\bsofa\b|\brug\b|\bvase\b|\bpendant\b|\bplate\b|\bbowl\b"),
]
NEAR = {("sideboards", "cabinets"), ("cabinets", "sideboards"), ("cabinets", "shelving"), ("shelving", "cabinets"), ("sideboards", "shelving"),
        ("shelving", "sideboards"), ("sideboards", "console-tables"), ("console-tables", "sideboards"), ("cabinets", "bedside-tables"),
        ("bedside-tables", "cabinets"), ("mirrors", "cabinets"), ("cabinets", "mirrors"), ("beds", "bedside-tables"), ("bedside-tables", "beds")}
LABELS = {"part": "an accessory or spare part (mattress, slats, handle)", "not-storage": "not storage, a bed or a mirror (a lamp, chair or similar)"}


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
        types_in_name = [t for t in nt if t not in ("part", "not-storage", "bed-extra")]
        if "bed-extra" in nt:
            types_in_name = [t for t in types_in_name if t != "beds"]
        reasons, suggest = [], []
        for t in nt:
            if t == "bed-extra":
                reasons.append("The name looks like a bed accessory, a pet bed or a toy bed, not a bed")
                suggest.append("part")
                continue
            if t in ("part", "not-storage"):
                if t == "not-storage" and types_in_name:
                    continue
                reasons.append("The name looks like " + LABELS[t])
                suggest.append(t)
        wrong = [s for s in have if types_in_name and not any(s == t or (s, t) in NEAR for t in types_in_name)]
        if wrong:
            reasons.append("It is on " + ", ".join(w.replace("-", " ") for w in wrong) + ", but the name points to " + ", ".join(t.replace("-", " ") for t in types_in_name))
            suggest += [t for t in types_in_name if t not in have]
        if "beds" in have and not re.search(r"\bbeds?\b|day ?bed|\bcama\b|\bbunk\b|headboard|settee|\bsofa\b", p["product_name"].lower()) and not suggest:
            reasons.append("It is on Beds but the name does not say bed: check the photo")
        if reasons:
            out.append({"id": pid, "brand": p["brand"], "name": p["product_name"], "tag": p["category"] or "", "url": p["product_url"],
                        "image": p["image_url"], "pages": sorted(have), "reasons": reasons, "suggest": sorted(set(suggest))})
    out.sort(key=lambda r: (r["suggest"][:1] not in (["part"], ["not-storage"]), r["brand"].lower(), r["name"].lower()))
    payload = {"title": "Storage review", "types": TYPES, "none": "Not storage / bed / mirror", "acc": "Accessory (mattress, slats, part)",
               "labels": {**dict(TYPES), "part": "Accessory (mattress, slats, part)", "not-storage": "Not storage"}, "items": out}
    (HERE / "storage_items.json").write_text(json.dumps(payload, ensure_ascii=False))
    print(len(byid), "pieces in the family;", len(out), "to review")
    print(collections.Counter(s for r in out for s in r["suggest"]).most_common())


if __name__ == "__main__":
    build()
