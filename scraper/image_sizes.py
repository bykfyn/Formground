"""
Card-sized image URLs (2026-10-04).

Formground shows makers' photos straight from the makers' own servers, which
mostly serve the full-size original (a 1.4MB photo for a 190px card; the home
page weighed 8.2MB on a throttled phone, 7.6MB of it images). Several image
services accept a width in the URL and return a resized copy, so every <img>
asks for the size it will actually be shown at. Verified 2026-10-04 on sample
images per host: 200 OK, correct dimensions, 5-400x fewer bytes (a 13.5MB
Contentful original becomes 5KB at 480px).

    sized(url, width) -> the same image at (at most) `width` px wide, or the
    URL unchanged when the host has no known resize rule. Never invents a size
    for a host it cannot verify (WordPress -WxH variants, Webflow, own-site
    files are left alone). Every host rule below was checked on real images (status, dimensions, bytes)
    before it was added; scripts/probes are in the 2026-10-04 audit in project-docs/Site_Patterns.md.

frontend/search.js carries the same rules in JavaScript (sizedImage) for the
live search results - keep the two in step (tests/test_image_sizes.py pins the
Python side).

Standard widths: CARD for a product card (a 190px card at up to 2.6x density),
TILE for a large tile, HERO for a full-width banner.
"""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

CARD = 500
TILE = 1000
HERO = 1600


def _with_query(url, drop=(), **params):
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k not in drop and k not in params]
    q += list(params.items())
    return urlunparse(p._replace(query=urlencode(q)))


def sized(url, width):
    if not url or not url.startswith("http"):
        return url
    host = urlparse(url).netloc.lower()
    if host == "cdn.shopify.com":
        return _with_query(url, width=width)
    if host in ("images.squarespace-cdn.com", "static1.squarespace.com"):
        return _with_query(url, format=f"{width}w")
    if host == "images.fogia.com":
        return _with_query(url, w=width)
    if host == "www.datocms-assets.com":
        # imgix: the scrape stored "?h=800" (a height cap); ask for a width instead
        return _with_query(url, drop=("h", "w"), w=width, auto="format")
    if host == "images.ctfassets.net":
        return _with_query(url, w=width, fm="webp", q=80)
    if host in ("www.hay.com", "cdn.thorcommerce.io"):
        # HAY and Gubi's image server: ?w= returns a resized copy (verified 2026-10-04: a 2.3MB, 3796px Gubi
        # original becomes 52KB at 500px; HAY 910-1220px -> 500px, 2-4x smaller)
        return _with_query(url, w=width)
    if host == "cdn.sanity.io":
        # Sanity's image pipeline (house photos): 957KB / 3000px -> 28KB at 500px, verified 2026-10-04
        return _with_query(url, w=width, auto="format")
    if host == "static.wixstatic.com" and "/media/" in url:
        # Wix's image engine: .../media/<id>.<ext>/v1/fit/w_W,h_H,q_80/file.<ext> (house photos), verified 2026-10-04
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}{p.path.split('/v1/')[0]}"
        ext = base.rsplit(".", 1)[-1].lower()
        if ext in ("jpg", "jpeg", "png", "webp", "gif"):
            return f"{base}/v1/fit/w_{width},h_{width},q_80/file.{ext}"
    return url
