# Formground — Context Summary

## What it is

A lean, opt-out (not opt-in) product discovery search tool for small/independent design brands — furniture, lighting, ceramics, objects. Built by scraping brand sites directly rather than asking brands to submit or maintain anything. No accounts, no checkout, no curation of results.

## Why this shape (the reasoning behind the files)

The core gap it targets: tested live against real queries during development — general web search and image search reliably surfaced only mass-market retailers (Wayfair, AllModern, Etsy); Architonic-scoped search surfaced real, structured, designer-attributed results, but only for brands established enough to be onboarded there. The gap that's genuinely unserved is the tier below what platforms like Architonic, Chairish, or Adorno accept — the smallest, least-resourced makers.

**Why scrape-and-link, not opt-in submission:** removes the cold-start problem entirely (a brand doesn't need to decide to participate before there's any traffic to justify it). Thumbnail + link-back to source follows the same fair-use pattern Google Images operates on; full-size rehosting would not. Remove-on-request handles goodwill/legal edge cases without requiring upfront permission.

**"Brand is the minimum unit of inclusion," not the product catalog:** a brand with one product or no structured catalog (just a portfolio/gallery) still gets a real entry — name, image, link, whatever exists. Rich taxonomy/multiple products is additive, never a bar to clear. This was a deliberate correction partway through development — the first instinct (product-attribute search only) would have structurally excluded exactly the smallest makers the tool is meant to serve.

**Taxonomy over tagging:** category and material are objective/stored facts. Style descriptors ("minimalist," "linear") are judgment calls — handled live, at query time, by matching against the filtered candidates, never baked into the stored record as a permanent tag.

**Match on form/material, not literal listed attributes:** small makers are often willing to customize (e.g. finish a chair in a color not shown) in ways their listing never states. Search should surface these as open possibilities ("shown in oak — many makers finish to order"), not silently exclude them the way a strict attribute filter would.

**Zero customization burden on brands, ever:** the value delivered to them is traffic, full stop — not data structure, not compliance, not adoption of any standard. This was an explicit correction from an earlier assumption that brands would need to be asked to standardize anything.

## Interface principles

- **Single "ask" box, no visible filters** — works identically whether a human types a messy sentence or an AI agent sends a structured request, because both route through one LLM-based query-translation step before hitting the taxonomy/matching engine underneath. Two surfaces (chat UI for humans, structured JSON endpoint for agents), one engine.
- **Category browse chips** (e.g. Chairs, Lighting, Ceramics, Tables + "All categories") sit alongside the ask box for people who want to browse rather than search precisely — deliberately different from "example brand" chips, which would have implied favoritism.
- **No large hero imagery or editorial photography** — a genuine design tension worth remembering: image-heavy layouts are an implicit taste/curation signal design sites usually can't avoid; a plain, text-and-icon interface reads as neutral utility instead. A single plain descriptor line ("Furniture, lighting, and objects from independent makers") does the "what is this" job imagery would otherwise do, without the curatorial implication.
- **Equally-relevant results are shown in randomized order within relevance tiers** (not fully random) — preserves real match-quality signal while making rank-buying structurally impossible to suspect, since order visibly isn't stable.
- **Thin/brand-only entries get a dashed border** rather than a lesser visual treatment — same size and prominence as fully-catalogued entries, just a subtle "different kind of entry" cue.
- **Discontinued product handling:** every entry stores both a product URL and a brand homepage URL; re-crawl checks link liveness periodically (not per-search) and falls back to the brand homepage automatically if a product page is truly gone (404), but keeps the product link if the page still exists (e.g. shows "sold out").

## Monetization shape (Phase 2 must be commercially viable on its own before Phase 3 is even considered)

- Discovery itself stays free, always, for everyone.
- Brands get a periodic analytics summary sent directly (no dashboard, no login) — how many people found them, via what kind of query. This doubles as the first contact with any brand, since the scrape model means brands never opt in — the summary itself is the outreach, leading with proof rather than a cold pitch.
- A second, later tier — an aggregate "market overview" (trends across a category) — offered only to brands who've already engaged with tier one, and only once there's enough brand density per category that aggregation is genuinely anonymizing rather than just obscuring 2-3 brands' numbers.
- Opt-out/removal instructions travel in the same message as the value delivery, from day one.
- **Explicitly ruled out:** pay-to-rank/pay-to-appear (breaks the core trust proposition), affiliate/conversion fees (would require brand cooperation and tracking, breaking the zero-burden principle).

## Current status

- 22 of 24 brands from an initial test list confirmed to have real, scrapable websites (2 unconfirmed at the time: "20by8" and "In Common With" — worth re-checking spelling). *(Note: as of the latest triage pass, 23 of 24 are now confirmed — H. Bigeleisen and In Common With were resolved, Bennet Schlesinger confirmed but robots.txt-blocked, only 20by8 remains dropped. See Brand List Triage doc for the current version.)*
- Live sample extraction already proven against 2 of those 22 (Kieran Kinsella, Sizar Alexis) — real structured product data (names, materials, dimensions) pulled directly from their own sites, included in the project files.
- Landing page copy drafted; UI mockups built for both the results state and the first-visit/empty state.

## Files already in this project

- Phase 1 Plan (build steps + interface decisions)
- Brand List Triage (all 24 brands, confirmed sites, notes)
- Sample extracted product data (JSON, real data)
- Formground Landing Page Copy (draft)
- Smaller Brands Discovery Decision Summary (earlier-stage strategic summary, written before "Formground" was named — some framing is superseded by the above)
