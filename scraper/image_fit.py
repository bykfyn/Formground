"""
Build-time image fit for wide banners (2026-10-03).

A banner frame is 2:1, so a portrait or squarish product photo is cropped to a
thin slice of itself (the Apparatus Lantern hero lost most of the lamp). Studio
shots usually sit on a flat background though, so the whole photo can be shown
on a fill matching its own edges and the frame still reads as one image.

analyze(url)  -> {"ratio", "bg", "edge_std"} or None (fetch/decode failure)
fit_for_banner(url, force=False) -> (css_class, inline_style); ("", "") means
    keep the normal full-bleed crop. Contain is chosen when the photo is not
    clearly landscape (ratio < LANDSCAPE_MIN) AND its edges are flat enough
    (edge_std <= FLAT_EDGE_MAX) that the fill is invisible; a busy portrait
    photo is left cropped and reported, since a visible box would look worse.

Results are cached in data/image_fit.json so rebuilds (and CI) do not refetch.
"""

import io
import json
from pathlib import Path

import requests
from PIL import Image

CACHE_PATH = Path(__file__).parent.parent / "data" / "image_fit.json"
LANDSCAPE_MIN = 1.6
FLAT_EDGE_MAX = 22
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://formground.com/"}

_cache = None


def _load():
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    return _cache


def _measure(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    ratio = im.width / im.height
    small = im.resize((64, max(8, round(64 / ratio))))
    w, h = small.size
    px = small.load()
    edge = [px[x, y] for x in range(w) for y in (0, 1, h - 2, h - 1)]
    edge += [px[x, y] for y in range(h) for x in (0, 1, w - 2, w - 1)]
    n = len(edge)
    mean = [sum(p[c] for p in edge) / n for c in range(3)]
    std = max((sum((p[c] - mean[c]) ** 2 for p in edge) / n) ** 0.5 for c in range(3))
    return {"ratio": round(ratio, 3), "bg": "#%02x%02x%02x" % tuple(round(v) for v in mean), "edge_std": round(std, 1)}


def analyze(url):
    cache = _load()
    if url not in cache:
        try:
            cache[url] = _measure(url)
        except Exception as e:  # noqa: BLE001 - any failure just means "crop as before"
            print(f"  image_fit: could not analyze {url[:70]} ({type(e).__name__})")
            return None
        CACHE_PATH.write_text(json.dumps(cache, indent=1, sort_keys=True))
    return cache[url]


TILE_SQUARE_RANGE = (0.9, 1.12)


def fit_for_tile(url, force=False):
    """Same idea for the square edit cards: a photo clearly wider or taller
    than square, on flat edges, is shown whole on its own edge colour instead
    of being cropped. Near-square or busy photos keep the normal crop."""
    info = analyze(url)
    if not info:
        return "", ""
    off_square = info["ratio"] < TILE_SQUARE_RANGE[0] or info["ratio"] > TILE_SQUARE_RANGE[1]
    if force or (off_square and info["edge_std"] <= FLAT_EDGE_MAX):
        return "fit-contain", f"background:{info['bg']}"
    return "", ""


def fit_for_banner(url, force=False):
    info = analyze(url)
    if not info:
        return "", ""
    if force or (info["ratio"] < LANDSCAPE_MIN and info["edge_std"] <= FLAT_EDGE_MAX):
        return "fit-contain", f"background:{info['bg']}"
    if info["ratio"] < LANDSCAPE_MIN:
        print(f"  image_fit: {url[:70]} is portrait/square (ratio {info['ratio']}) with a busy background - banner will crop it; consider another image")
    return "", ""
