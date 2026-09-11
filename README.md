# Formground

A product discovery search tool for small/independent design brands
(furniture, lighting, ceramics, objects). Built by scraping brand sites
directly - no accounts, no submissions required from brands, nothing to
maintain on their end.

This README explains what's in this repo in plain terms - you don't need
to read or understand the code itself to know what each part does.

## What's in here

| Folder | What it does |
|---|---|
| `scraper/` | Visits brand websites and pulls out product info (name, category, material, link) |
| `data/` | Where all the scraped info gets stored (a single database file), plus a `last_scrape_report.json` showing how long the last run took, per brand - worth a glance after any run so a slow or misbehaving site gets noticed quickly rather than after the fact |
| `backend/` | Answers searches - both the human ask-box and the AI-agent version |
| `frontend/` | The actual ask-box web page a person uses - a single static HTML file, no build step |
| `tests/` | A small set of automatic checks covering the specific bugs that have already slipped through once (a bad search match, duplicate/stale scraped data) - runs automatically on every change, so one of those can't quietly come back unnoticed |
| `.github/workflows/` | Runs the scraper automatically on a schedule, and the tests above on every change - no manual work needed |

## How things run day-to-day

**You don't need to run anything by hand.** The scraper runs automatically
once a week via GitHub Actions. If you want to trigger it manually:

1. Go to this repo on GitHub
2. Click the **Actions** tab
3. Click **Scrape brand sites** on the left
4. Click the **Run workflow** button

That's the entire manual interaction most weeks.

## Current status

- 23 brands confirmed and listed in `scraper/brands.json`
- 16 of 23 have a working scraper and real data (~1,840 records total,
  86% with a real product image):
  Kieran Kinsella, H. Bigeleisen, Yird Ceramics, Baleri Italia, and Paola
  Paronetto have brand-specific extractors; Minimalux, Pinch, Bitossi
  Ceramiche, GATOMIKIO, 101cph, In Common With, Anna Löwenhielm Ceramics,
  A. Petersen, and Luke Hope all run on Shopify and share one generic
  extractor; Verk and Another Country run on WooCommerce and share
  another. Two known partial/special cases: Baleri Italia's pagination
  doesn't work, so only its first ~24 products are captured, not its full
  catalog; Paola Paronetto only publishes named design collections, not
  individual products, so each of its 37 collections is indexed as one
  entry rather than a specific piece - a deliberate choice, not a gap
  (see the triage checklist for the reasoning).
- 4 brands are excluded on purpose for policy reasons, documented in
  `scraper/brands.json`: Bennet Schlesinger and Atelier de Troupe
  (robots.txt disallows automated/AI access), Nikari (blocked by
  Cloudflare bot management), Sizar Alexis (own site is JS-rendered -
  deferred rather than adding a headless browser for one brand)
- 3 brands are deferred as not worth the effort right now, per
  `project-docs/Brand_Scraping_Triage_Checklist.md`: Salvatori (real
  data, but split across ~215 separate pages), Marset (~98 separate
  pages needed), New Works DK (JS-rendered SPA)
- The scraper has hard safety limits (max time per brand, max time per
  run) after a scraper run was once left running far longer than it
  should have - see `last_scrape_report.json` after any run to check
  it stayed well within them. These limits already caught one real bug:
  Baleri Italia's broken pagination looping on the same page for the
  full 5 minutes before the fix went in.
- The backend (`main.py`) is built but not yet deployed anywhere live.
  Its query engine now caps any single brand to 3 results per search
  (`MAX_RESULTS_PER_BRAND` in `query_engine.py`), so a brand with a large
  catalog can't crowd out smaller makers in a single search's results.
- **The full pipeline has now been tested end-to-end with a real API key
  and real data** (2026-09-07) - search box → LLM query translation →
  filter → per-brand cap → real result cards, all confirmed working
  locally. Two real bugs were found and fixed by this real test, not by
  reading the code: Kieran Kinsella's products were all literally named
  "Kieran Kinsella" (the extractor was reading the page's site-logo
  `<h1>`, not the actual product `<h3>`), and the Enter key didn't
  reliably submit the search box (fixed with an explicit keydown handler
  rather than relying only on native form-submit-on-Enter). Neither
  would have been caught without actually running it.
- `frontend/index.html` is a minimal, working implementation of the two
  existing mockups (empty state + results grid) - one static file, no
  framework, no build step, calls the backend's `/search` endpoint. Not
  deployed anywhere yet; edit the `API_BASE` constant near the bottom of
  the file once the backend has a real URL.
- **Real product images now show on result cards** (2026-09-07) - this
  was a genuine gap, not a styling choice: no extractor had ever captured
  an image URL, despite the original Phase 1 plan explicitly calling for
  one and the whole legal/product model resting on "thumbnail +
  link-back." Every extractor now captures a real image where the source
  site has one (86% of all records do - the rest are mostly spare-parts
  listings the brand itself never photographed, not a scraper gap). Falls
  back to a category icon only when there's genuinely no image or the
  real one fails to load.
- **The Shopify/WooCommerce "variant listed as a separate product"
  dedup now also splits on a comma** (e.g. "Gallon Side Table, Low" /
  "Gallon Side Table, Tall" → one "Gallon Side Table" entry with both
  merged into its material/variant list), not just `/`, `-`, `–`, `—`.
  This caught real, previously-uncaught duplicates on both Another
  Country (WooCommerce) and 101cph (Shopify) - `extract_woocommerce` had
  no grouping logic at all before this. WooCommerce names/categories are
  also now HTML-entity-decoded ("Ash &amp; Walnut" → "Ash & Walnut").
- The LLM the query engine uses is swappable by environment variable, not
  hardcoded - set `LLM_PROVIDER` (`anthropic` or `openai`) and/or
  `LLM_MODEL` to change provider or model for cost reasons, with no code
  changes. See the comment at the top of `query_engine.py` for details.
  Defaults to Anthropic's `claude-haiku-4-5-20251001` - a small,
  cheap/fast model is a deliberate choice here, not a placeholder: this
  step only extracts category/material/style/color from a short search
  query into JSON, a simple task that doesn't need a bigger model.
- **The specific model name (`DEFAULT_MODELS` in `query_engine.py`) is a
  setting to revisit occasionally, not a set-once value.** Model names
  get renamed/deprecated and cheaper or better options appear over time -
  when Claude Code (or anyone) touches this file, worth a quick check
  that the configured model still exists under that name and is still
  the best cost/quality tradeoff, rather than assuming it's still
  current.

## What happens next (in order)

1. Deploy the backend to Google Cloud Run and the frontend to a static
   host (Netlify/Vercel/GitHub Pages) so search actually works live -
   both are built and tested locally, neither is deployed yet
2. Wire up analytics (GA4, or at least basic click-through logging) so
   brand traffic summaries become possible
3. Decide whether to revisit any deferred brands (see the triage doc)

## A note on scope

This is a personal Phase 1 tool to prove the concept - not a finished
product. Nothing here costs money to run at this scale (GitHub Actions
and Cloud Run are both free or near-free at low usage).
