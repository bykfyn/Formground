"""Build the review list for the table family: pieces whose type pages do not match what their name or photo says.

    python3 scraper/review/build_table_review.py     # writes review/tables_items.json next to this script

Same flow as build_chair_review.py; serve_review.py shows it at http://localhost:8094/?family=tables and saves the answers
to data/category_review_tables.json.
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

FAMILY = ["dining-tables", "coffee-tables", "side-tables", "console-tables", "bedside-tables", "outdoor-tables", "bar-tables", "desks"]
TYPES = [("dining-tables", "Dining table"), ("coffee-tables", "Coffee table"), ("side-tables", "Side table"), ("console-tables", "Console table"),
         ("bedside-tables", "Bedside table"), ("outdoor-tables", "Outdoor table"), ("bar-tables", "Bar / counter table"), ("desks", "Desk")]
NAME_TYPES = [
    ("bar-tables", r"\bbar table|\bcounter table|bar height table|counter height table"),
    ("bedside-tables", r"bedside|night ?stand"),
    ("console-tables", r"\bconsole\b"),
    ("coffee-tables", r"coffee table|cocktail table|\bsofa table|lounge table"),
    ("side-tables", r"\bside table|\bend table|occasional table|nesting table|accent table"),
    ("dining-tables", r"dining table|kitchen table|\bdining\b.*\btable|\btable\b.*\bdining\b"),
    ("outdoor-tables", r"(outdoor|garden|patio|terrace).*\btable|\btable.*(outdoor|garden|patio|terrace)"),
    ("desks", r"\bdesk\b|writing table|secretaire|secrétaire"),
    ("part", r"table ?top\b(?! lamp)(?! in\b)|\btable legs?\b(?! in\b)|\blegs? for\b|table base\b(?! in\b)|base for table|\bleg set\b|replacement|\bspare\b"),
    ("not-a-table", r"\blamp\b(?! (side |end )?table)(?<!table & lamp)(?<!table and lamp)|\bchair\b|\bstool\b|\bbench\b|\bsofa\b(?! (side |end )?table)|\bshelf\b|\bmirror\b|\bvase\b|\bcandle"),
]
VISION_TO_SLUG = {"dining table": "dining-tables", "coffee table": "coffee-tables", "side table": "side-tables", "console table": "console-tables",
                  "desk": "desks", "bedside table": "bedside-tables", "bar table": "bar-tables", "outdoor table": "outdoor-tables",
                  "not_a_table": "not-a-table"}
NEAR = {("coffee-tables", "side-tables"), ("side-tables", "coffee-tables"), ("console-tables", "side-tables"), ("side-tables", "console-tables"),
        ("bedside-tables", "side-tables"), ("side-tables", "bedside-tables"), ("dining-tables", "outdoor-tables"), ("outdoor-tables", "dining-tables"),
        ("console-tables", "desks"), ("desks", "console-tables"), ("coffee-tables", "outdoor-tables"), ("side-tables", "outdoor-tables"),
        ("bar-tables", "dining-tables"), ("dining-tables", "bar-tables"), ("dining-tables", "desks"), ("desks", "dining-tables")}
LABELS = {"part": "a table part (top, base, legs)", "not-a-table": "not a table"}


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
    vision = json.loads((ROOT / "data" / "table_vision_labels.json").read_text())
    out = []
    for pid, p in byid.items():
        have = pages[pid]
        nt = name_types(p["product_name"])
        reasons, suggest = [], []
        for t in nt:
            if t in ("part", "not-a-table"):
                reasons.append("The name looks like " + LABELS[t])
                suggest.append(t)
            elif t not in have and not any((t, h) in NEAR for h in have):
                reasons.append(f"The name says {t.replace('-', ' ')}, but it is not on that page")
                suggest.append(t)
        wrong = [s for s in have if nt and not any(s == t or (s, t) in NEAR for t in nt if t not in ("part", "not-a-table"))
                 and any(t not in ("part", "not-a-table") for t in nt)]
        if wrong and not suggest:
            reasons.append("It is on " + ", ".join(w.replace("-", " ") for w in wrong) + ", but the name points elsewhere")
            suggest += [t for t in nt if t not in have and t not in ("part", "not-a-table")]
        v = vision.get(str(pid))
        if v and v.get("confidence", 0) >= 0.85 and v.get("label") in VISION_TO_SLUG:
            vs = VISION_TO_SLUG[v["label"]]
            if vs not in have and vs not in suggest and not any((vs, h) in NEAR for h in have):
                reasons.append(f"The photo looks like a {v['label']}" if vs != "not-a-table" else "The photo does not look like a table")
                suggest.append(vs)
        if reasons:
            out.append({"id": pid, "brand": p["brand"], "name": p["product_name"], "tag": p["category"] or "", "url": p["product_url"],
                        "image": p["image_url"], "pages": sorted(have), "reasons": reasons, "suggest": sorted(set(suggest))})
    out.sort(key=lambda r: (r["suggest"][:1] not in (["part"], ["not-a-table"]), r["brand"].lower(), r["name"].lower()))
    payload = {"title": "Tables review", "types": TYPES, "labels": {**dict(TYPES), "part": "Part (top, base, legs)", "not-a-table": "Not a table", "tables": "Tables"},
               "items": out}
    (HERE / "tables_items.json").write_text(json.dumps(payload, ensure_ascii=False))
    print(len(byid), "pieces in the family;", len(out), "to review")
    print(collections.Counter(s for r in out for s in r["suggest"]).most_common())


if __name__ == "__main__":
    build()
