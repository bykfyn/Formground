# Formground site patterns

One page of rules so the same thing looks and behaves the same everywhere,
whichever page a visitor is on. **Check this before building or changing a
layout, and update it in the same change when a pattern changes.**

Drafted 2026-10-04 from what the code already does (home `frontend/index.html`,
the generators in `scraper/generate_*.py`). Where the pages disagreed, the
pattern below is the one chosen; the note says which pages were brought in line.

## 1. Banners (the wide photo with one featured product)

Used on: home (Sofas, Two Seater Sofas), the Edits hub, every Edit page.

- **Title row ABOVE the photo.** The edit/section name on the left, a "See the
  edit →" / "See all →" link on the right (internal link).
- **Clean photo.** 2:1 frame (4:3 on phones), 0.5px border, no text laid over it.
- **Caption BELOW the photo:** the product name, then the maker underneath
  (smaller, secondary colour). Photo and caption both link to the maker's own
  site, new tab.
- Hierarchy: the edit/section title is primary, the product and maker are secondary.
- Never overlay text on a banner photo. (The Edits hub did, a leftover from
  Promotions; changed 2026-10-04. The Promotions overlay style is retired.)

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

## 5. Type and spacing

- Page title: Archivo 700. Edits hub 44px (uppercase), Edit page 36px.
- Banner/section title: Archivo 700 (hub 26px, home group rows are the smaller 14px label style).
- Card text 12-13px; secondary text uses `--text-secondary` / `--text-muted`.
- Breakpoints used everywhere: 959px (4-column grids), 760px (tiles show details,
  stacked layouts), 639px (2-column grids).
- Header nav (every page): Work · Creators · Edits · For Creators.

## 6. Links and tracking

- Product and photo links go to the maker's own site (`target="_blank"`,
  `rel="noopener noreferrer"`). Titles, "See the edit →" and tiles go to our own pages.
- A new page type gets click tracking by inheriting `fg-track.js`; do not add a separate tracker.

## 7. Before you change a layout

1. Find the other places that show the same thing (grep the class names across
   `frontend/` and `scraper/generate_*.py`) and change them together.
2. Mock it up and check desktop and phone width before pushing a visual change.
3. Update this page.
