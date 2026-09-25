"""
Generates docs/marketplace.html and frontend/marketplace.html.

WHAT THIS ADDS (2026-09-25):
  The page was a single "coming soon" placeholder for paid Creator
  listings (Architects/Designers/Makers chips, no real content behind
  any of them). This adds two new tabs alongside that:
    - Stockists: a real, free directory of retailers who carry work
      from Formground's makers - sourced from data/retailers.json (see
      scraper/scrape_retailers.py and project memory,
      "Retailer/stockist + Promotions concept"). Not a paid placement.
    - Promotions: still a coming-soon placeholder, but its copy now
      reflects the real plan - a freemium mix of paid Creator feature
      listings and free, basic scraped retailer sales (see the same
      memory entry for the freemium framing).
  Same chip + pre-rendered cat-panel pattern as for-creators.html
  (generate_for_creators_page.py) - all panels' real HTML ships in the
  page at build time; the click handler only shows/hides.

STATUS: mockup, not yet pushed live. Run with --mockup to write to
  project-docs/mockups/ instead of docs/ and frontend/, for review
  before promoting (see project memory, "Mockup before push").

HOW TO RUN:
    python3 scraper/generate_marketplace_page.py            # writes docs/ + frontend/
    python3 scraper/generate_marketplace_page.py --mockup   # writes project-docs/mockups/ only
"""

import html
import json
import sys

from pathlib import Path
from urllib.parse import urlparse

from generate_brand_pages import CARD_CLICK_TRACKING_JS, DIRECTORY_FILTER_JS

SCRAPER_DIR = Path(__file__).parent
REPO_ROOT = SCRAPER_DIR.parent
RETAILERS_PATH = REPO_ROOT / "data" / "retailers.json"

CLOUDFLARE_BEACON = (
    "<!-- Cloudflare Web Analytics -->"
    "<script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' "
    "data-cf-beacon='{\"token\": \"87e51fd2f5894326b3c6e883edc75a6d\"}'></script>"
    "<!-- End Cloudflare Web Analytics -->"
)

FAVICON_TAGS = """<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon-32x32.png" type="image/png" sizes="32x32">
<link rel="icon" href="/favicon-16x16.png" type="image/png" sizes="16x16">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">"""

CHIPS = [
    ("stockists", "Stockists"),
    ("promotions", "Promotions"),
]

# Promotions' own sub-filter (2026-09-25, user direction): not creator
# type (Architects/Designers/Makers, dropped "for now") but *what's
# being promoted* - a product category to start, with room to grow
# (user: "later on we can add courses and consultation for example").
# "All" lives here now instead of as a top-level chip, since Stockists
# is the only other top-level tab and needs no "all" of its own.
PROMOTIONS_SUBCHIPS = [
    ("all", "All"),
    ("furniture", "Furniture"),
    ("lighting", "Lighting"),
    ("objects", "Objects"),
]

PAGE_CSS = """
  main { max-width: 1160px; margin: 0 auto; padding: 24px 20px 60px; }
  .site-header { margin-bottom: 0; }
  .search-wide { width: 100%; max-width: 900px; margin: 0 auto 32px; }
  /* No above-the-fold lead paragraph (2026-09-25, user: "a user will
     understand the concepts of promotion and stockist" - the chip
     labels plus each panel's own intro already carry that context
     where it's actually needed). A condensed version lives in the
     footer instead - real body text still reads for SEO/crawlers even
     when visually de-emphasized, same reasoning as the Guides content
     on For Creators. */
  p.footer-description { font-size: 12px; color: var(--text-muted); max-width: 640px; margin: 0 auto 20px; line-height: 1.6; text-align: center; }

  /* One real search box (2026-09-25, user: "there are two search boxes,
     we should only have the main one" - typing here filters whichever
     panel is currently showing, live, same substring-match pattern as
     makers.html/architects.html; the chips act as the category filter
     on top of that query, not a separate search of their own). */
  .ask-box {
    display: flex; align-items: center; gap: 10px; min-height: 57px;
    background: var(--surface-1); border: 0.5px solid var(--border);
    border-radius: var(--radius); padding: 13px 16px;
  }
  .ask-box i { font-size: 18px; color: var(--text-muted); }
  .ask-box input {
    border: none; background: none; outline: none; flex: 1;
    font-size: 15px; color: var(--text-primary); font-family: inherit;
  }
  .ask-box input::placeholder { color: var(--text-muted); }

  .chips { display: flex; justify-content: center; gap: 8px; margin-bottom: 32px; flex-wrap: wrap; }
  .chip {
    font-size: 13px; font-weight: 500; padding: 8px 14px; border-radius: 999px;
    border: 0.5px solid var(--border-strong); background: var(--surface-2);
    color: var(--text-muted); font-family: inherit; opacity: 0.7; cursor: pointer;
  }
  .chip.active { background: var(--surface-1); color: var(--text-secondary); border-color: var(--border-strong); opacity: 1; }

  @media (max-width: 640px) {
    .chips {
      flex-wrap: nowrap; justify-content: flex-start; overflow-x: auto;
      -webkit-overflow-scrolling: touch; padding-bottom: 4px; scrollbar-width: none;
      -webkit-mask-image: linear-gradient(to right, black calc(100% - 28px), transparent 100%);
      mask-image: linear-gradient(to right, black calc(100% - 28px), transparent 100%);
    }
    .chips::-webkit-scrollbar { display: none; }
    .chip { flex-shrink: 0; }
  }

  .panel-intro { font-size: 13px; color: var(--text-muted); text-align: center; max-width: 560px; margin: 0 auto 24px; line-height: 1.6; }

  /* Sub-filter within a panel (e.g. Promotions' Architects/Designers/
     Makers creator-type filter) - same chip look, smaller and no
     bottom margin since it sits directly above that panel's own
     content rather than the page-level chip row. */
  .sub-chips { display: flex; justify-content: center; gap: 6px; margin: 0 0 28px; flex-wrap: wrap; }
  .sub-chips .chip { font-size: 12px; padding: 6px 12px; }

  .empty-state {
    border: 1px dashed var(--border-strong); border-radius: 14px;
    padding: 56px 24px; text-align: center; background: var(--surface-1);
  }
  .empty-state .eyebrow {
    font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--text-accent); margin: 0 auto 10px;
  }
  .empty-state p { font-size: 14px; color: var(--text-secondary); max-width: 420px; margin: 0 auto 22px; line-height: 1.6; }
  .cta-btn {
    display: inline-flex; align-items: center; gap: 8px;
    font-size: 14px; font-weight: 600; color: var(--surface-2);
    background: var(--text-primary); padding: 12px 22px; border-radius: var(--radius);
    text-decoration: none;
  }
  .cta-btn:hover { background: var(--text-secondary); }

  .who-for {
    margin-top: 36px; padding-top: 24px; border-top: 0.5px solid var(--border);
    font-size: 13px; color: var(--text-muted); line-height: 1.7; text-align: center;
  }

  /* Stockist cards reuse for-creators.html's maker-card/tool-card-hero
     pattern (see project memory) - a retailer's own real favicon over a
     bare monogram (user, 2026-09-25), since we don't have a real
     storefront photo per retailer. */
  .maker-grid { display: grid; grid-template-columns: repeat(auto-fit, 190px); justify-content: center; gap: 16px; align-items: start; }
  .maker-card { display: block; text-decoration: none; color: inherit; }
  .maker-card-hero { aspect-ratio: 4/3; background: var(--surface-1); border: 0.5px solid var(--border); margin: 0 0 10px; display: flex; align-items: center; justify-content: center; }
  .maker-card-body { padding: 0; text-align: center; }
  .maker-card .maker-name { display: block; font-size: 15px; font-weight: 500; color: var(--text-secondary); margin: 0 0 3px; }
  .maker-card:hover .maker-name { text-decoration: underline; }
  .maker-country { display: block; font-size: 11px; color: var(--text-secondary); margin: 0 0 3px; }
  /* Fixed-size circular badge, shared by a real favicon and the
     monogram fallback alike (user, 2026-09-25: favicons "minuscule" vs
     "larger" - real favicons bake wildly different amounts of their own
     internal padding into the image, so even identical CSS bounds leave
     them looking inconsistent; normalizing every icon into the same
     56px circle, favicon or not, fixes that instead of chasing each
     image's own whitespace). */
  .icon-badge {
    width: 56px; height: 56px; border-radius: 50%; background: var(--surface-2);
    border: 0.5px solid var(--border-strong); display: flex; align-items: center;
    justify-content: center; overflow: hidden;
  }
  .icon-badge img { width: 65%; height: 65%; object-fit: contain; }
  .monogram {
    font-family: 'Archivo', sans-serif; font-weight: 700;
    font-size: 18px; color: var(--text-secondary);
  }

  [hidden] { display: none !important; }
"""

PAGE_SCRIPT = """
  // Top-level chips: every panel's real content already sits in the
  // page - this just shows the one matching the clicked chip and hides
  // the rest.
  document.querySelectorAll('.chips > .chip').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var cat = btn.dataset.cat;
      document.querySelectorAll('.chips > .chip').forEach(function (b) {
        b.classList.toggle('active', b === btn);
      });
      document.querySelectorAll('.cat-panel').forEach(function (panel) {
        panel.style.display = panel.dataset.cat === cat ? '' : 'none';
      });
    });
  });

  // Promotions' Furniture/Lighting/Objects sub-filter: purely visual
  // for now (no real promotions to filter yet), but wired so it's
  // ready the moment there's something to filter.
  document.querySelectorAll('.sub-chips .chip').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.sub-chips .chip').forEach(function (b) {
        b.classList.toggle('active', b === btn);
      });
    });
  });
"""


def _initials(name):
    words = [w for w in name.split() if w and w[0].isalpha()]
    return "".join(w[0] for w in words[:2]).upper()


def _location(r):
    city, country = r.get("city", ""), r.get("country", "")
    if city and country:
        return f"{city}, {country}"
    return city or country or "Online retailer"


def _group_stockists(retailers):
    """
    One real retail brand with several physical locations gets one
    card, not one per city (user, 2026-09-25) - grouped by the raw
    entry's own "brand" field where one is set (see BRAND_MAP in the
    data-cleanup script that tagged it), falling back to the entry's
    own name for everyone else, since most stockists really are just
    one location.
    """
    groups = {}
    order = []
    for r in retailers:
        key = r.get("brand") or r["name"]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    return [(key, groups[key]) for key in order]


def _grouped_location_line(locations):
    if len(locations) == 1:
        return _location(locations[0])
    countries = {loc.get("country", "") for loc in locations if loc.get("country")}
    if len(countries) == 1:
        return f"{len(locations)} locations in {countries.pop()}"
    return f"{len(locations)} locations across {len(countries)} countries"


def _grouped_location_sr(locations):
    # Every location's own city/country/address stays real, searchable
    # content, even when only a summary count is shown (see
    # _grouped_location_line) - "Malmö" still has to find Svenssons.
    parts = []
    for loc in locations:
        bits = [b for b in (loc.get("address"), loc.get("city"), loc.get("country")) if b]
        if bits:
            parts.append(", ".join(bits))
    return "; ".join(parts)


def _favicon_url(website):
    domain = urlparse(website).netloc.removeprefix("www.")
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128" if domain else None


# A site's own real favicon is occasionally something that shouldn't
# stand in for the business on a directory card - Creolight AS's is a
# photo of a person (user, 2026-09-25). Google's favicon service almost
# never actually fails to return *something*, so onerror doesn't catch
# this; force the monogram instead for the rare flagged case.
FORCE_MONOGRAM = {"Creolight AS"}


def _stockist_card(name, locations):
    website = locations[0]["website"]
    # Union of every location's brands, order preserved, dedup by
    # first occurrence - a chain like Svenssons doesn't necessarily
    # carry the identical lineup in every store.
    seen = set()
    brands = []
    for loc in locations:
        for b in loc.get("brands") or []:
            if b not in seen:
                seen.add(b)
                brands.append(b)
    # Full brand list, and every location's own city/country/address,
    # stay in the DOM for the search box to match against, just not
    # rendered - many stockists carry 15-20+ brands, and a truncated
    # "X, Y, Z +17 more" reads badly on a card (user, 2026-09-25).
    # sr-only, not display:none, so it's still real content a screen
    # reader and a crawler both see, just not painted.
    brands_sr = f'<span class="sr-only">{html.escape(", ".join(brands))}</span>' if brands else ""
    locations_sr = (
        f'<span class="sr-only">{html.escape(_grouped_location_sr(locations))}</span>'
        if len(locations) > 1 else ""
    )
    # Real favicon over a bare monogram (user, 2026-09-25) - same
    # icon-with-monogram-fallback pattern as for-creators.html's tool
    # cards, just fetched live via Google's favicon service instead of
    # hand-checked per entry (137 sites, not a handful of known tools).
    # onerror swaps to the monogram on the rare genuine load failure.
    favicon = None if name in FORCE_MONOGRAM else _favicon_url(website)
    monogram_span = f'<span class="monogram" title="{html.escape(name)}">{_initials(name)}</span>'
    badge = (
        f'<img src="{html.escape(favicon)}" alt="{html.escape(name)}" loading="lazy" '
        f'onerror="this.remove();this.parentElement.querySelector(\'.monogram\').style.display=\'\';">'
        f'<span class="monogram" style="display:none;" title="{html.escape(name)}">{_initials(name)}</span>'
        if favicon else monogram_span
    )
    return f"""      <a class="maker-card" href="{html.escape(website)}" target="_blank" rel="noopener noreferrer">
        <div class="maker-card-hero"><div class="icon-badge">{badge}</div></div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(name)}</span>
          <span class="maker-country">{html.escape(_grouped_location_line(locations))}</span>{locations_sr}{brands_sr}
        </div>
      </a>"""


def render_stockists_panel(retailers):
    groups = _group_stockists(retailers)
    ordered = sorted(groups, key=lambda g: (g[1][0].get("country") or "zzz", g[1][0].get("city") or "", g[0]))
    cards = "\n".join(_stockist_card(name, locations) for name, locations in ordered)
    intro = (
        "    <p class=\"panel-intro\">Real retailers who carry work from Formground's makers, "
        "found via their own published stockist lists - not a paid placement. "
        "Something outdated or missing? <a href=\"contact.html\">Let us know</a>.</p>"
    )
    return f'    <div class="cat-panel" data-cat="stockists">\n{intro}\n    <div class="maker-grid">\n{cards}\n    </div>\n    </div>'


def render_promotions_panel():
    subchips_html = "\n".join(
        f'      <button class="chip{" active" if cat_id == "all" else ""}" data-subcat="{cat_id}">{html.escape(label)}</button>'
        for cat_id, label in PROMOTIONS_SUBCHIPS
    )
    return f"""    <div class="cat-panel" data-cat="promotions" style="display: none;">
    <p class="panel-intro">A mix of paid feature listings from Creators - filterable by type below - and free, basic promotions pulled from stockists' own live sales pages, sourced the same transparent, attributed, remove-on-request way as the rest of Formground.</p>
    <div class="sub-chips">
{subchips_html}
    </div>
    <div class="empty-state">
      <p class="eyebrow">Coming soon</p>
      <p>This is where listings will appear once the Marketplace opens — a small first group, by invitation, before it's open to everyone.</p>
      <a class="cta-btn" href="contact.html">Want to be featured here? Get in touch<i class="ti ti-arrow-right" aria-hidden="true"></i></a>
    </div>
    </div>"""


def render_page(retailers):
    chips_html = "\n".join(
        f'    <button class="chip{" active" if cat_id == "stockists" else ""}" data-cat="{cat_id}">{html.escape(label)}</button>'
        for cat_id, label in CHIPS
    )

    panels_html = "\n\n".join([
        render_stockists_panel(retailers),
        render_promotions_panel(),
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Marketplace — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="Stockists who carry work from Formground's makers, live promotions, and a paid space for architects, designers, and makers to feature something specific.">
<meta property="og:title" content="Marketplace — Formground">
<meta property="og:description" content="Stockists who carry work from Formground's makers, live promotions, and a paid space for architects, designers, and makers to feature something specific.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://formground.com/marketplace.html">
<meta property="og:site_name" content="Formground">
<meta property="og:image" content="https://formground.com/favicon-192x192.png">
<link rel="canonical" href="https://formground.com/marketplace.html">
<meta name="twitter:card" content="summary">
<meta name="twitter:image" content="https://formground.com/favicon-192x192.png">
<meta name="twitter:title" content="Marketplace — Formground">
<meta name="twitter:description" content="Stockists, promotions, and a paid space for architects, designers, and makers.">
<link rel="preload" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"></noscript>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="site.css">
<style>{PAGE_CSS}</style>
</head>
<body>

<header class="site-header">
  <a class="home-link" href="/"><img src="logo/formground_logotype_RGB.png" alt="Formground"></a>
<nav class="top-nav">
  <a href="work.html">Work</a>
  <a href="creators.html">Creators</a>
  <a href="marketplace.html" class="current">Marketplace</a>
  <a href="for-creators.html">For Creators</a>
</nav>
</header>

<main>

  <h1 class="sr-only">Marketplace</h1>

  <div class="search-wide">
    <div class="ask-box">
      <i class="ti ti-search" aria-hidden="true"></i>
      <input id="directory-filter" type="text" placeholder="Search stockists and promotions — a brand, a city, a product…" autocomplete="off">
    </div>
  </div>

  <div class="chips">
{chips_html}
  </div>

{panels_html}

  <p class="who-for">
    Already on Formground as an architect, designer, or maker? Reach out if you'd like in early.
  </p>

  <p class="footer-description">Real stockists who carry work from Formground's makers, live promotions, and a paid space for architects, designers, and makers to feature something specific. Stockist listings are free and unpaid, sourced the same transparent way as the rest of Formground - paid features are always clearly marked.</p>

  <p class="foot-note">
    &copy; 2026 Formground &middot; <a href="/">← Back to Formground</a> &middot; <a href="privacy.html">Privacy</a> &middot; <a href="about.html">About</a>
  </p>
</main>

<script>{PAGE_SCRIPT}</script>
<script>{DIRECTORY_FILTER_JS}</script>
<script>{CARD_CLICK_TRACKING_JS}</script>

{CLOUDFLARE_BEACON}
</body>
</html>
"""


def main():
    retailers = json.loads(RETAILERS_PATH.read_text(encoding="utf-8"))
    page = render_page(retailers)
    n_cards = len(_group_stockists(retailers))
    summary = f"{n_cards} cards ({len(retailers)} locations)"

    if "--mockup" in sys.argv:
        out_path = REPO_ROOT / "project-docs" / "mockups" / "marketplace_stockists_promotions.html"
        out_path.write_text(page)
        print(f"Wrote mockup: {out_path} ({summary})")
    else:
        for target_dir in ("docs", "frontend"):
            out_path = REPO_ROOT / target_dir / "marketplace.html"
            out_path.write_text(page)
            print(f"Wrote {out_path} ({summary})")


if __name__ == "__main__":
    main()
