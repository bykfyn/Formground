# Brand Scraping Triage Checklist

A quick, time-boxed check to run on any brand before investing in a real
extractor — meant to take a few minutes per brand, not a deep dive. With
23+ candidate brands and a Phase 1 target of only 15-30, it's cheaper to
move on to the next brand than to force a hard one to work.

## The checks, in order

1. **Is there a clean, documented API?** Shopify (`/products.json`) and
   WooCommerce (`/wp-json/wc/store/v1/products`) both expose one for free —
   check these first on any e-commerce-platform brand before writing any
   HTML parsing at all.
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
   deliberate exclusion — respect it, don't route around it.

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
