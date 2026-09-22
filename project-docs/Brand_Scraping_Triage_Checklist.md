# Brand Scraping Triage Checklist

A quick, time-boxed check to run on any brand before investing in a real
extractor — meant to take a few minutes per brand, not a deep dive. With
23+ candidate brands and a Phase 1 target of only 15-30, it's cheaper to
move on to the next brand than to force a hard one to work.

## The checks, in order

1. **Is there a clean, documented API?** Shopify (`/products.json`) and
   WooCommerce (`/wp-json/wc/store/v1/products`) both expose one for free —
   check these first on any e-commerce-platform brand before writing any
   HTML parsing at all. **A 200 response with valid JSON isn't proof the
   API returns the whole catalog** — a headless/composable storefront can
   leave the classic public endpoint live but scoped to only a handful of
   products (confirmed on Made by Choice: `/products.json` returned just
   3 items - one product line's variants - while the site's own nav
   listed 8 more real collections with nothing in the feed). Cross-check
   the API's product count against the number of distinct `/products/`
   or `/product/` links on the site's own "all products" page before
   trusting it; a big mismatch is a fail, not a smaller-than-expected
   brand.
2. **If not, does a single page reveal real server-rendered content
   easily?** Fetch one plausible listing/product page and look for actual
   product names, materials, or prices in the rendered HTML. If all you
   get back is navigation/menu text and the real content only shows up
   after JavaScript runs (React/Vue/Nuxt hydration), that's a fail —
   defer rather than reach for a headless browser (per the project's own
   Phase 1 policy: JS-rendered sites are deferred, not solved upfront).
3. **Roughly how many fetches would a full catalog need?** Look for a
   sitemap, a pagination signal (`hasMorePages`, `X-WP-TotalPages`), or
   count links on one listing page and extrapolate. More than ~30-40
   fetches for one single brand's catalog is a fail at this stage - not
   impossible, just not a good use of scraping time compared to another
   brand that's already clean.
4. **Does robots.txt single out this bot/AI crawlers specifically?** A
   generic AI-crawler listing (common Squarespace/WordPress boilerplate)
   is fine. A *dedicated* `Disallow: /` record for a specific bot (e.g.
   `ClaudeBot`), separate from the general wildcard rule, is a real,
   deliberate exclusion — respect it, don't route around it. **Test with
   the scraper's own real `HEADERS` User-Agent, not a generic one** -
   confirmed on De Padova (2026-09-13): the site returns real content to
   a plain `Mozilla/5.0` curl but a live 403 to `scrape.py`'s actual
   `FormgroundBot` User-Agent specifically - an active WAF block that a
   manual curl check with a different UA string would miss entirely. A
   brand that "works" in manual triage but 403s under the real scraper
   is excluded, not worked around with a different UA - same
   don't-route-around-it principle as a named robots.txt block, just
   enforced by the server instead of a text file.

5. **Does the raw category/product_type data mix non-product listings
   into the main catalog?** For a Shopify/WooCommerce brand, glance at
   the distinct `product_type`/category values across the catalog (not
   just one item) before writing the extractor. Red-flag words: sample,
   swatch, spare (part), replacement, service, customization, finish,
   course, class, workshop. Finding a few of these isn't a reason to
   defer the brand - they're usually fixable with a clean, structural
   exclusion once found (see `EXCLUDED_CATEGORIES` in `scrape.py`) - but
   it's a heads-up to budget that investigation time up front rather
   than discover it listing-by-listing after the fact. In Common With is
   the case that prompted this: Finish Samples, Swatches-equivalents,
   Service fees, and a certification-mark-as-category bug (Pinch's "UL"/
   "CE") all surfaced only after building the extractor, not during
   triage - a quick category scan at triage time would have caught the
   pattern immediately and saved several rounds of "found this after the
   fact" fixes.

6. **Is the `vendor` field (Shopify) actually the brand itself on every
   listing, or does the store resell other brands too?** Confirmed on
   Asplund (2026-09-22): a real Shopify store, real `products.json`,
   real robots.txt - but of 789 raw listings, only ~225 carried an
   Asplund house vendor; the rest were dozens of *other*, separately
   real design brands being resold (Fredericia, Wästberg, Maruni,
   Alessi, Living Divani, ...) plus third-party skincare/candles
   (MALIN+GOETZ). Several of those resold brands are already their own
   independently-triaged Formground entries - scraping everything under
   "Asplund" would have misattributed their work and duplicated them
   under the wrong name. Check the spread of `vendor` values across a
   sample before building (`Counter(p["vendor"] for p in products)` on
   one `products.json?limit=250` page is enough to spot it) - a
   multi-brand boutique needs a vendor filter to its own house line(s)
   before anything else in this checklist matters.

If a brand fails any of these within a few minutes, mark it
`"scrapable": false` in `scraper/brands.json` with a one-line reason and
move to the next brand on the list, rather than sinking more time in.
Check #5 is the exception - it's a heads-up, not a fail condition; note
what you found and keep going unless it looks unusually extensive.

**Exception - a brand with real data one level up.** Before deferring a
brand purely for failing check #2 (no individual products), check whether
it publishes something coarser but still real - named collections/series,
for instance. If a quick check of one of those confirms there's genuinely
nothing more granular underneath (no per-piece names, materials, or
dimensions - not just a page that needs more digging), index at that
coarser level instead of skipping the brand entirely. This is "brand is
the minimum unit of inclusion" applied one level down: a collection is a
legitimate unit when that's the finest-grained real data a brand
publishes. Paola Paronetto is the first case of this - see below.

## Applied so far (2026-09-07)

| Brand | Check failed | Verdict |
|---|---|---|
| Baleri Italia | none at triage - built, but its `page` param turned out to be silently ignored in practice (every page returns the same 24 products, `hasMorePages` always true). Now fetches just that one reliable page rather than looping forever; real catalog is likely larger than the ~24 products captured. | **Built (partial coverage)** |
| Salvatori | #3 - real per-product data, but split across ~215 separate collection pages | Deferred |
| Marset | #3 - ~98 product pages needed, and content wasn't quickly confirmable on a first pass | Deferred |
| New Works DK | #2 - Nuxt.js SPA, product listings are client-rendered with no server-side links | Deferred |
| Paola Paronetto | #2 initially - listing page only shows named collections, not individual products. Resolved by indexing at the collection level instead of skipping the brand (see below) | **Built (collection-level)** |
| In Common With | #5, discovered after the fact rather than at triage - Finish Samples, Service fees, a Swatches-equivalent, and a certification-mark-as-category bug all needed cleanup. Considered removing the brand entirely (2026-09-08) rather than keep fixing it, but after the fixes above, 220 real results remain and a sample check confirmed the "no category" ones are genuine products (Arundel Orb Pendant, Murano Glass Cosmos Chandelier, etc.), not more junk - kept. This is the case that prompted adding check #5. | **Built (kept after cleanup)** |
| Made by Choice | #1, discovered after building rather than at triage - `/products.json` returned 200 with valid JSON (3 real products), passing a naive "does the API work" check, but the site's own nav listed 8 more real collections (Airisto, Beebee, Laakso, Cabinets, Seating, Tables, Accessories) with zero of their products in that feed - a headless/composable Shopify setup. Removed after shipping and re-checking, rather than leave a 3-product listing that misrepresents the brand. This is the case that prompted adding the count cross-check to #1 (2026-09-13). | Deferred (needs bespoke work) |
| De Padova | #4, discovered after building rather than at triage - WooCommerce with the Store API disabled, but real server-rendered category pages and product pages were confirmed live during manual triage (curl with a generic UA). Failed once actually run through `scrape.py`: a live 403 under the scraper's real `FormgroundBot` User-Agent specifically. This is the case that prompted testing check #4 with the real scraper headers, not a generic one (2026-09-13). | Deferred (WAF blocks the scraper's real UA) |
| Asplund | #6, discovered after building rather than at triage - real Shopify store, but a multi-brand boutique reselling dozens of other real brands (Fredericia, Wästberg, Maruni, ...) plus third-party skincare/candles under the same catalog; also #5, separately - its `product_type` field was unreliable even within its own house lines (untranslated Swedish, a flatly wrong assignment, a designer name leaking through as a category). This is the case that prompted adding check #6 (2026-09-22). | **Built (vendor-filtered to house lines, 225 of 789 raw listings)** |
| Byarums Bruk | #5 - 106 of 183 real catalog entries (58%) were replacement components ("Beslag till Classic bord" - fitting FOR the Classic table), not standalone objects, caught via the Swedish "till" ("for") construction. | **Built (106 spare-part listings excluded)** |
| Fabrikant | none at triage - built, but its WooCommerce Store API returned 200 + `Content-Type: application/json` with raw `<style>` HTML leaked into the response before the real JSON payload (a server-side theme/plugin bug, not something triage would catch). `_fetch_json` now retries the parse from every bracket position in the response before giving up. | **Built (after a `_fetch_json` resilience fix)** |
| Interesting Times Gang, G.A.D | Passed all checks cleanly - real domain needed correcting first for Interesting Times Gang (itg.studio, not the dead interestingtimesgang.com) | **Built** |
| Blå Station | #2 initially - /products listing is mostly client-rendered - resolved the same way as Paola Paronetto/Fogia: ~60 real, server-rendered /family/{slug} and /product/{slug} pages exist underneath it. Also a variant of #5/#6 - the same real model surfaces as a "related family" card on more than one top-level page (Arc A44 appears on both /family/acoustic-family and /product/decofunc), needing a global dedupe-by-model-code pass rather than a per-page one. No taxonomy/category field is exposed anywhere (checked the WP REST API directly - no custom taxonomy on the `product`/`family` post types), so category coverage stays partial (~43%) - breadcrumb trail on /product/ pages, keyword-matched member titles on /family/ pages, blank otherwise, same accepted tradeoff as In Common With. | **Built (221 products, partial category coverage)** |
| Gärsnäs | None at triage - real, server-rendered WordPress catalog behind 6 category pages (no pagination), each product page carrying a real image gallery, a "Design {name} {year}" credit, and a real dimensions field. A handful of products share an identical display name with a genuinely different real product (different URL, different image, e.g. "Akustik III" and "Akustik karmstol") - not a scraping artifact, the brand's own site names two distinct models the same; kept as separate rows since each is a real, separately addressable product. | **Built (110 products, 0 blank category/image)** |
| Norrgavel | #3 - real, server-rendered per-product pages (not a JS-rendering problem), but its own products sitemap lists 1,615 individual URLs with no lighter API to group color/finish variants before fetching - well beyond the project's own past deferral threshold (Salvatori at 215, Marset at 98). User wants to revisit once there's a way to include a brand via a real curated subset rather than an all-or-nothing scrape - see project memory ("partial-catalog inclusion") for the open design question. | Deferred (user flagged for revisit) |
| Davsjö | None at triage - Webflow, no product API, but a real sitemap.xml lists all 68 real /product/ pages directly. Each page's own `<h1>` is a clean "{code} \| {category text} \| {finish}" string, used directly as category rather than guessed from the product name. | **Built (68 products, 0 blank category/image)** |
