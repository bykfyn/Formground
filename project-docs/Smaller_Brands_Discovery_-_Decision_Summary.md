# Aiding Smaller Brands — Discovery Concept Summary

## The core idea
A lean, opt-out (not opt-in) product discovery layer for small/independent design brands — built by scraping brand sites directly, not by asking brands to submit or maintain anything.

## How it works
- **Scrape brand sites** for products — thumbnail image + link back to the brand's own page. No hosting full assets, no checkout, no accounts.
- **Remove on request** — any brand can ask to be taken down; no permission needed to be included in the first place.
- **Match on form + material, not literal listed attributes.** A red chair search should surface a maker who finishes to order in red, even if red isn't listed — small brands are flexible on execution in ways their listings don't show. Treat unlisted variants as a live question ("shown in oak — many makers finish to order"), not a filter to exclude on.
- **Structure by taxonomy (category, material, objective facts), not by style tags.** Taxonomy is factual and tractable; "minimalist," "linear," etc. are judgment calls. Handle style-matching live, at query time, rather than baking subjective tags into the record.
- **Zero burden on brands.** No customization, no data submission, no adoption of any standard required. The entire value to them is traffic they can see in their own analytics — nothing else needs to be understood or maintained on their end.

## Build sequence
1. **Phase 1 — scraped discovery layer.** Personal tool to prove the concept, generate real referral traffic to real small brands. Not the end goal.
2. **Phase 2 — commercially viable on its own terms.** Not just "prove traffic exists" — Phase 2 needs a working revenue mechanism in its own right, standing independently of whether Phase 3 ever happens. **Not yet decided how** — needs to be worked through against the existing monetization principles (freemium core, no pay-to-rank, survival-not-maximization).
3. **Phase 3 — structured/protocol help (UCP/ACP-style data for agentic commerce) — only considered once Phase 2 is commercially viable**, not before. Deliberately deferred, not a near-term goal.

Current scope: Phase 1 and 2 are sufficient for now. Phase 3 is explicitly out of scope until Phase 2 proves itself commercially.

## Legal grounding
- Thumbnail + link-back to source is a well-precedented fair-use pattern (same basis Google Images operates on) — full-size rehosting would not carry the same protection.
- Remove-on-request reduces friction and goodwill risk; it doesn't eliminate underlying exposure, but it's a reasonable, precedented position.

## Decided
- **Scale & site quality**: build slowly. Filter out JS-rendered/hard-to-scrape sites in the first instance rather than solving for them upfront. Reach out directly to a brand only if inclusion is deemed worth the manual effort — not a default step.
- **Phase 1 purpose**: a personal tool to test the concept, not the end goal.
- **Scope for now**: Phase 1 and 2 only. Phase 3 is deferred until Phase 2 is commercially viable on its own.

## What's still genuinely open
- **Taxonomy normalization work** — different brands categorize inconsistently; mapping many sites' own structures onto one shared taxonomy is real, ongoing work, even though it's more tractable than style-tagging.
- **How Phase 2 actually becomes commercially viable** — the central open question now. Needs to be worked through against the existing monetization principles (freemium core, no pay-to-rank, survival-not-profit-maximization), once Phase 1 has real results to test ideas against.
- **Target scale for the first real test** — how many brands, roughly, for a first working version.
- Whether Phase 2 stays purely your own tool/workflow, or is meant to become something with its own front end once it proves out.
