# Phase 1 Plan — Personal Discovery Tool

Goal: a working personal tool that scrapes a curated list of small brand sites and lets you search — and browse — across them by category, material, and live style-matching. Framed around serendipitous discovery (like browsing a gallery or shop), not precision e-commerce search — consistent brand quality matters more than exact-match density. No accounts, no hosting of full assets, no burden on brands.

---

## Step 1 — Build the starting brand list
- Compile an initial list from your folder, kept deliberately small (15–30 brands is a good first target — enough to be useful, small enough to debug by hand).
- One row per brand: name, homepage URL, product/catalog page URL if different.

## Step 1.5 — Curation criteria + brand approval
- Brand inclusion is **curated, not purely mechanical** — you review and approve each brand before it enters scope, applying a consistent standard: small-to-medium, design-led, original work. Excludes brands primarily reselling or reproducing others' designs (including expired-copyright reproductions).
- This is a deliberate correction from a pure opt-out/scrape-everything model — without it, results would be indistinguishable from a general web search and could include knockoff/reproduction sellers, undermining the "consistently interesting" value proposition.
- **This step is the real throughput bottleneck for catalog growth**, not scraper build speed — brand-list growth is rate-limited by curation time, not engineering time. Worth sizing expectations (and Phase 1/2 scope) around that constraint rather than around how fast a scraper could technically be built.
- Not always obvious from a brand's own site whether a design is original — may need spot-checking against known designs rather than a quick fetchability check. Slower than Step 2's triage.

## Step 2 — Triage for scrapability
- For each site, check whether it's a plain fetchable site or JS-rendered (same distinction we ran into repeatedly tonight with TMF and Sheerd's own site).
- Sort into two lists: **in scope now** (fetchable) and **skip for now** (JS-rendered — revisit later, no scraper investment yet).
- This can be done directly, live, by testing each URL — I can help triage your actual list this way as a first concrete action.
- Respect robots.txt as a hard rule, consistent with the fair-use/goodwill framing — sites that disallow automated access are excluded from scraping (manual/case-by-case only, if ever), not worked around.

## Step 3 — Define a starter taxonomy
- A lean category set covering what you'd actually search for — chairs, tables, storage, lighting, textiles, decor, etc. Doesn't need to be exhaustive on day one.
- Google's Product Taxonomy is a reasonable reference point to crib from rather than inventing one from scratch, trimmed down to what's relevant.

## Step 4 — Build the scraper
- For each in-scope brand: extract product name, image URL, category/breadcrumb (if present), any stated material, link back to the product page.
- Output to a simple structured file (JSON or CSV) — no database needed at this scale.
- This is a deliverable I can write as an actual script for you to run.

## Step 5 — Build the search/matching logic
- Filter first on hard facts: taxonomy category + material.
- Style-matching ("minimalist," "linear," etc.) happens live, at query time, over the filtered candidates — not baked into the stored data.
- Given the discovery/browsing framing, a search with no exact match should still return adjacent results (e.g. chairs generally, if no walnut chair exists) rather than an empty result — breadth within a category matters more than precision matching.
- At this scale, this step can just be you asking me directly, working from the structured file — no need to build a separate matching engine yet.

## Interface decisions (locked in)
- **Single ask box, no visible filters.** Natural-language query in, results out — matches the "ask me directly" interaction model rather than faceted search chips.
- **One query-translation step in front of the matching engine.** An LLM pass turns the raw query (human or agent) into structured intent — category, material, color, style descriptors — before it touches the taxonomy filter. This is what makes "works for any user, agentic or human" actually true: both a messy human sentence and a clean structured agent request reduce to the same intermediate form before matching happens.
- **Two surfaces, one engine.** Humans get a chat-style ask box + card results. Agents get a structured JSON endpoint (schema.org Product-shaped, consistent with the UCP/ACP-style protocols) returning the same underlying matches — no separate UI to build for that surface, just a different output format on the same query engine.
- **Result cards treat all entries as equal weight**, regardless of how much structured data a brand has — a single-product or portfolio-only brand gets the same size/prominence card as a fully-catalogued one (dashed border as a subtle "different kind of entry" cue, not a lesser one).
- **Non-literal matches ("shown in oak, finishes to order") are labeled informationally, not flagged as a caveat** — no warning colors, just a small note, since flexible finishing is a genuine, common small-maker reality, not a defect in the match.
- **No accounts, no pricing chrome, no checkout affordance on cards** — every card's only action is "go to the source," consistent with the thumbnail + link-back legal model already established.

## Step 6 — Test against real queries
- Repeat the kind of test we ran tonight (the chair, the lamp) against your actual curated list, and see what comes back.
- Use this to spot gaps — brands whose sites don't parse well, categories that are missing, matches that feel wrong.

## Step 7 — Basic instrumentation, from day one
- Even informally, note what gets searched and what gets clicked through. Not urgent to formalize now, but worth the habit early, since Phase 2 will need this data to demonstrate real traffic to brands later.
- Revenue proof for brands (does traffic actually convert to sales) is planned to be handled via direct outreach/conversation with brands, not automated tracking — consistent with the zero-burden principle. This is self-reported and anecdotal rather than measured, which is an accepted tradeoff at this scale.

---

## Suggested first concrete action
Share the brand list (or a first batch of it), and we start at Step 1.5 — curating which brands actually meet the inclusion standard — since that now determines everything downstream, ahead of technical scrapability.
