"""Tier 2 for tables: label tables that carry only a generic tag ("table", "tables", "small tables", ...)
by looking at the photo plus the name. Same flow as classify_chairs_vision.py (dry run writes
data/table_vision_labels.json; `--apply` prepends the type tag, e.g. "coffee table, Tables").

    python3 classify_tables_vision.py --limit 40
    python3 classify_tables_vision.py
    python3 classify_tables_vision.py --apply
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import classify_chairs_vision as base  # noqa: E402

ROOT = base.ROOT
DB = base.DB
LABELS = ROOT / "data" / "table_vision_labels.json"
LABEL_SET = ["dining table", "coffee table", "side table", "console table", "desk", "bedside table",
             "bar table", "outdoor table", "other table", "not_a_table", "unsure"]
APPLY_AS = {"dining table", "coffee table", "side table", "console table", "desk", "bedside table",
            "outdoor table"}
SECOND_MODEL = "claude-sonnet-5-5"
MIN_CONFIDENCE = 0.9  # tables: the 0.85 bucket was wrong about a quarter of the time in the hand check

GENERIC = {"table", "tables", "tavoli", "small tables", "tables and complements", "low tables",
           "lounge tables", "tavolini", "tavolo"}
SPECIFIC = re.compile(r"dining|coffee|side|console|bedside|bar table|desk|dressing|end table|nightstand|"
                      r"night stand|sideboard|work ?table|picnic|garden|outdoor|conference|kitchen|nesting|"
                      r"cocktail|pedestal|trestle|folding|vanity|bistro|tisch|mesa|lamp|ware|linen|runner|"
                      r"cloth|placemat|tray", re.I)
NOT_A_TABLE_NAME = re.compile(r"lamp|lantern|linen|runner|cloth|placemat|napkin|candle|vase|bowl|plate|rug|"
                              r"cushion|\bchair\b|stool|sofa|bench|mirror|pendant|sconce|light", re.I)

PROMPT = (
    "Product name: {name}\n\n"
    "What kind of table is this? Pick exactly one label from: {labels}.\n"
    "The product name is a strong hint (\"Atlas Dining Table\" is a dining table); use the photo to decide when the "
    "name does not say. Judge by size and height in the photo.\n"
    "- dining table: seats people at a meal, standard table height, usually large\n"
    "- coffee table: low table in front of a sofa\n"
    "- side table: small table beside a sofa or chair, an end table, or a small accent table\n"
    "- console table: long narrow table against a wall\n"
    "- desk: writing/work desk\n"
    "- bedside table: nightstand\n"
    "- bar table: tall counter or bar-height table\n"
    "- outdoor table: garden or patio table\n"
    "- other table: a table that fits none of these\n"
    "- not_a_table: lamp, linen, tableware, chair, accessory, anything that is not a table\n"
    "- unsure: the photo does not settle it\n"
    'Reply with JSON only: {{"label": "...", "confidence": 0.0-1.0}}'
)


def confident(res):
    """First pass: 0.9+. Second-pass items (the first pass was unsure): the stronger model at 0.9+, or at
    0.75+ when it agrees with the first model - hand-checked 2026-10-04, about nine in ten right."""
    if res["confidence"] >= MIN_CONFIDENCE:
        return True
    return "second" in res and res["label"] == (res.get("first") or {}).get("label") and res["confidence"] >= 0.75


def pool(conn):
    rows = conn.execute("SELECT id, brand, product_name, category, image_url FROM products "
                        "WHERE link_dead=0 AND image_url IS NOT NULL AND image_url != ''").fetchall()
    out = []
    for pid, brand, name, cat, img in rows:
        tags = [t.strip().lower() for t in (cat or "").split(",") if t.strip()]
        if not any(t in GENERIC for t in tags) or any(SPECIFIC.search(t) for t in tags):
            continue
        if NOT_A_TABLE_NAME.search(name or ""):
            continue
        out.append({"id": pid, "brand": brand, "name": name, "category": cat, "image_url": img})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--second-pass", action="store_true",
                    help="re-label the items the first pass was not sure about (below 0.9) with a stronger model")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}

    if args.apply:
        n = 0
        for pid, res in labels.items():
            if res["label"] in APPLY_AS and confident(res):
                cat = conn.execute("SELECT category FROM products WHERE id=?", (int(pid),)).fetchone()[0]
                if cat and cat.lower().startswith(res["label"]):
                    continue
                conn.execute("UPDATE products SET category=? WHERE id=?", (f'{res["label"]}, {cat}', int(pid)))
                n += 1
        conn.commit()
        print(f"applied {n} labels")
        return

    if args.second_pass:
        # Only items the first (Haiku) pass left unapplied; the answer replaces it, the old one is kept.
        by_id = {str(i["id"]): i for i in pool(conn)}
        todo = [by_id[k] for k, v in labels.items()
                if k in by_id and v["confidence"] < MIN_CONFIDENCE
                and ("second" not in v or v["label"] == "error")]
    else:
        todo = [i for i in pool(conn) if str(i["id"]) not in labels or labels[str(i["id"])]["label"] == "error"]
    if args.limit:
        todo = todo[: args.limit]
    key = base.load_key()
    print(f"{len(todo)} tables to classify")
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        model = SECOND_MODEL if args.second_pass else None
        for n, (item, res) in enumerate(
                zip(todo, ex.map(lambda i: base.classify(i, key, PROMPT, LABEL_SET, model), todo)), 1):
            old = labels.get(str(item["id"]), {})
            first = old.get("first") or {"label": old.get("label"), "confidence": old.get("confidence")}
            extra = {"second": model, "first": first} if args.second_pass else {}
            labels[str(item["id"])] = {**res, "brand": item["brand"], "name": item["name"],
                                       "image_url": item["image_url"], **extra}
            if n % 50 == 0:
                LABELS.write_text(json.dumps(labels, indent=1))
                print(f"  {n}/{len(todo)}  {time.time() - t0:.0f}s")
    LABELS.write_text(json.dumps(labels, indent=1))
    c = Counter((r["label"], r["confidence"] >= MIN_CONFIDENCE) for r in labels.values())
    for (label, ok), k in sorted(c.items(), key=lambda x: -x[1]):
        print(f"  {label:14} {'confident' if ok else 'low':9} {k}")


if __name__ == "__main__":
    main()
