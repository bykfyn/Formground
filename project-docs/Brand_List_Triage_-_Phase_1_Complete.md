# Brand List Triage — Phase 1 (Complete)

## Confirmed, with own site

| Brand | Site | Notes |
|---|---|---|
| Kieran Kinsella | kierankinsella.com | Squarespace, static/fetchable. Gallery page is unstructured process photography — no per-product data. "Wood"/"Ceramic" pages worth checking specifically for structured listings. |
| Sizar Alexis | sizaralexis.se | Real structured data on his own site — named pieces, dimensions, materials. Also on 1stDibs/Monde Singulier/Galerie Philia with richer data. |
| Minimalux | minimalux.com | Standard e-commerce (page-refresh cart behavior). |
| Pinch | pinchdesign.com | Established UK brand, standard catalog structure. |
| Bitossi Ceramiche | bitossiceramiche.it | Standard e-commerce pattern. |
| Nikari | nikari.fi | Real per-product pages, product carousel confirmed. |
| Atelier de Troupe | atelierdetroupe.com | Dedicated /products/furniture page — real catalog structure. |
| Paola Paronetto | paolaparonetto.com | Own site confirmed; content skews editorial/bio, product-level structure not yet confirmed — worth a direct check. |
| Another Country | anothercountry.com | Established UK brand, real catalog. |
| Salvatori | salvatoriofficial.com | Established Italian brand, real catalog with category pages (living room, home collection, etc.). |
| Marset | marset.com | Established Spanish lighting brand. |
| GATOMIKIO ("gatomikio_shouten") | gatomikio-store.com (+ gatomikio.jp, gatomikio-1.com) | Real, established Japanese lacquerware company (founded 1908). Real e-commerce site with cart. |
| A. Petersen ("apetersen_collection") | apetersen.dk | Real Danish furniture maker, own site with journal/news content. |
| H. Bigeleisen | hbigeleisen.com | Real Brooklyn design practice (founded 2020), Squarespace, static/fetchable. Has a dedicated "In Stock" catalog page separate from portfolio/design pages. |
| Luke Hope / Hope in the Woods | lukehope.com | Real, well-documented maker with own site. |
| Yird Ceramics | yirdstudio.com | Genuinely tiny, independent Warsaw-based potter (Aleksander Kozera) — real own site despite the Instagram-handle-style name. |
| Bennet Schlesinger | bennetschlesinger.com | Real, well-covered designer (Interior Design, Surface, Sight Unseen). Site confirmed live, but **robots.txt currently disallows automated fetching** — needs manual scrapability review or respectful exclusion at Step 4, not a standard scrape target. |
| 101cph (101 Copenhagen) | 101cph.com | Established brand, real catalog structure. |
| New Works DK | newworks.dk | Established Copenhagen brand, real shop structure (/en/shop/). |
| Baleri Italia | baleri-italia.com | Established Italian brand, real catalog. |
| Anna Löwenhielm Ceramics | annalowenhielm.se | Real own site with /collections/all product page. Also a member of Konsthantverkscentrum — already tracked as an association in the Sheerd workbook. |
| Verk | verk.se | Real Swedish furniture brand, own site, real products. Also appeared independently in the Stockholm Furniture Fair exhibitor list pulled earlier this session. |
| In Common With | incommonwith.com | Real Brooklyn lighting design studio (founded 2018, Nick Ozemba & Felicia Hung). Standard e-commerce structure, real catalog including a /collections/all-lighting page. |

## Dropped
- **20by8** — no matches found across multiple search attempts and spelling variants. Not a design brand, ceramics studio, or maker under any tried search. Dropped from scope; can be revisited if a source or alternate spelling ever surfaces.

## Summary
23 of the original 24 brands confirmed with real, identifiable sites — the large majority genuinely fetchable with standard e-commerce or portfolio structures. Only 20by8 was dropped as unresolvable. Even the Instagram-handle-style names (GATOMIKIO, A. Petersen, Yird) turned out to have real sites — the earlier assumption that handle-style naming meant no site existed continues to not hold up.

**Recurring pattern worth keeping in mind for the scraper build**: several sites (Kieran Kinsella, Paola Paronetto) are fetchable but may not have per-product structured data on their main pages — some pages are galleries/portfolios rather than catalogs. Worth checking specific sub-pages (e.g. Kieran Kinsella's "Wood" and "Ceramic" pages) before concluding a brand can't be included.

**New pattern from this round**: not every "real site" is a straightforward scrape target — Bennet Schlesinger's site is confirmed live but blocks automated access via robots.txt. Worth deciding early in Step 4 whether the scraper respects robots.txt as a hard rule (likely, given the fair-use/goodwill framing already established) or whether sites like this get manually reviewed case-by-case instead.
