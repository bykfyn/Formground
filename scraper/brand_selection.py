"""
"A selection": the pieces shown first on a maker's page, chosen to represent the whole collection rather than
whatever sorts first alphabetically or happens to be new.

representative_selection(products, n) takes one piece per category in turn (largest category first, then round
again), so a maker who makes plates, bowls, lamps and benches shows one of each before a second plate. Inside a
category the pick is stable but arbitrary (a hash of brand and name, so a rebuild does not reshuffle the page)
among the pieces whose photo suits a square card. Colour/finish variants count once.
"""
import hashlib

import image_fit

_WIDE, _TALL = 1.8, 0.55    # the same limits the card CSS uses before it letterboxes a photo


def _photo_suits_card(url):
    info = image_fit._load().get(url)
    if not info:
        return True                       # not measured: assume a normal photo
    ratio = info["ratio"]
    return _TALL <= ratio <= _WIDE


def _stable_key(p):
    return hashlib.md5(f'{p.get("brand", "")}|{p["product_name"]}'.encode()).hexdigest()


def representative_selection(products, n=12):
    from generate_theme_landing_pages import _group_color_variants   # colour variants count once
    usable = [p for p in products if p.get("image_url") and not p.get("link_dead")]
    if len(usable) <= n:
        return usable
    singles, _ = _group_color_variants(usable)

    by_cat = {}
    for p in singles:
        by_cat.setdefault((p.get("category") or "").strip() or "Other", []).append(p)
    for items in by_cat.values():
        # pieces with a well-fitting photo and real details first, then the stable arbitrary order
        items.sort(key=lambda p: (not _photo_suits_card(p["image_url"]), bool(p.get("thin")), _stable_key(p)))
    # biggest categories first; "Other" (unclassified) goes last in each round
    order = sorted(by_cat, key=lambda c: (c == "Other", -len(by_cat[c]), c))

    picked = []
    rnd = 0
    while len(picked) < n and any(len(by_cat[c]) > rnd for c in order):
        for c in order:
            if len(by_cat[c]) > rnd:
                picked.append(by_cat[c][rnd])
                if len(picked) == n:
                    break
        rnd += 1
    return picked
