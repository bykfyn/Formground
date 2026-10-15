"""Build the review list for the Sofas page: pieces on it whose name says they are something else.

    python3 scraper/review/build_sofa_review.py     # writes review/sofas_items.json next to this script

Shown at http://localhost:8094/?family=sofas; answers go to data/category_review_sofas.json (see apply_sofa_review.py).
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "backend"))
import generate_browse_pages as g  # noqa: E402

TYPES = [("sofas", "Sofa / daybed"), ("armchairs", "Armchair / lounge"), ("benches", "Bench"), ("ottomans-and-poufs", "Ottoman / pouf"),
         ("footstools", "Footstool"), ("stools", "Stool"), ("beds", "Bed"), ("coffee-tables", "Coffee table"), ("side-tables", "Side table")]
# what the name says it is; a name that also says sofa ("Another Sofa & Armchair", "Sofa Eight Table") is judged by the review
NAME_TYPES = [
    ("part", r"\bsofa cover\b|^cover\b|\bcover\b(?! medium)|\bthrow\b|\bcushion\b(?! incl)|\bpillow\b(?! \d)|\bspare\b|replacement|swatch|\bsample\b|\bleg(s)?\b$"),
    ("beds", r"\bsofa bed\b|\bbed ?settee\b|\bbed\b"),
    ("armchairs", r"\barm ?chair\b|\blounge chair\b|\bfireside chair\b|\bchair\b"),
    ("benches", r"\bbench\b"),
    ("ottomans-and-poufs", r"\bottoman\b|\bpouf\b"),
    ("stools", r"\bstool\b"),
    ("coffee-tables", r"coffee table"),
    ("side-tables", r"side table|\btable\b"),
]


def build():
    cat = next(c for c in g.BROWSE_CATEGORIES if c["slug"] == "sofas")
    out = []
    for p in g._category_products(cat):
        name = p["product_name"]
        low = name.lower()
        has_sofa = bool(re.search(r"\bsofa\b|\bsettee\b|\bcouch\b|\bloveseat\b|\bdaybed\b|\bsectional\b|\bmodular\b|\bseater\b", low))
        suggest, reasons = [], []
        for slug, rx in NAME_TYPES:
            if re.search(rx, low):
                if slug == "part" and has_sofa and "cover" not in low:
                    continue
                suggest.append(slug)
                reasons.append("The name looks like " + ("a cover, cushion or part" if slug == "part" else slug.replace("-", " ").rstrip("s")))
        if not suggest:
            continue
        out.append({"id": p["id"], "brand": p["brand"], "name": name, "tag": p["category"] or "", "url": p["product_url"], "image": p["image_url"],
                    "pages": ["sofas"], "reasons": reasons, "suggest": sorted(set(suggest))})
    out.sort(key=lambda r: (r["brand"].lower(), r["name"].lower()))
    labels = {**dict(TYPES), "part": "Accessory (cover, cushion, part)"}
    payload = {"title": "Sofas review", "types": TYPES, "none": "Not seating at all", "acc": "Accessory (cover, cushion, part)", "labels": labels, "items": out}
    (HERE / "sofas_items.json").write_text(json.dumps(payload, ensure_ascii=False))
    print(len(out), "to review")


if __name__ == "__main__":
    build()
