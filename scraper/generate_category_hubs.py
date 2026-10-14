"""
The category hubs: /work/furniture.html, /work/lighting.html, /work/objects.html (2026-10-14).

Each hub used to be the search box, the menu and a bare grid of type tiles. It is now a scaled-down home page in the home
page's own look: the search box and menu, then Popular types (the home page's banners for that category), New in <category>
(a row of recent pieces), Edits in <category>, Browse every type (all the type tiles, grouped), a short closing paragraph and
the buying guides. A visually hidden H1 names the page. Houses keeps its own page (a full list of houses).

HOW: generate_browse_pages.py still writes the plain page first; this generator runs after the Edits are built and reuses
that page's head, header, search box, menu and type tiles, the home page's banner sections (frontend/index.html), the New
view's first cards (work/new-<category>.html), the Edit tiles (edits.html) and the guide texts (guides.html), then rewrites
the page. Run order is set in build_site.py.
"""

import html
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from image_sizes import HERO, sized

SCRAPER_DIR = Path(__file__).parent
ROOT = SCRAPER_DIR.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(SCRAPER_DIR))
sys.path.insert(0, str(ROOT / "backend"))

CATEGORIES = {"Furniture": "furniture", "Lighting": "lighting", "Objects": "objects"}
# Edits shown under each category (an Edit's own kind label); looks (rooms) are furniture and lighting together
EDIT_KINDS = {"Furniture": {"Furniture", "Living room"}, "Lighting": {"Lighting"}, "Objects": {"Objects", "Ceramics"}}
GUIDE_PICKS = {
    "Furniture": ["chairs", "sofas", "dining-tables"],
    "Lighting": ["floor-lamps", "table-lamps", "pendant-lamps"],
    "Objects": ["rugs", "candle-holders"],
}
NEW_ROW = 8
EDITS_MAX = 2      # the newest two, in one row; all of them are on the Edits page
SHOW_CLOSING_TEXT = False   # the short paragraph under the types (removed for now, 2026-10-14); CLOSING holds its text
POPULAR_PATH = ROOT / "data" / "hub_popular.json"   # per category: the big tile (a room/in-situ photo) and four type tiles
CLOSING = {
    "Furniture": "From a single stool to a full dining room, made by studios and workshops that sell directly.",
    "Lighting": "Pendants, table and floor lamps, wall lights and chandeliers from makers who design and produce their own light.",
    "Objects": "Rugs, vases, bowls, candle holders and the smaller things that finish a room, from ceramicists, glassmakers and studios.",
}

HUB_CSS = """
  .recent-section.hub-first { margin-top: 46px; }
  /* Popular types: one large tile (two columns, two rows) and four type tiles, each a type tile with its name below the photo */
  .bento { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); grid-template-rows: repeat(2, auto); gap: 20px; }
  .bento .bt { display: grid; grid-template-rows: 1fr auto; min-width: 0; }
  .bento .bt-img { aspect-ratio: 1 / 1; height: auto; position: relative; overflow: hidden; }
  .bento .bt-img img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .bento .bt-big { grid-column: 1 / 3; grid-row: 1 / 3; }
  .bento .bt-big .bt-img { aspect-ratio: auto; min-height: 0; }
  @media (max-width: 639px) { .bento { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .bento .bt-big { grid-column: 1 / 3; grid-row: auto; } .bento .bt-big .bt-img { aspect-ratio: 4 / 3; } }
  .hub-about { max-width: 640px; margin: 10px auto 36px; padding-top: 22px; border-top: 0.5px solid var(--border); }
  .hub-about p { font-size: 14px; line-height: 1.7; color: var(--text-secondary); text-align: center; margin: 0; }
  .guide-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .guide-card { display: flex; flex-direction: column; gap: 6px; padding: 18px; border: 0.5px solid var(--border); border-radius: 8px;
    text-decoration: none; background: var(--surface-1); }
  .guide-title { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 16px; color: var(--text-primary); }
  .guide-desc { font-size: 13px; line-height: 1.5; color: var(--text-secondary); }
  .guide-card:hover .guide-title { text-decoration: underline; }
  @media (max-width: 639px) { .guide-row { grid-template-columns: 1fr; } }
"""


def _soup(path):
    return BeautifulSoup(Path(path).read_text(), "html.parser")


def _home():
    """(home banner sections by category name, the home page's own <style> and carousel <script>)."""
    soup = _soup(ROOT / "frontend" / "index.html")
    sections = {}
    for sec in soup.find("main").find_all("section", recursive=False):
        h2 = sec.find("h2")
        if h2:
            sections[h2.get_text(strip=True).replace("→", "").strip()] = sec
    style = soup.find("style").string or ""
    script = next((s.string for s in soup.find_all("script") if s.string and "Banner/carousel rotation" in s.string), "")
    return sections, style, script


def _edit_tiles(category):
    """[(slug, title, image, alt, product, brand)] for this category's Edits, from the Edits hub page."""
    soup = _soup(DOCS / "edits.html")
    out = []
    for fig in soup.find_all("figure", class_="edit-feature"):
        kind = fig.find(class_="edit-kind").get_text(strip=True)
        if kind not in EDIT_KINDS[category]:
            continue
        link = fig.find("a", class_="edit-link")
        img = fig.find("img")
        credit = fig.find("a", class_="visit-source")
        product, brand = "", ""
        if credit:
            parts = [p.strip() for p in credit.find("span").get_text(" ", strip=True).split("·")]
            product, brand = parts[0], (parts[-1] if len(parts) > 1 else "")
        out.append((link["href"], fig.find(class_="edit-title").get_text(strip=True), img["src"] if img else "",
                    img.get("alt", "") if img else "", product, brand))
    return out


def _new_cards(cat_slug):
    path = DOCS / "work" / f"new-{cat_slug}.html"
    if not path.exists():
        return []
    out = []
    for c in _soup(path).find_all("a", class_="card")[:NEW_ROW]:
        img = c.find("img")
        out.append((c["href"], c.find(class_="card-title").get_text(strip=True), c.find(class_="card-brand").get_text(strip=True),
                    img["src"] if img else ""))
    return out


def _guides(category):
    soup = _soup(DOCS / "guides.html")
    by_slug = {}
    for entry in soup.find_all("div", class_="guide-entry"):
        a = entry.find("h3").find("a")
        slug = a["href"].rsplit("/", 1)[-1].replace(".html", "")
        by_slug[slug] = (a.get_text(strip=True), entry.find("p").get_text(strip=True))
    return [(s, *by_slug[s]) for s in GUIDE_PICKS[category] if s in by_slug]


def _type_blocks(old_main):
    """The old page's type tiles: group headings in the home page's group-header style, without the lone New tile."""
    parts = []
    for x in old_main.find_all(["h2", "div"], recursive=False):
        cls = x.get("class") or []
        if x.name == "h2" and "type-group-title" in cls:
            parts.append(f'<div class="recent-group-header"><h3>{html.escape(x.get_text(strip=True))}</h3></div>')
        elif x.name == "div" and "type-grid" in cls:
            links = x.find_all("a", recursive=False)
            if len(links) == 1 and "/work/new" in links[0].get("href", ""):
                continue                                              # New has its own section now
            parts.append(str(x))
    return "".join(parts)


def render_hub(category):
    cat_slug = CATEGORIES[category]
    old = _soup(DOCS / "work" / f"{cat_slug}.html")
    old_main = old.find("main")
    if old_main.find("section", class_="recent-section"):         # already a hub: rebuilt from the plain page next run
        raise RuntimeError("generate_browse_pages must run first")
    sections, home_style, _home_script = _home()

    description = old.find("meta", attrs={"name": "description"})["content"]
    m = re.search(r"([\d,]+) pieces .* across (\d+) types", description)
    total, ntypes = (m.group(1), m.group(2)) if m else ("", "")
    lower = category.lower()

    # Popular types: a bento of five tiles (data/hub_popular.json): one large tile and four type tiles, same tile as the types below
    popular_html = ""
    pop = json.loads(POPULAR_PATH.read_text()).get(category) if POPULAR_PATH.exists() else None
    if pop:
        tiles = {}                                                  # the old page's own type tiles: href -> (photo, name, count)
        for a in old_main.select("div.type-grid > a.maker-card"):
            tiles[a["href"]] = (a.find("img")["src"], a.find(class_="maker-name").get_text(strip=True), a.find(class_="maker-country").get_text(strip=True))

        def tile(slug, image, alt, cls=""):
            href = f"/work/{slug}.html"
            _img, name, count = tiles[href]
            return (f'<a class="maker-card bt{cls}" href="{href}"><div class="maker-card-hero bt-img"><img alt="{html.escape(alt or name)}" loading="lazy" '
                    f'src="{html.escape(image or _img)}"></div><div class="maker-card-body"><span class="maker-name">{html.escape(name)}</span>'
                    f'<span class="maker-country">{html.escape(count)}</span></div></a>')
        big = pop["big"]
        grid = tile(big["slug"], sized(big["image"], HERO), f'{big["name"]} by {big["brand"]}', " bt-big")
        grid += "".join(tile(slug, None, None) for slug in pop["types"])
        popular_html = ('<section class="recent-section hub-first"><div class="recent-header"><h2>Popular types</h2>'
                        f'<div class="recent-header-rule"></div></div><div class="recent-group"><div class="bento">{grid}</div></div></section>')

    new_cards = _new_cards(cat_slug)
    new_html = ""
    if new_cards:
        row = "".join(
            f'<a class="recent-card" href="{html.escape(href)}" target="_blank" rel="noopener noreferrer">'
            f'<div class="recent-card-image"><img alt="{html.escape(name)} by {html.escape(brand)}" loading="lazy" src="{html.escape(img)}"></div>'
            f'<span class="recent-name">{html.escape(name)}</span><span class="recent-brand">{html.escape(brand)}</span></a>'
            for href, name, brand, img in new_cards)
        new_html = (f'<section class="recent-section"><div class="recent-header"><h2><a class="cat-link section-header-link" '
                    f'href="/work/new-{cat_slug}.html">New in {lower}<span class="header-arrow"> &rarr;</span></a></h2>'
                    f'<a href="/work/new-{cat_slug}.html">See all new &rarr;</a><div class="recent-header-rule"></div></div>'
                    f'<div class="recent-row">{row}</div></section>')

    edits = _edit_tiles(category)[:EDITS_MAX]
    edits_html = ""
    if edits:
        cols = []
        for href, title, img, alt, product, brand in edits:
            cols.append(
                f'<div class="duo-col"><div class="recent-group-header"><h3>{html.escape(title)}</h3>'
                f'<a href="{html.escape(href)}">See the edit &rarr;</a></div>'
                f'<a class="duo-card" href="{html.escape(href)}"><div class="duo-card-image"><img alt="{html.escape(alt)}" loading="lazy" src="{html.escape(img)}"></div>'
                f'<span class="duo-name">{html.escape(product)}</span><span class="duo-brand">{html.escape(brand)}</span></a></div>')
        rows = "".join(f'<div class="recent-group"><div class="duo-row">{"".join(cols[i:i + 2])}</div></div>' for i in range(0, len(cols), 2))
        edits_html = (f'<section class="recent-section"><div class="recent-header"><h2><a class="cat-link section-header-link" href="/edits.html">'
                      f'Edits in {lower}<span class="header-arrow"> &rarr;</span></a></h2><div class="recent-header-rule"></div></div>{rows}</section>')

    types_html = (f'<section class="recent-section"><div class="recent-header"><h2>Browse every type</h2>'
                  f'<div class="recent-header-rule"></div></div>{_type_blocks(old_main)}</section>')
    about = f'<div class="hub-about"><p>{html.escape(CLOSING[category])} Each piece links to the maker\'s own page, where price, sizes and materials are theirs to state. {total} pieces across {ntypes} types.</p></div>'
    guides = _guides(category)
    guides_html = ""
    if guides:
        cards = "".join(f'<a class="guide-card" href="/guides/{s}.html"><span class="guide-title">{html.escape(t)}</span>'
                        f'<span class="guide-desc">{html.escape(d)}</span></a>' for s, t, d in guides)
        guides_html = (f'<section class="recent-section"><div class="recent-header"><h2><a class="cat-link section-header-link" href="/guides.html">'
                       f'Buying guides<span class="header-arrow"> &rarr;</span></a></h2><div class="recent-header-rule"></div></div>'
                       f'<div class="guide-row">{cards}</div></section>')

    # the plain page's own top of page (search box, menu) and its end (footer note), in place
    search = old_main.find("div", class_="search-wide")
    menu = old_main.find("nav", class_="work-menu")
    noscript = old_main.find("noscript")
    foot = old_main.find("p", class_="foot-note")
    main_html = (f'<main><h1 class="sr-only">{category}</h1>{search}{menu}{noscript or ""}{popular_html}{types_html}{new_html}{edits_html}'
                 f'{about if SHOW_CLOSING_TEXT else ""}{guides_html}{foot}</main>')

    # the plain page is edited as text, not re-serialised (the head must stay exactly as it was written)
    page = (DOCS / "work" / f"{cat_slug}.html").read_text()
    page = page.replace("</head>", f"<style>{home_style}{HUB_CSS}</style>\n</head>", 1)
    head_part, body_part = page.split("<body", 1)          # only the body's own <main> (a CSS comment in the head can mention it)
    body_part = re.sub(r"<main[ >].*?</main>", lambda _m: main_html, body_part, count=1, flags=re.S)
    page = head_part + "<body" + body_part
    return page


def generate():
    for category, cat_slug in CATEGORIES.items():
        path = DOCS / "work" / f"{cat_slug}.html"
        path.write_text(render_hub(category))
        print(f"work/{cat_slug}: hub written")


if __name__ == "__main__":
    generate()
