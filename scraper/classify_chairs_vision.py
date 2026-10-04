"""Tier 2 of chair sub-typing: label chairs that still carry only a generic tag by LOOKING at the photo.

Pool = chairs where scrape._refine_chair_subtype found nothing to read in the name (generic tag only,
no specific chair tag). Each photo (resized to card width) plus the product name goes to Haiku, which
answers with one label from a fixed list, a confidence and "not_a_chair" for things like cushions.

Default is a dry run that writes data/chair_vision_labels.json for review; nothing touches the DB.
`--apply` prepends the sub-type tag (same form as the name-based refinement) to rows whose label is
confident. Results are cached in the JSON so re-runs only pay for new rows.

    python3 classify_chairs_vision.py --limit 40      # try a few
    python3 classify_chairs_vision.py                 # whole pool, writes labels file
    python3 classify_chairs_vision.py --apply         # apply confident labels from the file
"""
import argparse
import base64
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import image_sizes  # noqa: E402
import scrape  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "formground.db"
LABELS = ROOT / "data" / "chair_vision_labels.json"
MODEL = "claude-haiku-4-5-20251001"
LABEL_SET = ["dining chair", "armchair", "lounge chair", "side chair", "office chair", "garden chair",
             "folding chair", "rocking chair", "kids chair", "stool", "bench", "sofa", "not_a_chair", "unsure"]
# Labels that map onto a chair tag we already use; the others are reported but never applied.
APPLY_AS = {"dining chair", "armchair", "lounge chair", "side chair", "office chair", "garden chair",
            "folding chair", "rocking chair", "kids chair"}
MIN_CONFIDENCE = 0.8
# Hand-checked 2026-10-04: the model called these garden chairs at 0.85 but they are indoor designs.
NOT_GARDEN = {("A. Petersen", "Wire Chair"), ("Galerie Kreo", "Wicker Chair"), ("Ferm Living", "Dapple Chair with Arms"),
              ("Thorup Copenhagen", "Noel Armrest Chair"), ("Artek", "Rope Chair"), ("Lland", "Masonry Chair"),
              ("Piet Hein Eek", "Aluminium stoel"), ("Piet Hein Eek", "Even-dik-en-breed stoel"),
              ("Desalto", "Softer than Steel - Sedia"), ("Ligne Roset", "Lapel Carver chair")}

PROMPT = (
    "Product name: {name}\n\n"
    "What kind of chair is this? Pick exactly one label from: {labels}.\n"
    "- dining chair: upright chair meant for a dining table, no arms or with light arms\n"
    "- armchair: upholstered or framed chair with arms, relaxed seating\n"
    "- lounge chair: low, reclined seating (club, easy, wing, slipper, lounge)\n"
    "- side chair: occasional/accent chair without arms\n"
    "- office chair: task chair on a base/castors or desk chair\n"
    "- garden chair: outdoor chair (rattan weave, teak, metal garden furniture)\n"
    "- folding chair: visibly folding or stacking chair\n"
    "- rocking chair: on rockers\n"
    "- kids chair: child-size\n"
    "- stool/bench/sofa: it is one of those, not a chair\n"
    "- not_a_chair: cushion, part, accessory, other\n"
    "- unsure: the photo does not settle it\n"
    'Reply with JSON only: {{"label": "...", "confidence": 0.0-1.0}}'
)


def pool(conn):
    rows = conn.execute(
        "SELECT id, brand, product_name, category, image_url FROM products "
        "WHERE link_dead=0 AND image_url IS NOT NULL AND image_url != ''"
    ).fetchall()
    out = []
    for pid, brand, name, cat, img in rows:
        tags = [t.strip() for t in (cat or "").split(",") if t.strip()]
        lowered = [t.lower() for t in tags]
        if not any(t in scrape.CHAIR_GENERIC_TAGS for t in lowered):
            continue
        if any(scrape.CHAIR_SPECIFIC_RE.search(t) for t in lowered):
            continue
        if scrape.CHAIR_NOT_A_CHAIR_RE.search(name or ""):
            continue
        if scrape._refine_chair_subtype(name, cat) != cat:
            continue  # the name already decides it
        out.append({"id": pid, "brand": brand, "name": name, "category": cat, "image_url": img})
    return out


def classify(item, key):
    try:
        url = image_sizes.sized(item["image_url"], image_sizes.CARD)
        r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (Formground classifier)"})
        r.raise_for_status()
        media = r.headers.get("content-type", "image/jpeg").split(";")[0]
        if not media.startswith("image/") or media == "image/svg+xml":
            return {"label": "unsure", "confidence": 0, "error": f"bad media {media}"}
        data = base64.standard_b64encode(r.content).decode("ascii")
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": MODEL, "max_tokens": 60, "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                {"type": "text", "text": PROMPT.format(name=item["name"], labels=", ".join(LABEL_SET))},
            ]}]},
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip()
        text = text[text.find("{"): text.rfind("}") + 1]
        parsed = json.loads(text)
        label = str(parsed.get("label", "unsure")).lower()
        if label not in LABEL_SET:
            label = "unsure"
        return {"label": label, "confidence": float(parsed.get("confidence", 0))}
    except Exception as e:  # leave it unlabelled; a re-run retries it
        return {"label": "error", "confidence": 0, "error": str(e)[:120]}


def load_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env = ROOT / "backend" / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("no ANTHROPIC_API_KEY")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}

    if args.apply:
        n = 0
        for pid, res in labels.items():
            if res["label"] == "garden chair" and (res["brand"], res["name"]) in NOT_GARDEN:
                continue
            if res["label"] in APPLY_AS and res["confidence"] >= MIN_CONFIDENCE:
                cat = conn.execute("SELECT category FROM products WHERE id=?", (int(pid),)).fetchone()[0]
                if cat and cat.lower().startswith(res["label"]):
                    continue
                conn.execute("UPDATE products SET category=? WHERE id=?", (f'{res["label"]}, {cat}', int(pid)))
                n += 1
        conn.commit()
        print(f"applied {n} labels")
        return

    todo = [i for i in pool(conn) if str(i["id"]) not in labels or labels[str(i["id"])]["label"] == "error"]
    if args.limit:
        todo = todo[: args.limit]
    key = load_key()
    print(f"{len(todo)} chairs to classify")
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        for n, (item, res) in enumerate(zip(todo, ex.map(lambda i: classify(i, key), todo)), 1):
            labels[str(item["id"])] = {**res, "brand": item["brand"], "name": item["name"],
                                       "image_url": item["image_url"]}
            if n % 50 == 0:
                LABELS.write_text(json.dumps(labels, indent=1))
                print(f"  {n}/{len(todo)}  {time.time() - t0:.0f}s")
    LABELS.write_text(json.dumps(labels, indent=1))
    from collections import Counter
    c = Counter((r["label"], r["confidence"] >= MIN_CONFIDENCE) for r in labels.values())
    for (label, ok), k in sorted(c.items(), key=lambda x: -x[1]):
        print(f"  {label:14} {'confident' if ok else 'low':9} {k}")


if __name__ == "__main__":
    main()
