# Formground — Infrastructure Requirements

Organized by layer, with what's needed now (lean, Phase 1/2 scale) versus what only becomes necessary later. Nothing here requires heavy capital — this is a data/software stack, not physical infrastructure.

---

## 1. Data pipeline (scraping + extraction)
**What it does:** periodically fetches each brand's site, extracts product/brand-level data, tags it against the taxonomy.

- A scraper script (Python is the natural choice — requests/httpx + BeautifulSoup for static sites; a headless browser like Playwright only for the JS-rendered sites currently being deferred).
- Runs on a schedule (weekly or monthly re-crawl is plenty at this scale) — not continuous, not real-time.
- Same job also re-checks stored product URLs for the link-health/fallback logic already decided (does the page still resolve, does it still look like the product).

**Phase 1 scale:** this can run as a script on your own machine, triggered manually or via a simple scheduled task. No server needed yet.

## 2. Data storage
**What it does:** holds the structured records (brand, product, category, material, dimensions, URLs, thumbnail references).

- At 22–50 brands: a JSON file or a lightweight SQLite database is genuinely sufficient — no need for a hosted database service yet.
- Images: **never stored in full** — only thumbnail-sized copies or, better, just the source URL referenced live, consistent with the thumbnail+link-back legal model.
- This only needs to become a "real" hosted database once brand count and query volume grow past what a single file can comfortably serve.

## 3. Query/matching engine
**What it does:** the LLM query-translation step (raw query → structured intent) plus the taxonomy filter and live style-matching, already designed.

- This is API calls to an LLM (Claude via the API, straightforward to wire up) plus simple filtering logic against the stored data — not infrastructure-heavy, mostly code.
- Cost scales with query volume, which is naturally low at this stage.

## 4. Serving layer — two surfaces, one engine
- **Human surface:** the ask-box web interface. Needs basic web hosting — a lightweight framework is enough (no need for anything elaborate at this scale).
- **Agent surface:** a structured JSON endpoint returning schema.org Product-shaped results. Technically just another route on the same small backend — not a separate system.

**Phase 1 scale:** both can run from a single small, cheap hosting instance (or even serverless functions, which cost close to nothing at low traffic).

## 5. Analytics & instrumentation
**What it does:** tracks real visits and click-throughs, which is what makes the brand analytics summaries (the Phase 2 monetization mechanism) possible at all.

- GA4 with Enhanced Measurement, exactly as already scoped for Sheerd — same setup, same principle (needs-based, aggregate, not invasive).
- This needs to be live *before* the first analytics summary is ever sent, since there's nothing to report without it.

## 6. Outreach / report delivery
**What it does:** sends the periodic per-brand analytics summaries — the mechanism now doing double duty as both monetization and first contact.

- At small scale: this can be manual or semi-manual (a templated email, personally sent) — genuinely fine while the brand count is small enough to do by hand.
- Only needs real email infrastructure (a transactional email service) once volume makes manual sending impractical.

## 7. Removal / opt-out handling
- Doesn't need infrastructure beyond a simple intake (an email address or short form) and a process to actually remove a brand's data from the pipeline on request. Worth having this working from day one, even if handled manually at first.

---

## What's genuinely not needed yet
- No accounts/auth system (no user accounts for either brands or searchers).
- No payment processing (nothing being sold directly through the tool itself yet).
- No CDN or image hosting (thumbnails/links only).
- No dedicated database server (a file or SQLite is enough at this scale).

## Rough sequencing
Data pipeline and storage first (this is most of Phase 1, already underway). Query engine and human-facing search next. Analytics instrumentation *before* any outreach begins, since the first analytics summary needs real data behind it. Agent-facing endpoint can come after the human surface is working, since it's incremental on the same backend rather than a separate build.
