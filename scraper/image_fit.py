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
    raw = Image.open(io.BytesIO(r.content))
    ratio = raw.width / raw.height
    rgba = raw.convert("RGBA")
    small = rgba.resize((64, max(8, round(64 / ratio))))
    w, h = small.size
    px = small.load()
    coords = [(x, y) for x in range(w) for y in (0, 1, h - 2, h - 1)] + [(x, y) for y in range(h) for x in (0, 1, w - 2, w - 1)]
    edge_px = [px[x, y] for x, y in coords]
    # A cut-out PNG/WebP has transparent edges: flattening that to RGB gives black
    # (several packshots were wrongly read as black-edged). Report it as
    # "transparent" so no fill is painted and the card's own surface shows.
    if sum(1 for p in edge_px if p[3] < 128) / len(edge_px) > 0.5:
        return {"ratio": round(ratio, 3), "bg": "transparent", "edge_std": 0.0}
    edge = [p[:3] for p in edge_px]
    n = len(edge)
    mean = [sum(p[c] for p in edge) / n for c in range(3)]
    std = max((sum((p[c] - mean[c]) ** 2 for p in edge) / n) ** 0.5 for c in range(3))
    out = {"ratio": round(ratio, 3), "bg": "#%02x%02x%02x" % tuple(round(v) for v in mean), "edge_std": round(std, 1)}
    box = _subject_box(rgba, ratio, mean) if std <= FLAT_EDGE_MAX else None
    if box:
        out["box"] = box
    return out


def _subject_box(rgba, ratio, bg):
    """(left, top, right, bottom) of everything that differs clearly from the flat background, as shares of the
    photo; None when nothing stands out. A soft shadow is below the threshold on purpose."""
    small = rgba.resize((96, max(12, round(96 / ratio))))
    w, h = small.size
    px = small.load()
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) > 38:
                xs.append(x)
                ys.append(y)
    if len(xs) < 6:
        return None
    return [round(min(xs) / w, 3), round(min(ys) / h, 3), round((max(xs) + 1) / w, 3), round((max(ys) + 1) / h, 3)]


def analyze(url, fetch_url=None):
    """fetch_url: a smaller copy of the same photo to measure (the cache is still keyed by `url`)."""
    cache = _load()
    if url not in cache:
        try:
            cache[url] = _measure(fetch_url or url)
        except Exception as e:  # noqa: BLE001 - any failure just means "crop as before"
            print(f"  image_fit: could not analyze {url[:70]} ({type(e).__name__})")
            return None
        CACHE_PATH.write_text(json.dumps(cache, indent=1, sort_keys=True))
    return cache[url]


TILE_SQUARE_RANGE = (0.9, 1.12)


def _bg_style(info):
    return "" if info["bg"] == "transparent" else f"background:{info['bg']}"


def fit_for_tile(url, force=False):
    """Same idea for the square edit cards: a photo clearly wider or taller
    than square, on flat edges, is shown whole on its own edge colour instead
    of being cropped. Near-square or busy photos keep the normal crop."""
    info = analyze(url)
    if not info:
        return "", ""
    off_square = info["ratio"] < TILE_SQUARE_RANGE[0] or info["ratio"] > TILE_SQUARE_RANGE[1]
    if force or (off_square and info["edge_std"] <= FLAT_EDGE_MAX):
        return "fit-contain", _bg_style(info)
    return "", ""


def fit_for_banner(url, force=False):
    info = analyze(url)
    if not info:
        return "", ""
    if force or (info["ratio"] < LANDSCAPE_MIN and info["edge_std"] <= FLAT_EDGE_MAX):
        return "fit-contain", _bg_style(info)
    if info["ratio"] < LANDSCAPE_MIN:
        print(f"  image_fit: {url[:70]} is portrait/square (ratio {info['ratio']}) with a busy background - banner will crop it; consider another image")
    return "", ""


# Hand-set crops for photos the automatic fit cannot judge (a busy backdrop), keyed by the photo URL: the square window's
# object-position. Used on every card that shows the photo (type pages, Edits).
MANUAL_CARD_POSITION = {
    # the lamp spans 28-86% of the photo's height, so the square window has to start about a quarter of the way down
    "https://cdn.shopify.com/s/files/1/0177/8296/files/GB_Nov2024_IndiaHobson_LR-108A.jpg?v=1741619890": "50% 71%",
}


def fit_for_card(url):
    """Square product cards (2026-10-11, user: table lamp photos cropped badly). Cache only, never fetches at build
    time: run analyze_card_images.py for a type first. Returns (class, container style, image style).
    A photo clearly taller or wider than square, on flat edges:
      - if the piece fits inside the square window, it stays full-size and the window is moved onto the piece
        (object-position), so nothing is cut off and nothing shrinks;
      - otherwise it is shown whole on its own edge colour (contain).
    Near-square or busy photos keep the normal centred crop."""
    if url in MANUAL_CARD_POSITION:
        return "", "", f"object-position:{MANUAL_CARD_POSITION[url]}"
    info = _load().get(url)
    if not info:
        return "", "", ""
    ratio = info["ratio"]
    if TILE_SQUARE_RANGE[0] <= ratio <= TILE_SQUARE_RANGE[1] or info["edge_std"] > FLAT_EDGE_MAX:
        return "", "", ""
    box = info.get("box")
    if box:
        left, top, right, bottom = box
        if ratio < 1:                       # taller than square: the window is `ratio` of the height
            window, lo, hi = ratio, top, bottom
            fits = (hi - lo) <= window - CARD_MARGIN
            pos = f"50% {_pos(lo, hi, window)}"
        else:                               # wider than square: the window is 1/ratio of the width
            window, lo, hi = 1 / ratio, left, right
            fits = (hi - lo) <= window - CARD_MARGIN
            pos = f"{_pos(lo, hi, window)} 50%"
        if fits:
            return "", "", f"object-position:{pos}"
    return "contain-fit", _bg_style(info), ""


CARD_MARGIN = 0.03          # the piece needs this much air (of the photo's own length) inside the square window


def _pos(lo, hi, window):
    """object-position percentage that centres the span [lo, hi] in a window of the given size (clamped to the photo)."""
    offset = min(max((lo + hi) / 2 - window / 2, 0.0), 1.0 - window)
    return f"{round(100 * offset / (1.0 - window), 1)}%" if window < 1 else "50%"
