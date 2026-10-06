"""
Generates the Buying guides hub (docs/guides.html) and one page per guide (docs/guides/<slug>.html).
MOCKUP built 2026-10-06 for review; nothing here is pushed until approved.

Content lives in guides_content.py (general guidance only: no maker claims, no sustainability labels).
Run it AFTER generate_edits_page.py in the chain (it appends to the sitemap), and re-run the whole chain
afterwards so the versioned asset links stay in step.
"""

import html
import json
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
DOCS_DIR = SCRAPER_DIR.parent / "docs"
sys.path.insert(0, str(SCRAPER_DIR))
sys.path.insert(0, str(SCRAPER_DIR.parent / "backend"))

from generate_brand_pages import (  # noqa: E402
    CARD_CLICK_TRACKING_JS,
    CLOUDFLARE_ANALYTICS,
    FAVICON_TAGS,
    PAGE_CSS,
    SITE_FOOTER_HTML,
    SITE_URL,
    fit_title,
    site_nav_html,
)
from generate_theme_landing_pages import append_to_sitemap  # noqa: E402
from guides_content import GROUP_ORDER, GUIDES, LABEL_NOTE  # noqa: E402
from site_assets import ICONS_CSS  # noqa: E402

GUIDE_CSS = """
  main.guide { max-width: 720px; margin: 0 auto; padding: 0 20px 40px; }
  .guide-crumb { font-size: 12px; color: var(--text-muted); text-align: center; margin: 26px 0 0; }
  .guide-crumb a { color: var(--text-accent); text-decoration: none; }
  .guide-crumb a:hover { text-decoration: underline; }
  .guide h1 { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 28px; line-height: 1.15; text-align: center; margin: 10px 0 14px; text-wrap: balance; }
  .guide-intro { font-size: 15px; line-height: 1.6; color: var(--text-secondary); text-align: center; margin: 0 auto 8px; max-width: 600px; }
  .guide-links { font-size: 13px; text-align: center; margin: 14px 0 30px; }
  .guide-links a { color: var(--text-accent); text-decoration: none; white-space: nowrap; }
  .guide-links a:hover { text-decoration: underline; }
  .guide-links .sep { color: var(--text-muted); margin: 0 8px; }
  .guide h2 { font-family: 'Archivo', sans-serif; font-weight: 600; font-size: 18px; margin: 30px 0 10px; }
  .guide ul { margin: 0; padding-left: 20px; }
  .guide li { font-size: 15px; line-height: 1.6; margin: 0 0 8px; }
  .guide-sources { margin-top: 38px; padding-top: 22px; border-top: 0.5px solid var(--border); }
  .guide-sources h2 { margin-top: 0; }
  .guide-sources .note { font-size: 13px; color: var(--text-muted); font-style: italic; line-height: 1.5; margin: 0 0 12px; }
  .guide-sources li { font-size: 14px; }
  .guide-sources a { color: var(--text-accent); overflow-wrap: anywhere; }
  .guides-hero { text-align: center; padding: 34px 0 8px; }
  .guides-hero h1 { font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 30px; margin: 0 0 10px; }
  .guides-hero p { font-size: 15px; line-height: 1.6; color: var(--text-secondary); max-width: 560px; margin: 0 auto; }
  .guides-group h2 { font-family: 'Archivo', sans-serif; font-weight: 600; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin: 34px 0 6px; }
  .guide-entry { padding: 16px 0; border-bottom: 0.5px solid var(--border); }
  .guide-entry h3 { font-family: 'Archivo', sans-serif; font-weight: 600; font-size: 18px; margin: 0 0 4px; }
  .guide-entry h3 a { color: var(--text-primary); text-decoration: none; }
  .guide-entry h3 a:hover { text-decoration: underline; }
  .guide-entry p { font-size: 14px; line-height: 1.55; color: var(--text-secondary); margin: 0 0 6px; }
  .guide-entry .guide-links { text-align: left; margin: 6px 0 0; display: flex; flex-wrap: wrap; row-gap: 4px; }
"""


def _head(title, description, url, extra_json=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
{FAVICON_TAGS}
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE_URL}/og-default.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="{SITE_URL}/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(description)}">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="{ICONS_CSS}">
<style>{PAGE_CSS}</style>
<style>{GUIDE_CSS}</style>
{extra_json}</head>
"""


def _breadcrumb_json(crumbs):
    return '<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": url}
            for i, (name, url) in enumerate(crumbs, start=1)
        ],
    }, ensure_ascii=False, separators=(",", ":")) + "</script>\n"


def _tail():
    return f"""  <p class="foot-note">
    {SITE_FOOTER_HTML}
  </p>
</main>
<script>{CARD_CLICK_TRACKING_JS}</script>
{CLOUDFLARE_ANALYTICS}
</body>
</html>
"""


def render_guide(guide, edit_exists):
    title = fit_title(f"How to choose {guide['noun']}: what to consider")
    description = (f"What to consider before choosing {guide['noun']}: sizes, materials, care and questions to ask "
                   "the maker. General guidance, no ratings.")
    url = f"{SITE_URL}/guides/{guide['slug']}.html"
    crumbs = [("Formground", f"{SITE_URL}/"), ("Buying guides", f"{SITE_URL}/guides.html"), (guide["title"], url)]
    sections = "".join(
        f"\n  <h2>{html.escape(heading)}</h2>\n  <ul>" + "".join(f"\n    <li>{html.escape(b)}</li>" for b in bullets) + "\n  </ul>"
        for heading, bullets in guide["sections"]
    )
    sources = "".join(
        f'\n    <li><a href="{html.escape(href)}" target="_blank" rel="noopener noreferrer">{html.escape(label)}</a></li>'
        for label, href in guide["sources"]
    )
    links = [f'<a href="/work/{guide["slug"]}.html">Browse {html.escape(guide["noun"])} &rarr;</a>']
    if edit_exists:
        links.append(f'<a href="/edits/{guide["edit_slug"]}.html">See an Edit &rarr;</a>')
    link_row = '<span class="sep">&middot;</span>'.join(links)
    return (
        _head(title, description, url, _breadcrumb_json(crumbs))
        + f"""<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html(None)}
</header>
<main class="guide">
  <p class="guide-crumb"><a href="/guides.html">Buying guides</a></p>
  <h1>How to choose {html.escape(guide['noun'])}: what to consider</h1>
  <p class="guide-intro">{html.escape(guide['intro'])}</p>
  <p class="guide-links">{link_row}</p>{sections}
  <section class="guide-sources">
    <h2>Sources and further reading</h2>
    <p class="note">{html.escape(LABEL_NOTE)}</p>
    <ul>{sources}
    </ul>
  </section>
  <p class="guide-links">{link_row}</p>
"""
        + _tail()
    )


def render_hub(groups, edit_slugs):
    description = ("Things to consider before you choose, from sizes and light to materials and care. "
                   "General guidance for buyers, no ratings.")
    title = "Buying guides: what to consider before you choose — Formground"
    url = f"{SITE_URL}/guides.html"
    crumbs = [("Formground", f"{SITE_URL}/"), ("Buying guides", url)]
    body = ""
    for group in GROUP_ORDER:
        entries = groups.get(group)
        if not entries:
            continue
        body += f'\n  <section class="guides-group">\n    <h2>{html.escape(group)}</h2>'
        for g in sorted(entries, key=lambda e: e['title']):
            links = [f'<a href="/guides/{g["slug"]}.html">Read the guide &rarr;</a>',
                     f'<a href="/work/{g["slug"]}.html">Browse {html.escape(g["noun"])}</a>']
            if g["edit_slug"] in edit_slugs:
                links.append(f'<a href="/edits/{g["edit_slug"]}.html">See an Edit</a>')
            body += f"""
    <div class="guide-entry">
      <h3><a href="/guides/{g['slug']}.html">{html.escape(g['title'])}</a></h3>
      <p>{html.escape(g['summary'])}</p>
      <p class="guide-links">{'<span class="sep">&middot;</span>'.join(links)}</p>
    </div>"""
        body += "\n  </section>"
    return (
        _head(title, description, url, _breadcrumb_json(crumbs))
        + f"""<body>
<header class="site-header">
  <a class="home-link" href="/"><img src="/logo/formground_logotype_RGB.png" alt="Formground"></a>
{site_nav_html(None)}
</header>
<main class="guide">
  <div class="guides-hero">
    <h1>Buying guides</h1>
    <p>Things to consider before you choose, from sizes and light to materials and care. General guidance for buyers: no ratings, and nothing about any one maker.</p>
  </div>{body}
"""
        + _tail()
    )


def generate():
    (DOCS_DIR / "guides").mkdir(exist_ok=True)
    edit_slugs = {p.stem for p in (DOCS_DIR / "edits").glob("*.html")}
    groups = {}
    for guide in GUIDES:
        (DOCS_DIR / "guides" / f"{guide['slug']}.html").write_text(render_guide(guide, guide["edit_slug"] in edit_slugs))
        groups.setdefault(guide["group"], []).append(guide)
    (DOCS_DIR / "guides.html").write_text(render_hub(groups, edit_slugs))
    append_to_sitemap(["guides"] + [f"guides/{g['slug']}" for g in GUIDES])
    print(f"Generated guides.html and {len(GUIDES)} guide pages.")


if __name__ == "__main__":
    generate()
