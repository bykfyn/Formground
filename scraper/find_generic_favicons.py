"""
Finds Stockist cards whose favicon is actually Google's generic "no
icon found" placeholder rather than a real one (2026-09-25).

WHY THIS IS NEEDED:
  Google's favicon service (https://www.google.com/s2/favicons) never
  errors outright, even for a domain with no real favicon - it silently
  returns a generic placeholder instead. The tell: a real favicon comes
  back at the requested size (sz=128 below); the generic placeholder
  always comes back as a tiny 16x16 image regardless of what was asked
  for. generate_marketplace_page.py's FORCE_MONOGRAM set (fed by this
  script's output) forces those cards to show their monogram instead of
  a blurry stretched placeholder.

RUN:
    python3 scraper/find_generic_favicons.py

  Prints one name per line for every card whose favicon should be
  force-monogrammed - paste the new full list into FORCE_MONOGRAM by
  hand (keep any manually-flagged entries like Creolight AS, whose real
  favicon exists but is inappropriate for a different reason - this
  script only catches the "no real icon at all" case).
"""

import json
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from generate_marketplace_page import RETAILERS_PATH, _favicon_url, _group_stockists

MIN_REAL_FAVICON_SIZE = 64


def find_generic_favicons():
    retailers = json.loads(RETAILERS_PATH.read_text(encoding="utf-8"))
    groups = _group_stockists(retailers)

    generic = []
    for name, locations in groups:
        website = locations[0]["website"]
        url = _favicon_url(website)
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=10)
            img = Image.open(BytesIO(resp.content))
            if img.size[0] < MIN_REAL_FAVICON_SIZE:
                generic.append(name)
        except Exception as e:
            print(f"  (skipped {name}: {e})", file=sys.stderr)
        time.sleep(0.05)

    return generic


if __name__ == "__main__":
    names = find_generic_favicons()
    print(f"{len(names)} cards with a generic/missing favicon:")
    for n in names:
        print(f'    "{n}",')
