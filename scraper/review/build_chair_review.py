"""Build the review list for the chair family: pieces whose type pages do not match what their name or photo says.

    python3 scraper/review/build_chair_review.py     # writes review/chairs_items.json next to this script

Used by serve_review.py (a local page where each piece is tagged with its right type; the answers are saved to
data/category_review_chairs.json). Nothing here touches the database or the site.
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

FAMILY = ["chairs", "dining-chairs", "armchairs", "side-chairs", "folding-chairs", "kids-chairs", "office-chairs",
          "garden-chairs", "stools", "bar-stools", "benches", "footstools", "ottomans-and-poufs"]
SPECIFIC = [s for s in FAMILY if s != "chairs"]
# what a name can say, in the order they are tried (first hits win within a group)
NAME_TYPES = [
    ("bar-stools", r"bar stool|counter stool|bar chair|counter chair|barstool|barstol|bar-stool"),
    ("footstools", r"footstool|foot stool|footrest|foot rest|fotpall"),
    ("ottomans-and-poufs", r"ottoman|pouf|puff\b|pouffe|hocker"),
    ("stools", r"\bstool|tabouret|taburete|\bkrukke?\b"),
    ("benches", r"bench|\bbanc\b|\bbänk|banco\b|panca"),
    ("kids-chairs", r"\bkids?\b|child|children|baby|junior"),
    ("office-chairs", r"office chair|desk chair|task chair|swivel chair|work ?chair"),
    ("garden-chairs", r"(garden|outdoor|patio|terrace).*(chair|stool)|(chair|stool).*(garden|outdoor|patio|terrace)"),
    ("folding-chairs", r"folding|stacking|stackable|foldable"),
    ("armchairs", r"(?<!dining )(?<!dining)\b(armchair|lounge chair|easy chair|club chair|recliner|rocking chair|fauteuil|bergere|bergère)"),
    ("dining-chairs", r"dining chair|dining armchair"),
    ("side-chairs", r"\bside chair"),
    ("sofas", r"\bsofa\b|\bcouch\b|settee|loveseat|daybed"),
    ("not-a-seat", r"\btable\b|\bshelf\b|\bshelves\b|trolley|\blamp\b|\bmirror\b(?! lounge)"),
]
VISION_TO_SLUG = {"dining chair": "dining-chairs", "armchair": "armchairs", "lounge chair": "armchairs", "side chair": "side-chairs",
                  "office chair": "office-chairs", "garden chair": "garden-chairs", "folding chair": "folding-chairs",
                  "kids chair": "kids-chairs", "stool": "stools", "bench": "benches", "sofa": "sofas", "not_a_chair": "not-a-seat"}
NEAR = {("dining-chairs", "armchairs"), ("armchairs", "dining-chairs"), ("garden-chairs", "dining-chairs"), ("garden-chairs", "armchairs"),
        ("stools", "bar-stools"), ("bar-stools", "stools"), ("footstools", "ottomans-and-poufs"), ("ottomans-and-poufs", "footstools"),
        ("side-chairs", "dining-chairs"), ("dining-chairs", "side-chairs")}


# Pads, covers and spare parts are told apart by their name alone, so they are not sent for review: the rule applies to them directly.
AUTO_ACCESSORY = re.compile(r"\bseat pads?\b|loose cover|\bcover for\b|chair cover|seat cover|stool cover|bench cover|swatch", re.I)
# Spare parts (feet glides and sliders, wall brackets, adjustment kits) are dropped from the site altogether, like the other spare-part listings.
AUTO_SPARE_PART = re.compile(r"\bglides?\b|\bsliders?\b|wall mount for|height adjustment kit|\bspare\b|replacement (part|leg|foot)", re.I)


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
    vision = json.loads((ROOT / "data" / "chair_vision_labels.json").read_text())
    out, auto = [], []
    for pid, p in byid.items():
        have = pages[pid]
        rule = "spare part" if AUTO_SPARE_PART.search(p["product_name"]) else "accessory" if AUTO_ACCESSORY.search(p["product_name"]) else None
        if rule:
            auto.append({"id": pid, "rule": rule, "brand": p["brand"], "name": p["product_name"], "tag": p["category"] or "", "pages": sorted(have)})
            continue
        nt = name_types(p["product_name"])
        reasons, suggest = [], []
        for t in nt:
            if t == "sofas" and re.search(r"sofa|couch|daybed|loveseat|settee", p["category"] or "", re.I):
                continue
            if t == "ottomans-and-poufs" and re.search(r"chair|sofa|bench", p["product_name"], re.I):
                continue
            if t == "accessory":
                reasons.append("The name looks like a pad, cover or spare part")
                suggest.append(t)
            elif t == "not-a-seat":
                reasons.append("The name looks like something that is not seating")
                suggest.append(t)
            elif t == "sofas":
                reasons.append("The name says sofa or daybed")
                suggest.append(t)
            elif t not in have:
                reasons.append(f"The name says {t.replace('-', ' ')}, but it is not on that page")
                suggest.append(t)
        wrong = [s for s in have if s in SPECIFIC and nt and not any(s == t or (s, t) in NEAR for t in nt)]
        if wrong and not suggest:
            reasons.append("It is on " + ", ".join(w.replace("-", " ") for w in wrong) + ", but the name points elsewhere")
            suggest += [t for t in nt if t not in have]
        v = vision.get(str(pid))
        if v and v.get("confidence", 0) >= 0.8:
            vs = VISION_TO_SLUG.get(v["label"])
            if vs and vs not in have and vs not in suggest and not any((vs, h) in NEAR for h in have):
                reasons.append(f"The photo looks like a {v['label']}")
                suggest.append(vs)
        if reasons:
            out.append({"id": pid, "brand": p["brand"], "name": p["product_name"], "tag": p["category"] or "", "url": p["product_url"],
                        "image": p["image_url"], "pages": sorted(have), "reasons": reasons, "suggest": sorted(set(suggest))})
    out.sort(key=lambda r: (r["suggest"][:1] not in (["accessory"], ["not-a-seat"]), r["brand"].lower(), r["name"].lower()))
    (HERE / "chairs_items.json").write_text(json.dumps(out, ensure_ascii=False))
    (HERE / "chairs_auto_accessories.json").write_text(json.dumps(auto, ensure_ascii=False, indent=1))
    print(len(byid), "pieces in the family;", len(auto), "set aside by the name rules;", len(out), "to review")
    print(collections.Counter(s for r in out for s in r["suggest"]).most_common())


if __name__ == "__main__":
    build()
