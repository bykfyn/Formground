"""
Architects & Interior Designers scraper - Formground's new Professionals
& Services section, Phase 2.

WHAT THIS DOES:
  Reads scraper/architects.json (a curated, individually-reviewed list -
  see WHY CURATED, NOT BULK-IMPORTED below), fetches each firm's real
  website, and pulls a small set of real, representative work photos -
  no per-project names or descriptions. Writes data/architects.json.

WHY CURATED, NOT BULK-IMPORTED:
  Sveriges Arkitekter's public directory has 693 real member firms
  (426-659 depending on which specializations are included) - but the
  user's explicit instruction was that architects get curated and
  triaged individually, the same way each of Formground's 74 maker
  brands was triaged one at a time, not wholesale-imported the way
  Interior Cluster/Skråhantverkarna were for Joiners & Craftspeople.
  This file is that curated allowlist, mirroring brands.json's shape
  and conventions exactly. The full reviewable candidate pool (with a
  live website check already run against all 393 real-website
  candidates) exists as Architects_Triage.csv for growing this list
  further - add entries here as they're reviewed, don't auto-import.

WHY MINIMAL PHOTOS, NOT NAMED PROJECT GALLERIES:
  Tested both this session against the real candidate pool. Structured
  per-project extraction (name + image per project, like Makers'
  product grids) needs a different parser per site's specific page-
  builder/plugin - real coverage came back at roughly 3% of candidates
  even after building 8 different pattern-specific extractors (2
  Squarespace, 6 WordPress plugins), because architecture-firm
  portfolio sites are far more heterogeneous than Shopify/WooCommerce's
  clean universal APIs. A much simpler "find real content photos on the
  page" approach (this file) - no per-project parsing, just filtering
  out obvious noise like logos/icons - reached 63-80% real coverage
  across the same pool with confirmed-good photo quality on spot
  checks. The richer named-project format stays a real future
  possibility (a natural fit for the optional paid enhancement tier
  discussed for this category - see project memory), not something
  every firm needs before being included at all.

PRIVACY RULE APPLIED: only business-labeled phone numbers are stored
(architects.json's own "phone" field, left blank when a firm only had a
personal mobile in the source data) - see project memory on this.

RUN:
    python3 scrape_architects.py
"""

import base64
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

SCRAPER_DIR = Path(__file__).parent
DATA_DIR = SCRAPER_DIR.parent / "data"
SOURCE_PATH = SCRAPER_DIR / "architects.json"
OUTPUT_PATH = DATA_DIR / "architects.json"

# Reuses backend/.env rather than needing a second copy of the API key -
# explicit path since scraper/ has no .env of its own and load_dotenv()
# with no argument only searches the current directory and its parents,
# which wouldn't find backend/.env when run from the repo root.
load_dotenv(SCRAPER_DIR.parent / "backend" / ".env")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
# Same default model backend/query_engine.py uses - a small
# classification task (does this photo show a building?), not one that
# needs a bigger/more expensive model.
VISION_MODEL = "claude-haiku-4-5-20251001"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FormgroundBot/1.0)"}
REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 0.2
MAX_PHOTOS_PER_FIRM = 6
# How many extra noise-filter-passing candidates to try per firm beyond
# max_photos, to absorb photos the vision check rejects (team/office
# photos, site context shots with no building in frame - see real cases
# found this session: AB Salt Arkitektur's beach photo, Yep Arkitekter's
# team-meeting photo). Bounded, not unlimited, to keep API usage predictable.
MAX_CANDIDATES_TO_TRY = MAX_PHOTOS_PER_FIRM + 6

# Below this many real photos, flag the firm for a manual look before
# publishing rather than trying to auto-detect a bad photo - the noise
# filter above only catches site chrome (logos/icons), not relevance
# (a real, large, non-chrome photo can still be irrelevant to the firm's
# actual work - confirmed live: AB Salt Arkitektur's one found photo was
# a genuine beach photo, no building in frame, that correctly passed
# every noise check since it really is a real, large, non-logo image).
# A low photo count is the cheap, honest signal that whatever was found
# deserves a second look, since firms are being curated individually
# anyway - not a claim that the photo IS wrong, just that it might be.
LOW_PHOTO_COUNT_THRESHOLD = 3

# Same noise-filtering approach validated during the pilot, refined
# after a real false-positive: Siegel Architecture has a genuine large
# (1024x1024) project graphic filed as "Hackspett-Logo-No-background...",
# which a blanket "logo" filename match wrongly excluded. "logo"/"icon"
# moved out of the filename-keyword list into a separate CSS-class check
# (real site chrome reliably uses classes like "custom-logo", real
# project photos with "logo" in their filename don't) - the filename
# keywords below are ones unlikely to appear in a real architecture
# photo's name either way.
# "pixel" deliberately excluded despite being a real tracking-pixel
# signal - it's also a substring of "shortpixel.ai", a common WordPress
# image-optimization CDN (confirmed live on Siegel Architecture: every
# real photo on the site is proxied through it, so this one keyword was
# excluding 100% of that site's real content). "1x1" already covers the
# actual tracking-pixel case without this false-positive risk.
NOISE_KEYWORDS = ("favicon", "sprite", "avatar", "placeholder", "spinner", "loader", "1x1")
NOISE_CLASSES = ("logo", "icon", "site-logo", "custom-logo", "navbar-brand", "header-logo", "nav-logo")
MIN_DIMENSION = 300
FILENAME_DIMENSION_RE = re.compile(r"(\d{2,4})x(\d{2,4})")


def _looks_like_noise(url, width, height, css_classes=()):
    if not url:
        return True
    lower = url.lower()
    path_only = lower.split("?")[0]
    if any(path_only.endswith(ext) for ext in (".mov", ".mp4", ".webm", ".m4v")) or "/video/" in lower:
        # Real case: Erik Andersson's site (Format.com) exposed a video-
        # streaming URL where a photo was expected. Cheap to catch by
        # extension/path before ever fetching it, same spirit as the SVG
        # exclusion below.
        return True
    if ".svg" in path_only:
        # Real case found while sampling candidates for a homepage mockup:
        # Malmström Edström's and Yep Arkitekter's first "photo" were both
        # their own logo SVGs, not project photography - neither matched
        # the CSS-class check (no "logo" class) nor the old filename
        # keyword (deliberately removed after the Siegel false-positive).
        # Architecture photography is never a vector file in practice, so
        # exclude the file type outright rather than trying to pattern-
        # match logo filenames again.
        return True
    if any(kw in lower for kw in NOISE_KEYWORDS):
        return True
    if any(any(nc in cls.lower() for nc in NOISE_CLASSES) for cls in css_classes):
        return True
    if width and height:
        try:
            if int(width) < MIN_DIMENSION or int(height) < MIN_DIMENSION:
                return True
        except ValueError:
            pass
    else:
        match = FILENAME_DIMENSION_RE.search(url)
        if match and (int(match.group(1)) < MIN_DIMENSION or int(match.group(2)) < MIN_DIMENSION):
            return True
    return False


def _image_url_from_tag(img, base_url):
    for attr in ("data-image", "data-src", "src"):
        val = img.get(attr)
        if val and not val.startswith("data:"):
            return urljoin(base_url, val)
    return None


_VISION_WARNED = False


def is_architecture_relevant(image_url):
    """
    Real, large, non-chrome photos can still be the wrong content - the
    noise filter above only catches site furniture (logos/icons), not
    relevance. Two real cases found this session: AB Salt Arkitektur's
    only found photo was a genuine beach photo with no building in
    frame, and Yep Arkitekter's photo pool included a real team-meeting
    photo (people, laptop, coffee mugs) - both real, large, non-logo
    images that no keyword/size/CSS-class heuristic can catch. This asks
    a vision-capable model directly instead of guessing from metadata.

    Fails open (returns True) on any error - a missing API key, a
    network hiccup, or a fetch failure should degrade to the old
    heuristic-only behavior, not silently drop every photo on the site.
    """
    global _VISION_WARNED
    if not ANTHROPIC_API_KEY:
        if not _VISION_WARNED:
            print("  (no ANTHROPIC_API_KEY set - skipping photo relevance check, using noise filter only)")
            _VISION_WARNED = True
        return True

    try:
        img_resp = requests.get(image_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        img_resp.raise_for_status()
        content_type = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]
        if not content_type.startswith("image/"):
            # Real bug found: Erik Andersson's Format.com portfolio
            # exposed a video-streaming URL (.mov, served as a "photo")
            # that made it all the way to the final data because this
            # used to return True (keep) here - meant to skip vision
            # classification for something that clearly isn't a photo,
            # but "skip the check" and "keep the item" are not the same
            # thing. A non-image response should never end up in the
            # photos list at all.
            return False
        image_b64 = base64.standard_b64encode(img_resp.content).decode("ascii")

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": VISION_MODEL,
                "max_tokens": 5,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": image_b64}},
                        {
                            "type": "text",
                            "text": (
                                "Does this photo clearly show a real BUILDING (its exterior or facade) or "
                                "the INTERIOR of a room inside a building - the kind of photo an architecture "
                                "or interior design firm would use to showcase a finished project? "
                                "Answer strictly 'yes' or 'no'. Answer 'no' for: people (portraits, "
                                "team/meeting photos), logos or diagrams, renderings/floor plans with no "
                                "photographic building shown, material/texture close-ups, and any outdoor "
                                "scene where a building isn't the clear subject - this includes beaches, "
                                "seawalls, breakwaters, docks, retaining walls, roads, bridges, or other "
                                "civil/landscape infrastructure that isn't part of a building itself. When in "
                                "doubt about whether a building is genuinely the subject of the photo, answer 'no'."
                            ),
                        },
                    ],
                }],
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        answer = response.json()["content"][0]["text"].strip().lower()
        return answer.startswith("y")
    except Exception as e:
        print(f"    (relevance check failed for {image_url}: {type(e).__name__} - keeping photo)")
        return True


def extract_minimal_photos(page_url, max_photos=MAX_PHOTOS_PER_FIRM):
    resp = requests.get(page_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    # requests falls back to ISO-8859-1 (the HTTP/RFC default) whenever a
    # server's Content-Type header omits a charset - real case found on
    # Arén & Yde's site, mangling every å/ä/ö. apparent_encoding reads
    # the real bytes instead of trusting an absent/wrong header.
    if resp.encoding == "ISO-8859-1":
        resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    seen = set()
    candidates = []
    for img in soup.select("img"):
        url = _image_url_from_tag(img, page_url)
        if not url or url in seen:
            continue
        css_classes = img.get("class") or []
        if _looks_like_noise(url, img.get("width"), img.get("height"), css_classes):
            continue
        seen.add(url)
        candidates.append(url)
        if len(candidates) >= MAX_CANDIDATES_TO_TRY:
            break

    if len(candidates) < MAX_CANDIDATES_TO_TRY:
        for el in soup.select("[style*='background-image']"):
            match = re.search(r'background-image:\s*url\(["\']?(.*?)["\']?\)', el.get("style", ""))
            if match:
                bg_url = urljoin(page_url, match.group(1))
                if bg_url not in seen and not _looks_like_noise(bg_url, None, None):
                    seen.add(bg_url)
                    candidates.append(bg_url)
                    if len(candidates) >= MAX_CANDIDATES_TO_TRY:
                        break

    # Vision check only runs on candidates that already passed the cheap
    # noise filter - keeps API calls bounded to real, plausible photos,
    # not every asset on the page.
    photos = []
    for url in candidates:
        if is_architecture_relevant(url):
            photos.append(url)
            if len(photos) >= max_photos:
                break

    return photos


def scrape():
    firms = json.loads(SOURCE_PATH.read_text())
    results = []
    for firm in firms:
        if not firm.get("scrapable", True):
            continue
        try:
            photos = extract_minimal_photos(firm["url"])
        except Exception as e:
            print(f"  {firm['name']}: FAILED ({type(e).__name__}: {e})")
            photos = []

        needs_review = len(photos) < LOW_PHOTO_COUNT_THRESHOLD
        results.append({
            "name": firm["name"],
            "url": firm["url"],
            "specialization": firm["specialization"],
            "city": firm.get("city"),
            "country": firm.get("country"),
            "email": firm.get("email") or None,
            "phone": firm.get("phone") or None,
            "photos": photos,
            "needs_review": needs_review,
            "source": firm.get("source"),
        })
        flag = "  <- low photo count, review before publishing" if needs_review else ""
        print(f"  {firm['name']}: {len(photos)} real photo(s){flag}")
        time.sleep(REQUEST_DELAY_SECONDS)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    flagged = [r["name"] for r in results if r["needs_review"]]
    if flagged:
        print(f"\n{len(flagged)} firm(s) flagged for review (fewer than {LOW_PHOTO_COUNT_THRESHOLD} real photos found):")
        for name in flagged:
            print(f"  - {name}")

    no_photos = sum(1 for r in results if not r["photos"])
    print(f"\nSaved {len(results)} architect firms to {OUTPUT_PATH} ({no_photos} with no photos found).")


if __name__ == "__main__":
    scrape()
