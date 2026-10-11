"""
Fills the profile lists on the Creators page (frontend/creators.html -> docs/creators.html).

Per category (architects / designers / makers) the page has a column: the tile, then an optional "In profile" card
(an editorial profile Edit), then "A few to start with": a rotating sample of real profiles taken from the category's
own index page. The sample is deliberately random so no one is permanently on top (equal weight in the listings);
it rotates once a week (the seed is the ISO week), so it is the same all week for everyone and stable between builds.

"In profile": add an entry to PROFILE_EDITS when a profile Edit exists, e.g.
    PROFILE_EDITS["makers"] = {"slug": "kallemo", "name": "Källemo", "line": "One sentence from the Edit.",
                               "image": "https://..."}
and it appears with a link to /edits/<slug>.html plus an "All Edits" link. With none, the column is just the tile and
the list: nothing placeholder is ever shown.

Run after generate_brand_pages / generate_designers_pages / generate_architects_pages (it reads their index pages).
"""

import datetime
import html
import random
import re
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
ROOT = SCRAPER_DIR.parent
DOCS = ROOT / "docs"
FRONTEND = ROOT / "frontend"

GROUPS = ("architects", "designers", "makers")
SEE_ALL = {"architects": "firms", "designers": "designers", "makers": "brands"}
SHOWN = 5                      # on a phone the page CSS shows the first three
PROFILE_EDITS = {}             # {"makers": {"slug", "name", "line", "image"}} - see the docstring

CARD_RE = re.compile(
    r'<a class="maker-card" href="([^"]+)"[^>]*>.*?<img src="([^"]+)" alt="[^"]*".*?'
    r'<span class="maker-name">([^<]*)</span>\s*<span class="maker-country">([^<]*)</span>\s*'
    r'<span class="maker-categories">([^<]*)</span>', re.S)


def read_cards(group):
    """[{href, img, name, sub, extra}] (all HTML-escaped already) from docs/<group>.html."""
    text = (DOCS / f"{group}.html").read_text()
    return [dict(href=m.group(1), img=m.group(2), name=m.group(3), sub=m.group(4), extra=m.group(5))
            for m in CARD_RE.finditer(text)]


def sample(cards, group, today):
    """SHOWN cards, chosen at random but fixed for the ISO week. Designers: a cut-out PNG sits badly in a small square,
    so JPEG/WebP photos come first; anything is used only if there are too few."""
    year, week, _ = today.isocalendar()
    rng = random.Random(f"{group}-{year}-{week}")
    pool = [c for c in cards if c["img"]]
    if group == "designers":
        photos = [c for c in pool if not re.search(r"\.png(\?|$)", html.unescape(c["img"]), re.I)]
        if len(photos) >= SHOWN:
            pool = photos
    return rng.sample(pool, min(SHOWN, len(pool)))


def row_html(c):
    return (f'<a class="pf-row" href="{c["href"]}"><span class="pf-thumb"><img src="{c["img"]}" alt="" loading="lazy"></span>'
            f'<span class="pf-text"><span class="pf-name">{c["name"]}</span>'
            f'<span class="pf-sub">{c["sub"]} &middot; {c["extra"]}</span></span></a>')


def edit_html(edit):
    slug = html.escape(edit["slug"])
    return (f'\n    <p class="cr-label"><span>In profile</span><a href="/edits.html">All Edits &rarr;</a></p>\n'
            f'    <a class="ed-card" href="/edits/{slug}.html"><span class="ed-photo"><img src="{html.escape(edit["image"])}" alt="" loading="lazy"></span>'
            f'<span class="ed-title">{html.escape(edit["name"])}</span><span class="ed-line">{html.escape(edit["line"])}</span></a>')


def column_html(group, cards, today, count):
    rows = "".join(row_html(c) for c in sample(cards, group, today))
    featured = edit_html(PROFILE_EDITS[group]) if group in PROFILE_EDITS else ""
    return (f'{featured}\n    <p class="cr-label"><span>A few to start with</span></p>\n'
            f'    <div class="pf-list">{rows}</div>\n'
            f'    <a class="pf-all" href="{group}.html">See all {count:,} {SEE_ALL[group]} &rarr;</a>\n    ')


def render(text, today=None):
    today = today or datetime.date.today()
    for group in GROUPS:
        cards = read_cards(group)
        if not cards:
            continue
        pattern = re.compile(rf"<!--PROFILES:{group}-->.*?<!--/PROFILES:{group}-->", re.S)
        block = f"<!--PROFILES:{group}-->{column_html(group, cards, today, len(cards))}<!--/PROFILES:{group}-->"
        text = pattern.sub(lambda m: block, text, count=1)
    return text


def generate():
    template = FRONTEND / "creators.html"
    text = render(template.read_text())
    for folder in (FRONTEND, DOCS):
        (folder / "creators.html").write_text(text)
    print(f"Creators page: profile lists filled for {len(GROUPS)} categories.")


if __name__ == "__main__":
    generate()
