# Formground site patterns

One page of rules so the same thing looks and behaves the same everywhere,
whichever page a visitor is on. **Check this before building or changing a
layout, and update it in the same change when a pattern changes.**

Drafted 2026-10-04 from what the code already does (home `frontend/index.html`,
the generators in `scraper/generate_*.py`). Where the pages disagreed, the
pattern below is the one chosen; the note says which pages were brought in line.

## 0. URL structure and navigation

Each nav item owns a URL namespace; a name never means two different pages.

```
/work.html                 search + the "browse by type" menu (four chips: Houses / Furniture / Lighting / Objects)
/work/<category>.html      furniture | lighting | objects - the types as photo tiles
/work/<type>.html          the full catalogue of one type; pages -2, -3 ... (flat: group is a breadcrumb)
/work/houses.html          every house (60 per page); /work/houses-<country>.html houses standing in that country (8+)
/edits.html                hub;  /edits/<slug>.html  the curated Edits
/brands/ /architects/ /designers/    unchanged
```

- One taxonomy (`scraper/work_menu.py`: categories -> groups -> types) feeds the menu, the
  category pages, breadcrumbs and the sitemap. To add a type: add it to `BROWSE_CATEGORIES`
  (generate_browse_pages.py) in a group that `TAXONOMY` lists.
- Type URLs stay flat so regrouping never breaks a link.
- Chairs have sub-type pages (dining, armchairs, side, garden and outdoor, folding and stacking, office and
  desk). A chair whose only tag is generic gets its sub-type from its NAME (`_refine_chair_subtype` in
  scrape.py; `backfill_chair_subtypes.py` for existing rows); chairs the name cannot place are labelled
  from the photo by Haiku (`classify_chairs_vision.py`, confident labels only, results kept in
  data/chair_vision_labels.json). A sub-type needs about 25+ products to get a page; rocking chairs
  (14) stay a tag only.
- Tables work the same way (`classify_tables_vision.py`, labels in data/table_vision_labels.json): only labels
  at 0.9+ are applied (the 0.85 bucket was wrong about a quarter of the time); the rest stay in the generic
  Tables bucket. Bedside, Outdoor and Bar Tables got pages.
- Menu: four category chips under the search bar, Houses first to mirror the home page bento
  (Houses left, then Furniture, Lighting, Objects). The panel's title ("Furniture →") is the link up to the category page, plain text on the category's own page. Each opens a panel of groups and types as
  plain links to the static pages (fast, indexable, shareable): one click to any category, no
  single "Browse" chip or tabs (decided 2026-10-04: four chips mirror the home page and save a
  click).
  "Surprise me" is the fifth chip, after Objects (an action, not a category; shuffle icon), so the
  search box only searches. On phones the chip row is a swipeable one-row slider that bleeds to
  the screen edges (the next chip peeks, the right edge fades, the current category's chip is
  scrolled into view). Left-aligned under the intro on type and category pages. Chips follow the form-chip
  family below. The chip of the category you are in is shown selected (darker text and border);
  its panel stays closed so the products remain above the fold (ad landing pages).
- Houses are a category of Work like the others (a house is an architect's product): home tile ->
  /work/houses.html, a Houses column in the menu, country pages, and each house card links to the
  architect's own project page and names the practice. Country = where the house STANDS: the
  country its location text names ("Aarhus, Denmark" - 12 houses stand outside their architect's
  home country), else the architect's own country. Country pages say "Houses in Sweden" and list
  their practices (with house counts) as links to the architect pages.
- House cards are the exception to square cards: landscape 4:3 photos in 4 columns (3 on tablet,
  2 on phones), name / location . year / "by practice" each on one line so every row is even.
  On phones the four category chips drop their chevrons so all four fit one row.
- Moved pages leave a redirect stub at the old address (`scraper/redirects.py`; GitHub Pages
  cannot send a 301): old /browse/*, /floor-lamps.html, the top-level Edit slugs and the
  retired category pages all redirect. The sitemap lists only real pages, and no live page
  links to an old address (`tests/test_work_structure.py` enforces all three).
- Moved 2026-10-04 from /browse/ and the site root, before ads started, so no paid or
  inbound traffic had to be carried over.

### Category pages (/work/furniture|lighting|objects.html)

Same header block as a type page (nav with Work current, Work-style search box, the four chips with the
current category selected, centred title, one results line ending in "Themed Edits ->"), then the types
as photo tiles grouped by section. Built by `render_category_page`; styles shared with the type pages.

### Listing template (type pages) - ALL types, 2026-10-04 (piloted on Table Lamps)

A type page must look like the Work page showing one type, not like a different kind of page. It is
built from the Work page's own pieces: the nav with Work current, the same search box (submitting
goes to /work.html?q=..., "Surprise me" to /work.html), the four chips (the current category's chip
selected), a centred title and results line ("816 table lamps from 77 makers, listed in full - page 1
of 3, no rankings, not paid for", plus "Themed Edit: <Edit> ->" when an Edit covers the type; always call these Edits / Themed Edits, never "curated selection"),
the same cards with the share button, a pager, then "Makers" (top 40 with counts, each linking to the
maker's page) and "More in <category>" siblings.

Page size follows Lighthouse's ~1,400-DOM-element limit and Baymard's 24-72 items per page: 60 cards
per page (divides every column count 6/4/3/2, so no ragged row; ~1,000 elements where 300 made
~3,400), a "See more" link that loads the next 60 in place (a real link to the next numbered page
without JavaScript, `frontend/listing.js`) and a compact pager "1 2 ... 13 Next". Every numbered page
stays a crawlable URL with its own canonical. Click tracking is delegated, so appended cards count.

Styles come from ONE shared file,
`frontend/work-results.css`, linked by both /work.html and the listing pages - edit it there, never
in either page. Every type page uses this template (rolled out 2026-10-04 after the Table Lamps pilot
was approved; the old 300-card renderer is deleted, so type page numbers grew: Chairs 6 -> 28 pages
of 60). The Houses pages still use their own template (landscape 4:3 cards) and could move onto this
one later.

## 1. Banners (the wide photo with one featured product)

Used on: home (Sofas, Two Seater Sofas), the Edits hub, every Edit page.

- **Title row ABOVE the photo.** The edit/section name on the left, a "See the
  edit →" / "See all →" link on the right (internal link).
- **Clean photo.** 2:1 frame (4:3 on phones), 0.5px border, no text laid over it.
- **Caption BELOW the photo:** the product name, then the maker underneath
  (smaller, secondary colour). Photo and caption both link to the maker's own
  site, new tab.
- Hierarchy: the edit/section title is primary, the product and maker are secondary.
- Never overlay text on a featured-product banner photo. (The Edits hub did, a leftover from
  Promotions; changed 2026-10-04. The Promotions overlay style is retired.)

### Page masthead (the one exception to "no text on a banner photo")

A masthead is the photo that IS a page's header, not a featured-product banner. Used
on the Edits hub (chosen 2026-10-04 over the classic title-row layout and over
white/sentence-case variants): the page title ("EDITS", Archivo 700 uppercase, 60px)
and the preamble sit on the photo in near-black, over the plain wall at the top; **no
overlay or shading on the photo**; a small light credit pill (bottom right) names and
links the pictured product's maker. It only works on a photo with a plain area to
hold the text - for a dark photo set `HUB_MASTHEAD_TEXT = "light"`, and never add a
scrim to rescue a busy photo; pick another photo. `HUB_LAYOUT = "classic"` restores
the title-row-above banner.

## 2. Tiles (the home page bento, the Edits hub's featured edit)

- The photo fills the tile; the category/edit title sits top-left on it
  (Archivo 700, white, soft dark scrim so it reads on light photos).
- Hover reveals the pictured product, its maker and a "Visit site" pill.
  On touch screens and under 760px those are always visible.
- The tile itself links to the category/edit; the pill links to the maker.

## 3. Product cards (grids)

- Square image, name (13px, 500), maker (12px, muted). No price on the card.
- Grids are a **fixed** column count, never auto-fit: 6 across, 4 under 960px,
  2 under 640px (gaps 20px, 16px on phones).
- Every card links straight to the maker's own site; nothing is sold or held on Formground.

## 4. Photos

- Ask the maker's server for the size the photo is shown at
  (`scraper/image_sizes.py`: CARD 500, TILE 1000, HERO 1600; the same rules are in
  `frontend/search.js`). Hosts without a verified resize rule are left alone.
- Show the whole photo (on its own edge colour) when it is clearly off-square on a
  flat background (`scraper/image_fit.py`); cropped photos need a different image,
  not a different crop.
- A product in a banner is **not repeated** in that page's grid; the grid backfills,
  and the piece count includes the banner product (13 on an edit with a banner).
- Images are always hotlinked and credited; a maker whose images cannot be loaded
  from our pages is excluded, never worked around.

## 5. Chips

Three families, each with ONE height, shape and weight. A new chip copies one of
them; it does not invent a fourth. (Aligned 2026-10-04: "Surprise me" was
squarer than the other form chips, the search-bar chip was bolder than the filter
chips, and the "N finishes" badge was shorter than the brand tags.)

| Family | Used for | Height | Text | Shape |
|---|---|---|---|---|
| Form chip | the scope chip inside a search bar ("Edits", "Makers"), tier filters, "Surprise me" | 32px | 13px, weight 500 | full pill (999px) |
| Photo pill | "Visit site" on tiles, the photo credit on the Edits masthead | 27px | 11px, weight 600 | full pill, glass background (light or dark to suit the photo) |
| Small label | brand-page tags (Lighting, Objects, country), the "N finishes" badge | 23px | 11px | 10px corners; the tag is outlined, the badge filled (both carry a 0.5px border so the box is identical) |

- Search bars: 60px tall with a chip, 57px on the home page (no chip); 900px wide, centred,
  on every page including Edits (decided 2026-10-04: it stays 900px rather than matching the
  1160px banner/grid edges, so it is the same everywhere).

## 5b. Icons and performance rules

- Icons are `<i class="ti ti-NAME">` drawn from `frontend/icons.css` (inline SVG masks, no
  font download; the Tabler icon font was 450KB per page for 13 icons). To add one: add the
  Tabler name to `ICONS` in `scraper/build_icon_css.py` and run it - never link an icon font.
  `tests/test_icons.py` fails if an icon class is used but not drawn.
- Shared assets are linked with a content hash (`/icons.css?v=...`, `scraper/site_assets.py`)
  so browsers never keep a stale copy next to new pages.
- No layout shift: a page that fills in after loading must not move what is already visible
  (the Work page keeps its footer invisible until results arrive - `finishLoading()` in
  `search.js`; CLS 0.124 -> 0).
- Photos are requested at card size (section 4); a new image host needs a verified rule in
  `scraper/image_sizes.py` and `search.js`.

## 6. Type and spacing

- Page title: Archivo 700. Edits hub 60px uppercase on the masthead photo (44px in the "classic" layout, see HUB_LAYOUT in generate_edits_page.py), Edit page 36px.
- Banner/section title: Archivo 700 (hub 26px, home group rows are the smaller 14px label style).
- Card text 12-13px; secondary text uses `--text-secondary` / `--text-muted`.
- Breakpoints used everywhere: 959px (4-column grids), 760px (tiles show details,
  stacked layouts), 639px (2-column grids).
- Header nav (every page): Work · Creators · Edits · For Creators.

## 7. Links and tracking

- Product and photo links go to the maker's own site (`target="_blank"`,
  `rel="noopener noreferrer"`). Titles, "See the edit →" and tiles go to our own pages.
- A new page type gets click tracking by inheriting `fg-track.js`; do not add a separate tracker.

## 8. Before you change a layout

1. Find the other places that show the same thing (grep the class names across
   `frontend/` and `scraper/generate_*.py`) and change them together.
2. Mock it up and check desktop and phone width before pushing a visual change.
3. Update this page.
