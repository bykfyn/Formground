"""
Photo-fit check for the 4:3 frames (Creators page tiles, "In profile" cards, Edit heroes).

A photo is cropped to fill its frame (object-fit: cover). When the photo is not 4:3 and the subject is a product on a
plain background, the crop can cut off legs, edges or the top of the piece. Run this when you add or change a hero:

    python3 scraper/check_image_fit.py            # every profile Edit hero in data/creator_texts.json
    python3 scraper/check_image_fit.py URL [URL]  # specific images

It reports, per image: the aspect ratio, whether the subject would be clipped, and what to do:
  - plain background (the corners match): clipped subjects get `"card_bg": "<colour>"` on the entry's `edit` block,
    which shows the photo whole on that colour (see generate_creators_page.edit_html);
  - busy background (a room, a landscape): not measurable, so it is only listed as "check by eye" when the ratio is
    far from 4:3.
Photos within 8% of 4:3 are fine either way and are not listed.
"""

import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
FRAME = 4 / 3
RATIO_TOLERANCE = 0.08
CLIP_TOLERANCE = 0.02          # share of the subject's extent the crop may remove


def fetch(url):
    from PIL import Image
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def background(im):
    """The corner colour if all four corners agree (a plain background), else None."""
    w, h = im.size
    px = [im.getpixel(p) for p in ((3, 3), (w - 4, 3), (3, h - 4), (w - 4, h - 4))]
    base = px[0]
    if all(max(abs(a - b) for a, b in zip(p, base)) <= 18 for p in px):
        return "#%02x%02x%02x" % tuple(sum(c) // 4 for c in zip(*px))
    return None


def subject_box(im, bg):
    """(left, top, right, bottom) of everything that differs from the background, as shares of the image."""
    import numpy as np
    a = np.asarray(im).astype(int)
    h, w = a.shape[:2]
    # compare each row/column with its own median so a soft gradient backdrop does not count as subject
    diff = (np.abs(a - np.median(a, axis=1, keepdims=True)).max(axis=2) > 28)
    rows = np.where(diff.sum(axis=1) > w * 0.01)[0]
    cols = np.where(diff.sum(axis=0) > h * 0.01)[0]
    if not len(rows) or not len(cols):
        return None
    return cols.min() / w, rows.min() / h, cols.max() / w, rows.max() / h


def clipped_share(im, box):
    """How much of the subject object-fit: cover removes, as a share of the subject's extent (centred crop)."""
    w, h = im.size
    left, top, right, bottom = box
    ratio = w / h
    if ratio > FRAME:                       # wider than the frame: the sides are cut
        keep = FRAME / ratio
        lo, hi = (1 - keep) / 2, (1 + keep) / 2
        lost = max(0, lo - left) + max(0, right - hi)
        return lost / max(right - left, 1e-6)
    keep = ratio / FRAME                    # taller than the frame: top and bottom are cut
    lo, hi = (1 - keep) / 2, (1 + keep) / 2
    lost = max(0, lo - top) + max(0, bottom - hi)
    return lost / max(bottom - top, 1e-6)


def check(label, url):
    try:
        im = fetch(url)
    except Exception as exc:                # noqa: BLE001 - a dead URL is itself worth reporting
        return f"{label}: could not load ({exc})"
    w, h = im.size
    ratio = w / h
    if abs(ratio / FRAME - 1) <= RATIO_TOLERANCE:
        return None
    bg = background(im)
    shape = f"{w}x{h} ({ratio:.2f}, frame is {FRAME:.2f})"
    if bg is None:
        return f"{label}: {shape}, busy background: check by eye"
    box = subject_box(im, bg)
    if box is None:
        return f"{label}: {shape}, plain background, subject not found: check by eye"
    lost = clipped_share(im, box)
    if lost > CLIP_TOLERANCE:
        return f'{label}: {shape} CLIPPED {lost:.0%} of the subject -> add "card_bg": "{bg}" to the edit block'
    return None


def main(argv):
    if argv:
        items = [(u, u) for u in argv]
    else:
        texts = json.loads((ROOT / "data" / "creator_texts.json").read_text())
        items = [(k, v["edit"]["hero"]) for k, v in texts.items()
                 if v.get("edit") and not v["edit"].get("card_bg")]
    problems = [r for r in (check(label, url) for label, url in items) if r]
    print("\n".join(problems) if problems else "All photos sit within the 4:3 frame or already have card_bg set.")
    return 1 if any("CLIPPED" in p for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
