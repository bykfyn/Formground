"""
Pick a representative photo for each type tile on the Work category pages (Furniture / Lighting / Objects).

WHY (2026-10-14): a type's tile photo used to be the first card of its list, which is the first brand alphabetically's
first piece. That was often not a typical example: a wall shelf for Desks, a sofa for Beds, a trolley for Sideboards, a
single sofa section for Sofas. This script scores each type's pieces and writes the best few candidates to
data/type_tile_candidates.json; data/type_tile_images.json holds the chosen photo per type (reviewed by eye, see
generate_browse_pages.TYPE_TILE_IMAGE which reads it).

A candidate is a piece whose own category tag IS the type (not a multi-tag breadcrumb string), whose name is not a part or an
accessory, and whose photo is a clean, whole-product shot: a plain light background, the piece centred with margin around it,
a near-square frame, not a close-up and not a room scene. Scores come from a small thumbnail of each photo (cached in
data/type_tile_cache.json, so reruns only fetch new photos).

    python3 pick_type_tile_images.py                 # score and write the candidates file
    python3 pick_type_tile_images.py --slug sofas    # one type only
"""

import argparse
import concurrent.futures as cf
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
import requests
from PIL import Image

SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR))
sys.path.insert(0, str(SCRAPER_DIR.parent / "backend"))

DATA = SCRAPER_DIR.parent / "data"
CACHE_PATH = DATA / "type_tile_cache.json"
CANDIDATES_PATH = DATA / "type_tile_candidates.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
PART_WORDS = re.compile(r"\b(leg|legs|cushion|cover|spare|part|swatch|sample|gift|voucher|set of|replacement|pad|seat pad)\b", re.I)


def _load_cache():
    return json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


def analyze(url):
    """Metrics for one photo from a small thumbnail, or None if it cannot be fetched."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        im = Image.open(io.BytesIO(r.content))
        if im.mode in ("RGBA", "LA", "P"):                       # transparent photos sit on a light ground
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (244, 244, 242, 255))
            bg.alpha_composite(im)
            im = bg
        im = im.convert("RGB")
        w0, h0 = im.size
        im.thumbnail((180, 180))
    except Exception:
        return None
    a = np.asarray(im).astype("float32")
    h, w = a.shape[:2]
    m = max(2, int(min(h, w) * 0.07))
    border = np.concatenate([a[:m].reshape(-1, 3), a[-m:].reshape(-1, 3), a[:, :m].reshape(-1, 3), a[:, -m:].reshape(-1, 3)])
    bg_col = np.median(border, axis=0)
    border_std = float(border.std(axis=0).mean())
    diff = np.abs(a - bg_col).sum(axis=2) > 45
    ys, xs = np.where(diff)
    if len(xs) < 20:
        return {"ratio": w0 / h0, "border_std": border_std, "bg": float(bg_col.mean()), "fill_w": 0, "fill_h": 0, "area": 0, "off": 1, "margin": 0}
    x0, x1, y0, y1 = xs.min() / w, xs.max() / w, ys.min() / h, ys.max() / h
    return {
        "ratio": round(w0 / h0, 3), "border_std": round(border_std, 1), "bg": round(float(bg_col.mean()), 1),
        "fill_w": round(float(x1 - x0), 3), "fill_h": round(float(y1 - y0), 3), "area": round(float(diff.mean()), 3),
        "off": round(float(max(abs((x0 + x1) / 2 - 0.5), abs((y0 + y1) / 2 - 0.5))), 3),
        "margin": round(float(min(x0, 1 - x1, y0, 1 - y1)), 3),
    }


def score(m):
    """Higher = a cleaner, more typical whole-product tile photo."""
    if not m:
        return -99
    s = 0.0
    s += 3 if (m["border_std"] < 14 and m["bg"] > 205) else (1 if m["border_std"] < 22 else -3)       # plain light ground
    biggest = max(m["fill_w"], m["fill_h"])
    s += 2 if 0.55 <= biggest <= 0.9 else (-2 if biggest > 0.97 or biggest < 0.3 else 0)             # whole piece, with margin
    s += 1 if m["margin"] >= 0.03 else -1
    s += 1 if m["off"] < 0.1 else 0
    s += 1 if 0.75 <= m["ratio"] <= 1.34 else -1
    s += 1 if 0.08 <= m["area"] <= 0.6 else -1                                                         # not tiny, not all frame
    return s


def canonical_names(category):
    names = set()
    for intent in (category.get("intents") or [category["intent"]]):
        c = (intent.get("category") or "").lower()
        if c:
            names |= {c, c + "s", c.rstrip("s")}
    if category["slug"] == "ottomans-and-poufs":
        names |= {"ottoman", "ottomans", "pouf", "poufs"}
    return names


def candidates_for(category, cache, per_type=40):
    import generate_browse_pages as g
    from generate_theme_landing_pages import _group_color_variants
    products = g._category_products(category)
    cards, _ = _group_color_variants(products)
    names = canonical_names(category)
    pool, seen_brands = [], set()
    for p in g._interleave_by_brand(cards):
        cat = (p.get("category") or "").lower().strip()
        if cat not in names or PART_WORDS.search(p["product_name"]) or not p.get("image_url"):
            continue
        if p["brand"] in seen_brands and len(pool) >= per_type // 2:
            continue
        seen_brands.add(p["brand"])
        pool.append(p)
        if len(pool) >= per_type:
            break
    need = [p["image_url"] for p in pool if p["image_url"] not in cache]
    with cf.ThreadPoolExecutor(8) as ex:
        for url, metrics in zip(need, ex.map(analyze, need)):
            cache[url] = metrics
    ranked = sorted(pool, key=lambda p: (-score(cache.get(p["image_url"])), p["brand"].lower()))
    return [{"brand": p["brand"], "name": p["product_name"], "image": p["image_url"], "score": score(cache.get(p["image_url"])),
             "metrics": cache.get(p["image_url"])} for p in ranked[:8]], len(products)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    args = ap.parse_args()
    import generate_browse_pages as g
    cache = _load_cache()
    out = json.loads(CANDIDATES_PATH.read_text()) if CANDIDATES_PATH.exists() and args.slug else {}
    for category in g.BROWSE_CATEGORIES:
        if args.slug and category["slug"] != args.slug:
            continue
        cands, total = candidates_for(category, cache)
        out[category["slug"]] = {"title": category["title"], "total": total, "candidates": cands}
        print(f"{category['slug']:22} {total:5} pieces  top: {cands[0]['brand'] + ' | ' + cands[0]['name'] if cands else '-'}")
        CACHE_PATH.write_text(json.dumps(cache))
    CANDIDATES_PATH.write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
