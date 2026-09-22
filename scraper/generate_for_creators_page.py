"""
Generates docs/for-creators.html and frontend/for-creators.html.

WHAT THIS REPLACES:
  The old for-creators.html was a hand-written flat list of resource
  links. This is its replacement - the "For Creators by Formground"
  concept built and reviewed as a mockup at
  project-docs/mockups/for_creators_marketplace.html, now promoted to
  the real site (2026-09-22, user: "What has been created will be the
  new For Creators page... It replaces for-creators.html").

WHY THIS IS A SEPARATE GENERATOR, NOT HAND-WRITTEN HTML:
  The mockup built all its content (craftspeople cards, tool-category
  cards) client-side via JavaScript, generating innerHTML from data
  arrays after the page loaded. That's fine for a scratch mockup but
  wrong for a real page: a crawler that doesn't execute JS sees an
  empty shell, which defeats the page's own stated purpose (see the
  "Getting Started: Selling & Distribution" guide's own point about a
  real, structured site being what an AI assistant can actually read).
  This script renders every category's real HTML at build time instead
  - all of it sits in the page's initial HTML regardless of JS - and
  only the chip-click show/hide toggle stays as a tiny runtime script,
  same pattern as every other real page on the site.

HOW TO RUN:
  python3 scraper/generate_for_creators_page.py

  No scraping happens here - the data below is a curated, hand-vetted
  list (see each entry's own sourcing comment), not something to
  re-scrape on a schedule the way scrape.py's brand catalog is.
"""

import html

from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
REPO_ROOT = SCRAPER_DIR.parent

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

# Föreningen Skråhantverkarna - independent traditional-craft practitioners
# (free/community tier). Violin Making and Goldsmithing removed 2026-09-22
# (user: doesn't fit this list - musical instruments and fine jewelry
# aren't production partners for architects/designers/makers the way
# joinery, casting, basketmaking etc. are).
#
# Each entry's image is checked against the firm's own site first, per
# project memory's standing rule (link to and photograph the firm's own
# site, never the association's) - and, where the firm's site offers a
# choice, a wordmark/product/interior shot over a photo of the person.
# Snickare Peter Dans AB's own domain no longer resolves at all - its
# link reverted to the association page rather than point at a dead site.
SKRAHANTVERKARNA = [
    {"name": "Snickare Peter Dans AB", "craft": "Fine Joinery", "location": "Vallentuna, Sweden", "website": "https://skrahantverkarna.se", "image": "https://skrahantverkarna.se/wp-content/uploads/2020/03/Dans-5-1024x796.jpg", "verified": False},
    {"name": "PV Specialmöbler & Inredning", "craft": "Furniture Joinery", "location": "Björkvik, Sweden", "website": "http://www.pekka.biz", "image": "https://pekka.biz/uploads/images/172/thumb-soffa_front.jpg", "verified": False},
    {"name": "Lidingö Möbelverkstad", "craft": "Furniture Restoration", "location": "Lidingö, Sweden", "website": "http://www.lidingomobelverkstad.se", "image": "https://skrahantverkarna.se/wp-content/uploads/2020/02/l2-646x502-1.jpg", "verified": False},
    {"name": "Larsson Korgmakare AB", "craft": "Basketmaking", "location": "Stockholm, Sweden", "website": "http://www.larssonkorgmakare.se", "image": "https://skrahantverkarna.se/wp-content/uploads/2020/02/lk-646x502-1.jpg", "verified": False},
    {"name": "Wretman Stenmontage", "craft": "Stonemasonry", "location": "Täby, Sweden", "website": "https://skrahantverkarna.se", "image": "https://skrahantverkarna.se/wp-content/uploads/2020/03/Sten-5-1024x796.jpg", "verified": False},
]

# Interior Cluster Sweden - established, production-scale partner
# companies (verified/established tier).
INTERIOR_CLUSTER = [
    {"name": "Vadstena Konstgjuteri", "craft": "Art Casting & Foundry", "location": "Vadstena, Sweden", "website": "https://www.vadstenakonstgjuteri.se/", "image": "https://skrahantverkarna.se/wp-content/uploads/2022/12/Bild3.jpg", "verified": True},
    {"name": "Stockholms Förgyllning & Bildhuggeri AB", "craft": "Gilding & Woodcarving", "location": "Stockholm, Sweden", "website": "http://www.stockholmsf%C3%B6rgyllning.se", "image": "https://skrahantverkarna.se/wp-content/uploads/2020/03/Fo%CC%88rgy-bildh-6-1024x796.jpg", "verified": True},
    {"name": "Bendinggroup", "craft": "Wood & Metal Bending", "location": "Sweden", "website": "http://www.bendinggroup.se", "image": "https://dx7phrh2v9esk.cloudfront.net/sites/11/media/1454_original_BendingGroup1080x680.jpg", "verified": True},
    {"name": "C & D Snickeri", "craft": "Woodworking & Carpentry", "location": "Sweden", "website": "http://www.cdsnickeri.se", "image": "https://dx7phrh2v9esk.cloudfront.net/sites/11/media/1616_medium_C_D_Snickeri_1080x680.jpg", "verified": True},
    {"name": "Anderssons Mekaniska", "craft": "Metal Fabrication", "location": "Sweden", "website": "http://www.anderssonsmekaniska.se", "image": "https://dx7phrh2v9esk.cloudfront.net/sites/11/media/5482_large_Anderssonsmekaniksa.jpg", "verified": True},
    {"name": "Ackurat Industriplast", "craft": "Plastic Fittings & Components", "location": "Sweden", "website": "https://www.ackurat.se", "image": "https://dx7phrh2v9esk.cloudfront.net/sites/11/media/1444_original_Ackurat_ICS_2_1080x680.jpg", "verified": True},
    {"name": "Carlsson Smide & Järnaffär", "craft": "Blacksmithing & Metalwork", "location": "Sweden", "website": "http://www.carlssonsmide.com", "image": "https://dx7phrh2v9esk.cloudfront.net/sites/11/media/1821_medium_CarlssonsSmide.jpg", "verified": True},
    {"name": "Elmo Läder", "craft": "Leather", "location": "Sweden", "website": "http://www.elmoleather.com", "image": "https://dx7phrh2v9esk.cloudfront.net/sites/11/media/2344_medium_Elmo.jpg", "verified": True},
    {"name": "Stolfabriken i Tibro", "craft": "Chair Manufacturing", "location": "Tibro, Sweden", "website": "http://stolfabriken.se", "image": "https://dx7phrh2v9esk.cloudfront.net/sites/11/media/1816_original_Stolfabriken.png", "verified": True},
]

# Stockholms Snickarmästareförening (~120-member Stockholm carpenters'
# association). Its live site is currently down (404-loops) - this list
# and each firm's own real site/photo were sourced from a Wayback Machine
# snapshot of /medlemmar from 2026-06-10, not a live scrape.
STOCKHOLMS_SNICKARMASTAREFORENING = [
    {"name": "Måns & Marcus Finsnickeri AB", "craft": "Custom Cabinetry", "location": "Stockholm, Sweden", "website": "https://www.mmfinsnickeri.se", "image": "https://mmfinsnickeri.se/wp-content/uploads/2026/05/B0048936-1.jpg", "verified": False},
    {"name": "KFK Snickeri AB", "craft": "Bespoke Furniture & Fixtures", "location": "Sollentuna, Sweden", "website": "https://www.kfksnickeri.se", "image": "https://kfksnickeri.se/wp-content/uploads/2017/09/byredo_hemsida.jpg", "verified": False},
    {"name": "Ekskogens Snickeri", "craft": "Built-in Carpentry", "location": "Stockholm, Sweden", "website": "https://www.ekskogenssnickeri.com", "image": "https://ekskogenssnickeri.com/wp-content/uploads/2025/05/cover6.webp", "verified": False},
]

# Sourced directly (not via an association): a web search for "möbelsnickeri
# stockholm" plus a cross-check on Houzz.se, which independently listed
# Ludwig Berg too.
DIRECT_SOURCED = [
    {"name": "Ludwig Berg", "craft": "Furniture Joinery", "location": "Bromma, Sweden", "website": "http://www.ludwigberg.com", "image": "https://images.squarespace-cdn.com/content/v1/54c61f45e4b09cfa786d4b45/1486228625944-10698EYCBAR69LCX82PN/Cabinet+Luftig+Nyckelsk%C3%A5p.jpg", "verified": False},
    {"name": "Asp Snickeri AB", "craft": "Fine Joinery", "location": "Stockholm, Sweden", "website": "https://www.aspsnickeri.se", "image": "https://i0.wp.com/www.aspsnickeri.se/wp-content/uploads/2019/12/PRIVAT-BIBLIOTEK.jpg?fit=1024%2C768&ssl=1", "verified": False},
    {"name": "Stockholms Finsnickeri AB", "craft": "Furniture Joinery", "location": "Stockholm, Sweden", "website": "https://www.stockholmsfinsnickeri.se", "image": "https://stockholmsfinsnickeri.com/wp-content/uploads/2024/04/vacker-platsbyggd-bokhylla.webp", "verified": False},
]

CRAFTSPEOPLE = SKRAHANTVERKARNA + INTERIOR_CLUSTER + STOCKHOLMS_SNICKARMASTAREFORENING + DIRECT_SOURCED

# Hand-picked top row (2026-09-22): the strongest real photography in the
# set, a better "professional looking" signal than the verified flag
# alone - leads ahead of the Interior Cluster tier, which leads ahead of
# everyone else.
TOP_ROW = ["KFK Snickeri AB", "Ekskogens Snickeri", "Måns & Marcus Finsnickeri AB", "Ludwig Berg"]


def _craftsperson_rank(c):
    if c["name"] in TOP_ROW:
        return TOP_ROW.index(c["name"])
    return len(TOP_ROW) + (0 if c["verified"] else 1)


# Brand mark for each tool/service - mostly each site's own apple-touch-icon,
# a couple via Google's favicon service where the site blocked a direct
# fetch or had no touch-icon of its own (Etsy, Fusion 360, Cloudways -
# those render smaller/softer than the rest). Interior Lifestyle Tokyo was
# dropped - its real domain doesn't resolve at all right now.
TOOL_CATEGORIES = {
    "selling": [
        {"name": "Shopify", "type": "E-commerce Platform", "country": "Canada", "website": "https://www.shopify.com", "icon": "https://cdn.shopify.com/b/shopify-brochure2-assets/c97c60ca19c64a8b5378d9f9e971f7bd.png"},
        {"name": "Squarespace", "type": "Website & Store Builder", "country": "USA", "website": "https://www.squarespace.com", "icon": "https://media-www.sqspcdn.com/logos/apple-touch-icon-120.png"},
        {"name": "WooCommerce", "type": "WordPress Store Plugin", "country": "USA", "website": "https://woocommerce.com", "icon": "https://woocommerce.com/wp-content/uploads/2024/12/cropped-logo-w-favicon.png?w=180"},
        {"name": "Big Cartel", "type": "Store Builder for Independent Makers", "country": "USA", "website": "https://www.bigcartel.com", "icon": "https://www.google.com/s2/favicons?domain=bigcartel.com&sz=128"},
        {"name": "Etsy", "type": "Handmade & Vintage Marketplace", "country": "USA", "website": "https://www.etsy.com", "icon": "https://www.google.com/s2/favicons?domain=etsy.com&sz=128"},
        {"name": "Faire", "type": "Wholesale Marketplace", "country": "USA", "website": "https://www.faire.com", "icon": "https://www.faire.com/apple-touch-icon.png"},
        {"name": "Ankorstore", "type": "Wholesale Marketplace", "country": "France", "website": "https://www.ankorstore.com", "icon": "https://cdn.ankorstore.com/ankorstore/apple-touch-icon.png"},
        {"name": "1stDibs", "type": "High-End & Collectible Marketplace", "country": "USA", "website": "https://www.1stdibs.com", "icon": "https://a.1stdibscdn.com/dist/adhoc/logo/monogram-white-120.png"},
        {"name": "Pamono", "type": "Collectible Design Marketplace", "country": "Germany", "website": "https://www.pamono.com", "icon": "https://www.pamono.com/skin/frontend/lamono/redesign/images/mobile-icons/pamono-app-icon-512.png"},
    ],
    "design": [
        {"name": "Fusion 360", "type": "CAD Software", "country": "USA", "website": "https://www.autodesk.com/products/fusion-360", "icon": "https://www.google.com/s2/favicons?domain=autodesk.com&sz=128"},
        {"name": "Shapeways", "type": "3D Printing Service", "country": "USA", "website": "https://www.shapeways.com", "icon": "https://www.shapeways.com/wp-content/uploads/2022/04/favicon.ico"},
        {"name": "Material District", "type": "Materials Database", "country": "Netherlands", "website": "https://materialdistrict.com", "icon": "https://materialdistrict.com/apple-icon.png"},
        {"name": "99designs", "type": "Design Contest Platform", "country": "Australia", "website": "https://99designs.com", "icon": "https://99designs.com/touch-icon-iphone.png"},
        {"name": "Fiverr", "type": "Freelancer Marketplace", "country": "Israel", "website": "https://www.fiverr.com", "icon": "https://www.google.com/s2/favicons?domain=fiverr.com&sz=128"},
    ],
    "hosting": [
        {"name": "WP Engine", "type": "Managed WordPress Hosting", "country": "USA", "website": "https://wpengine.com", "icon": "https://wpengine.com/assets/manifest/apple-touch-icon.png"},
        {"name": "Cloudways", "type": "Managed Cloud Hosting", "country": "Malta", "website": "https://www.cloudways.com", "icon": "https://www.google.com/s2/favicons?domain=cloudways.com&sz=128"},
    ],
    "marketing": [
        {"name": "Klaviyo", "type": "Email & SMS Marketing", "country": "USA", "website": "https://www.klaviyo.com", "icon": "https://www.klaviyo.com/icons/icon-48x48.png"},
        {"name": "PhotoRoom", "type": "AI Product Photo Editing", "country": "France", "website": "https://www.photoroom.com", "icon": "https://www.photoroom.com/favicons/apple-touch-icon.png"},
        {"name": "Packhelp", "type": "Custom Packaging", "country": "Poland", "website": "https://www.packhelp.com", "icon": "https://www.packhelp.com/_astro/apple-touch-icon.BrhYexou.png"},
        {"name": "Shippo", "type": "Shipping Rate Comparison", "country": "USA", "website": "https://goshippo.com", "icon": "https://cdn.prod.website-files.com/6462967bbf70fa5b5b227351/662680002605ee5735982802_img-shipp-favicon-256x256.png"},
        {"name": "Sendcloud", "type": "European Shipping Platform", "country": "Netherlands", "website": "https://www.sendcloud.com", "icon": "https://framerusercontent.com/images/42cXDspPEL7fiY0Ghw8qS8d6wAc.svg"},
        {"name": "uShip", "type": "Freight Marketplace", "country": "USA", "website": "https://www.uship.com", "icon": "https://www.ushipcdn.cloud/favicons/apple-touch-icon.png"},
    ],
    "fairs": [
        {"name": "Salone del Mobile", "type": "Furniture & Design Fair", "country": "Italy", "website": "https://www.salonemilano.it", "icon": "https://www.salonemilano.it/themes/custom/sdm/favicon.ico"},
        {"name": "Stockholm Furniture Fair", "type": "Furniture & Lighting Fair", "country": "Sweden", "website": "https://www.stockholmfurniturefair.com", "icon": "https://www.google.com/s2/favicons?domain=stockholmfurniturefair.com&sz=128"},
        {"name": "Maison&Objet", "type": "Home & Design Trade Fair", "country": "France", "website": "https://www.maison-objet.com", "icon": "https://www.google.com/s2/favicons?domain=maison-objet.com&sz=128"},
        {"name": "ICFF", "type": "Contemporary Furniture Fair", "country": "USA", "website": "https://icff.com", "icon": "https://icff.com/wp-content/uploads/2024/01/ICFF-FAVICON-128X128.png"},
    ],
    "associations": [
        # No working icon found - their own <link rel="icon"> points at a
        # CloudFront asset that 403s (Access Denied at the origin).
        {"name": "Interior Cluster Sweden", "type": "Furniture & Interior Industry Cluster", "country": "Sweden", "website": "https://interiorcluster.se", "icon": None},
        {"name": "Föreningen Skråhantverkarna", "type": "Traditional Craft Association", "country": "Sweden", "website": "https://skrahantverkarna.se", "icon": "https://skrahantverkarna.se/wp-content/uploads/2019/12/cropped-favicon512-300x300.png"},
        {"name": "EFIC", "type": "European Furniture Trade Body", "country": "Belgium", "website": "https://www.efic.eu", "icon": "https://static.wixstatic.com/media/a1d93b_f4079750b5404e9b83fbf168fdf86366~mv2.png"},
    ],
}

CATEGORIES = [
    ("all", "All"),
    ("craftspeople", "Craftspeople"),
    ("selling", "Selling & Distribution"),
    ("design", "Design & Prototyping"),
    ("hosting", "Hosting"),
    ("marketing", "Marketing & Fulfillment"),
    ("fairs", "Fairs & Exhibitions"),
    ("associations", "Associations"),
    ("guides", "Guides"),
]

PAGE_CSS = """
  main { max-width: 1160px; margin: 0 auto; padding: 24px 20px 60px; }
  .site-header { margin-bottom: 0; }
  .search-wide { width: 100%; max-width: 900px; margin: 0 auto 32px; }
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

  /* Mobile: a 9-category row wraps to 4 lines on a phone, pushing the
     first card well below the fold. Single-line, horizontally
     scrollable row instead of wrapping - no JS, scales to any category
     count. Right-edge fade signals there's more; left edge stays
     opaque so the first chip is never masked at rest. */
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

  /* Fixed-width columns (190px, not makers.html's minmax(190px, 1fr)):
     a short category (e.g. Hosting's 2 entries) must not stretch its
     cards bigger than a full category's - that would read as if the
     bigger ones were paid/featured, contradicting the equal-weight,
     no-paid-ranking listing this is. */
  .maker-grid { display: grid; grid-template-columns: repeat(auto-fill, 190px); gap: 16px; align-items: start; }
  .maker-card { display: block; text-decoration: none; color: inherit; }
  .maker-card-hero { aspect-ratio: 4/3; background: var(--surface-1); border: 0.5px solid var(--border); margin: 0 0 10px; }
  .maker-card-hero img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .maker-card-body { padding: 0; text-align: center; }
  .maker-card .maker-name { display: block; font-size: 15px; font-weight: 500; color: var(--text-secondary); margin: 0 0 3px; }
  .maker-card:hover .maker-name { text-decoration: underline; }
  .maker-country { display: block; font-size: 11px; color: var(--text-secondary); margin: 0 0 3px; }
  .maker-categories { display: block; font-size: 11px; color: var(--text-muted); letter-spacing: 0.01em; }

  /* Tool/service/association cards reuse .maker-card, but their image is
     a square brand mark, not a cropped photo - contain + padding
     centers the mark instead of cropping it illegibly. */
  .tool-card-hero { display: flex; align-items: center; justify-content: center; padding: 24px; box-sizing: border-box; }
  .tool-card-hero img { width: auto; height: auto; max-width: 72%; max-height: 72%; object-fit: contain; }
  .tool-card-hero .monogram {
    width: 56px; height: 56px; border-radius: 50%; background: var(--surface-2);
    border: 0.5px solid var(--border-strong); display: flex; align-items: center;
    justify-content: center; font-family: 'Archivo', sans-serif; font-weight: 700;
    font-size: 18px; color: var(--text-secondary);
  }

  /* Guides: editorial write-ups per category, aimed at makers earlier in
     their journey than the brands already featured elsewhere - not a
     card grid, since there's no single company/brand behind any of it. */
  .guides-list { max-width: 640px; margin: 0 auto; }
  .guide-article { margin-bottom: 40px; }
  .guide-article:last-of-type { margin-bottom: 0; }
  .guide-article h2 {
    font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 17px;
    letter-spacing: -0.005em; color: var(--text-primary); margin: 0 0 12px;
    text-transform: none; scroll-margin-top: 0;
  }
  .guide-article p { font-size: 14px; line-height: 1.7; color: var(--text-secondary); margin: 0 0 12px; }
  .guide-article p:last-child { margin-bottom: 0; }
  .guide-article strong { color: var(--text-primary); font-weight: 600; }
  .guide-article a { color: var(--text-accent); text-decoration: none; }
  .guide-article a:hover { text-decoration: underline; }
  .guide-intro { font-size: 14px; line-height: 1.7; color: var(--text-secondary); margin: 0 0 36px; text-align: center; }

  .guide-links { display: flex; flex-direction: column; gap: 18px; padding-top: 28px; border-top: 0.5px solid var(--border); }
  .guide-links .resource-name { font-size: 15px; font-weight: 500; color: var(--text-primary); text-decoration: none; }
  .guide-links .resource-name:hover { text-decoration: underline; }
  .guide-links .resource-name i { font-size: 14px; margin-left: 4px; vertical-align: 1px; color: var(--text-muted); }
  .guide-links p { font-size: 13.5px; line-height: 1.6; color: var(--text-secondary); margin: 2px 0 0; }
"""


def _initials(name):
    words = [w for w in name.split() if w and w[0].isalpha()]
    return "".join(w[0] for w in words[:2]).upper()


def _craftsperson_card(c):
    return f"""      <a class="maker-card" href="{html.escape(c['website'])}" target="_blank" rel="noopener noreferrer">
        <div class="maker-card-hero"><img src="{html.escape(c['image'])}" alt="{html.escape(c['name'])}" loading="lazy"></div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(c['name'])}</span>
          <span class="maker-country">{html.escape(c['location'])}</span>
          <span class="maker-categories">{html.escape(c['craft'])}</span>
        </div>
      </a>"""


def _tool_card(t):
    if t["icon"]:
        media = f'<img src="{html.escape(t["icon"])}" alt="{html.escape(t["name"])}" loading="lazy">'
    else:
        media = f'<div class="monogram" title="{html.escape(t["name"])}">{_initials(t["name"])}</div>'
    return f"""      <a class="maker-card" href="{html.escape(t['website'])}" target="_blank" rel="noopener noreferrer">
        <div class="maker-card-hero tool-card-hero">{media}</div>
        <div class="maker-card-body">
          <span class="maker-name">{html.escape(t['name'])}</span>
          <span class="maker-country">{html.escape(t['type'])}</span>
          <span class="maker-categories">{html.escape(t['country'])}</span>
        </div>
      </a>"""


def render_craftspeople_panel():
    sorted_people = sorted(CRAFTSPEOPLE, key=_craftsperson_rank)
    cards = "\n".join(_craftsperson_card(c) for c in sorted_people)
    return f'    <div class="maker-grid cat-panel" data-cat="craftspeople">\n{cards}\n    </div>'


def render_tool_panel(cat_id):
    cards = "\n".join(_tool_card(t) for t in TOOL_CATEGORIES[cat_id])
    return f'    <div class="maker-grid cat-panel" data-cat="{cat_id}" style="display: none;">\n{cards}\n    </div>'


GUIDES_HTML = """    <div class="guides-list cat-panel" data-cat="guides" style="display: none;">

      <p class="guide-intro">Formground exists to help independent designers and makers get found — and a lot of that work happens before anyone searches for you at all. The brands and makers already featured here have their own stores, their own domains, their own way of showing up. If you're earlier in that journey, these are written for you: honest, friendly starting points, not verdicts on the "right" choice — because the right one really does depend on where you are.</p>

      <div class="guide-article">
        <h2>Getting Started: Selling &amp; Distribution</h2>
        <p><strong>Start with something that's yours.</strong> Wherever you sell, having your own site — a domain you control, not just a profile on someone else's platform — is worth prioritizing early, even before your catalog feels "ready." It's the difference between building something that compounds and renting space you could lose access to. It also matters more than it used to: as more shopping starts with an AI assistant reading a page on your behalf rather than a person browsing a marketplace, a real site with clear, structured information about your work is what that assistant actually finds. A marketplace profile mostly isn't.</p>
        <p><strong>Shopify</strong>, <strong>Squarespace</strong>, and <strong>WooCommerce</strong> are the three most common starting points among makers already here, and honestly, any of the three will get you selling. Shopify tends to suit a growing catalog best; Squarespace is a nice fit if the shop sits alongside a portfolio-style site; WooCommerce makes sense if you're already comfortable with WordPress and want more control over the details. <strong>Big Cartel</strong> is worth a look if your catalog is small and likely to stay that way — it's built for exactly that, not scaled down from something bigger.</p>
        <p><strong>Etsy</strong> is a genuinely useful place to start if handmade, smaller-ticket work is what you're making — just go in with your eyes open about the trade-off: fees and ad placements can take close to a third of what you earn, so most people treat it as a supplement to their own site rather than a home base.</p>
        <p><strong>Faire</strong> and <strong>Ankorstore</strong> open up trade — selling to retailers instead of individual customers — once your own site has shown there's real demand. Which one fits often comes down to simple locality: Faire leans North American, Ankorstore European, so start with whichever matches where your interest is actually coming from.</p>
        <p><strong>1stDibs</strong> and <strong>Pamono</strong> sit at the high end — vetted, application-only marketplaces for collectible design. They're worth keeping in mind for later rather than reaching for now; a track record tends to matter more here than a strong start.</p>
        <p>A last thought, since it comes up often as you grow: transparency with your customers — where things are made, what they're made of, how they're shipped — isn't just good practice, it's increasingly expected, and regulation is starting to make some of it a requirement rather than a choice (more on that in the regulation note below). Worth building the habit early, while it's still simple to do.</p>
      </div>

      <div class="guide-article">
        <h2>Getting Started: Design &amp; Prototyping</h2>
        <p>These five don't really compete with each other — they cover different moments in getting from an idea to a real object, so think of this less as "which one" and more as "which stage are you at." <strong>Fusion 360</strong> is where a design becomes testable before it costs you anything in materials or tooling — worth learning early, even if the curve feels steep at first. Once you've got something worth holding, <strong>Shapeways</strong> turns a digital file into a real, physical prototype without needing your own equipment — a good gut-check before committing to a full production run.</p>
        <p><strong>Material District</strong> is worth a browse whenever a material choice feels uncertain; it's built for designers rather than manufacturers, and its sustainable-options coverage is a genuinely easy way to make a more considered choice early, while a spec is still easy to change. If branding is the gap rather than the object itself, <strong>99designs</strong> and <strong>Fiverr</strong> offer two different ways to get there — a contest across many designers if you want options to choose from, or a freelancer you hire directly if you already know the look you're after.</p>
      </div>

      <div class="guide-article">
        <h2>Getting Started: Hosting</h2>
        <p>A small, practical choice most people only think about once. <strong>WP Engine</strong> is the specialist pick if you're running WooCommerce — it costs more than generic hosting, but it takes server maintenance off your plate entirely, which is worth it once a store is actually your livelihood. <strong>Cloudways</strong> is the friendlier-on-budget alternative — still fully managed, still no server upkeep for you to worry about, just less specialized. Neither is wrong; it mostly comes down to what you can comfortably spend before the store is earning enough to justify the difference.</p>
      </div>

      <div class="guide-article">
        <h2>Getting Started: Marketing &amp; Fulfillment</h2>
        <p>Three genuinely different jobs live under this one heading, so take them one at a time. For actually reaching people, <strong>Klaviyo</strong> is worth setting up before a launch, not after — building a waitlist through email or SMS gives a small run somewhere to sell to on day one, rather than hoping social media catches it. <strong>PhotoRoom</strong> is a low-cost way to get clean product photography without booking a full studio shoot, which matters more than it sounds like when you're weighing where early budget goes.</p>
        <p>For packaging, <strong>Packhelp</strong> is worth a look the moment an off-the-shelf box stops fitting what you make — custom packaging in small quantities also tends to mean less wasted material than forcing an odd-shaped piece into a box built for something else.</p>
        <p>And for getting things to people: <strong>Shippo</strong> and <strong>Sendcloud</strong> do the same job on opposite sides of the Atlantic — Shippo if you're shipping mostly within the US and Canada, Sendcloud if you're in Europe — while <strong>uShip</strong> is the one worth remembering specifically for furniture: large, heavy, or fragile pieces need a freight marketplace built for that, not a standard parcel carrier.</p>
      </div>

      <div class="guide-article">
        <h2>Getting Started: Fairs &amp; Exhibitions</h2>
        <p>Which fair makes sense mostly comes down to where you are and how big a step you're ready to take. <strong>Salone del Mobile</strong> in Milan is the largest furniture and design fair there is — an aspiration for many, not usually a first fair. <strong>Stockholm Furniture Fair</strong> is a friendlier entry point if you're Nordic or Northern European, regional in scale but a real, respected stage. <strong>Maison&amp;Objet</strong> in Paris leans more lifestyle and home than furniture specifically, which can suit certain kinds of work particularly well. And if North America is the goal, <strong>ICFF</strong> in New York is the natural first stop — sized for exactly that kind of first step, rather than requiring one already.</p>
      </div>

      <div class="guide-article">
        <h2>Getting Started: Associations</h2>
        <p>Joining one of these is less about a membership badge and more about not having to figure everything out alone. <strong>Interior Cluster Sweden</strong> connects manufacturers, designers, and subcontractors — useful if you're looking for production partners, not just peers. <strong>Föreningen Skråhantverkarna</strong> exists to keep traditional trades and skills alive, which makes it a genuinely good place to find (or become) the kind of specialist craftsperson a bigger studio would otherwise struggle to source. And bodies like <strong>EFIC</strong> operate a level up again — shaping how regulation actually gets applied to furniture makers, which matters more than it might seem from the outside (more on that below).</p>
      </div>

      <div class="guide-article">
        <h2>A Macro Note: Regulation &amp; Trade</h2>
        <p>This part tends to feel intimidating from a distance and much more manageable once you're actually in it — worth reading now, while it's still simple, rather than later under pressure. If you start selling across borders, VAT and customs rules will eventually apply to you, and they're genuinely easier to set up correctly from the start than to untangle after a few hundred orders.</p>
        <p>On the regulation side, change is coming gradually rather than all at once: the EU's <a href="https://green-forum.ec.europa.eu/implementing-ecodesign-sustainable-products-regulation_en" target="_blank" rel="noopener noreferrer">Ecodesign for Sustainable Products Regulation</a> is introducing a "Digital Product Passport" — a standard record of a product's materials, durability, and repairability that travels with it — and furniture is one of the categories in scope, with the EU's central registry live since mid-2026 and furniture-specific requirements expected around 2028–2029. That's a few years out, but it rewards starting early: transparency about materials and origin is a habit worth building before it's mandatory, not after.</p>
        <p>This is exactly where a trade association earns its keep — several, including EFIC, are already building shared infrastructure so individual makers don't have to solve this alone. None of this needs to slow you down today. It's just worth knowing it's coming, and worth choosing partners and habits now that won't need to be redone later.</p>
      </div>

      <div class="guide-links">
        <div>
          <a class="resource-name" href="https://search.google.com/search-console" target="_blank" rel="noopener noreferrer">Google Search Console<i class="ti ti-external-link" aria-hidden="true"></i></a>
          <p>Free — shows how Google actually sees your site, and lets you submit a sitemap or flag a page for re-indexing.</p>
        </div>
        <div>
          <a class="resource-name" href="https://developers.google.com/search/docs/fundamentals/seo-starter-guide" target="_blank" rel="noopener noreferrer">Google's SEO Starter Guide<i class="ti ti-external-link" aria-hidden="true"></i></a>
          <p>Free, written by Google itself, and enough to cover the fundamentals without hiring anyone.</p>
        </div>
        <div>
          <a class="resource-name" href="https://schema.org/Product" target="_blank" rel="noopener noreferrer">schema.org structured data<i class="ti ti-external-link" aria-hidden="true"></i></a>
          <p>The structured-data format search engines and AI agents both use to read a page accurately.</p>
        </div>
      </div>

    </div>"""

PAGE_SCRIPT = """
  // Every category's real content already sits in the page (see the
  // .cat-panel divs above) - this just shows the one matching the
  // clicked chip and hides the rest, no data fetching or templating.
  document.querySelectorAll('.chip').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var cat = btn.dataset.cat;
      document.querySelectorAll('.chip').forEach(function (b) {
        b.classList.toggle('active', b === btn);
      });
      document.querySelectorAll('.cat-panel').forEach(function (panel) {
        var show = panel.dataset.cat === cat || (cat === 'all' && panel.dataset.cat === 'craftspeople');
        panel.style.display = show ? '' : 'none';
      });
    });
  });
"""


def render_page():
    chips_html = "\n".join(
        f'    <button class="chip{" active" if cat_id == "craftspeople" else ""}" data-cat="{cat_id}">{html.escape(label)}</button>'
        for cat_id, label in CATEGORIES
    )

    panels = [render_craftspeople_panel()]
    for cat_id in ("selling", "design", "hosting", "marketing", "fairs", "associations"):
        panels.append(render_tool_panel(cat_id))
    panels.append(GUIDES_HTML)
    panels_html = "\n\n".join(panels)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>For Creators — Formground</title>
{FAVICON_TAGS}
<meta name="description" content="Production partners, resources and suppliers for architects, designers, and makers - real craftspeople and companies, plus friendly starting-point guides for makers earlier in their journey.">
<meta property="og:title" content="For Creators — Formground">
<meta property="og:description" content="Production partners, resources and suppliers for architects, designers, and makers - real craftspeople and companies, plus friendly starting-point guides for makers earlier in their journey.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://formground.com/for-creators.html">
<meta property="og:site_name" content="Formground">
<meta property="og:image" content="https://formground.com/favicon-192x192.png">
<link rel="canonical" href="https://formground.com/for-creators.html">
<meta name="twitter:card" content="summary">
<meta name="twitter:image" content="https://formground.com/favicon-192x192.png">
<meta name="twitter:title" content="For Creators — Formground">
<meta name="twitter:description" content="Production partners, resources and suppliers for architects, designers, and makers.">
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
  <a href="marketplace.html">Marketplace</a>
  <a href="for-creators.html" class="current">For Creators</a>
</nav>
</header>

<main>

  <h1 class="sr-only">For Creators</h1>

  <div class="search-wide">
    <div class="ask-box">
      <i class="ti ti-search" aria-hidden="true"></i>
      <input type="text" placeholder="Find production partners, resources and suppliers" autocomplete="off">
    </div>
  </div>

  <div class="chips">
{chips_html}
  </div>

{panels_html}

  <p class="foot-note">
    This list doesn't imply any partnership or endorsement beyond what's stated above. &middot; &copy; 2026 Formground &middot; <a href="/">← Back to Formground</a> &middot; <a href="privacy.html">Privacy</a> &middot; <a href="about.html">About</a>
  </p>

</main>

<script>{PAGE_SCRIPT}</script>

{CLOUDFLARE_BEACON}
</body>
</html>
"""


def main():
    page = render_page()
    for target_dir in ("docs", "frontend"):
        out_path = REPO_ROOT / target_dir / "for-creators.html"
        out_path.write_text(page)
        total_craftspeople = len(CRAFTSPEOPLE)
        total_tools = sum(len(v) for v in TOOL_CATEGORIES.values())
        print(f"Wrote {out_path} ({total_craftspeople} craftspeople, {total_tools} tools/services, 7 guide articles)")


if __name__ == "__main__":
    main()
