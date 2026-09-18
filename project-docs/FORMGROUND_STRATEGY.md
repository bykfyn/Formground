# Formground — Strategy Source of Truth

*Last updated: 2026-09-18. This file is the canonical reference for Formground's structure and decisions. Replace the copy in the project repo with this version whenever it's regenerated — don't merge by hand.*

## What Formground is

Formground is the umbrella brand and single site, built on a shared scrape/extract/card engine (working name **Coreframe**). It has two parallel sections:

- **Products** — existing maker/product discovery (furniture, lighting, ceramics, objects)
- **Professionals & Services** — architects, interior architects, landscape architects, and production/fabrication partners (working name "Archframe" was considered as a separate product — decided against; this is a Formground section, not a separate brand)

**Brandvue** (working name) is fully separate: a B2B card/directory service sold to associations (e.g. Snickarmästarna, Interior Cluster), sharing only the Coreframe engine underneath — different brand, different domain, different customer.

## Why one site, two sections

Architects and interior designers are already a real audience on Formground's Products side (browsing for client projects). The cross-audience value — e.g. established production companies wanting visibility to architects — already exists within Formground's own traffic. No need to build a separate site's audience from scratch.

Products and Professionals & Services are kept as **separate, parallel search experiences** (not one blended search) since search intent and taxonomy genuinely differ, and separation creates clearer, independently sellable monetization inventory for each.

## Professionals & Services — scope and sourcing

- Comprehensive and non-gated by design (unlike Sveriges Arkitekter's members-only directory)
- International from the start, since architects work across borders
- Sourcing: Sweden's SNI code 71110 (~2,912 companies) via allabolag.se/näringslivsregistret.se as a base list, cross-referenced against Sveriges Arkitekter's members
- Onboarding sequence: largest to smallest by **revenue**, not employee count (many are solo practices where the principal isn't formally employed by their own company)
- Category rollout: architects + interior architects first, landscape architects later (weakest tie-in to the Products catalog)

## Categories & monetization

| Category | Access | Notes |
|---|---|---|
| Makers | Free, always | Core mission — no visibility cost |
| Craftspeople (small/independent) | Free, always | Same logic as Makers — e.g. many Snickarmästarna members have no website at all |
| Craftspeople (established, serving larger architecture practices) | Plausibly monetizable | Distinct category — closer to a vetted B2B supplier network |
| Architects & Designers | Free base listing | Optional paid enhancement tier considered separately — higher lead-gen value of hiring a professional vs. buying an object |

**Cross-platform advertising** (once there's traffic): makers advertising to architects/interior designers, professionals advertising to Formground's product-buying audience. Clearly labeled, sold simply (per-listing/per-period) — not a bidding system.

## New/independent makers page

A dedicated, **additive** (not exclusionary) page for new/independent makers, modeled on how trade exhibitions separate emerging designers from established brands. Makers featured here still appear in general search. Has its own scoped search box.

**Triage — four signals, combined:**
1. Coreframe-scraped company age where available
2. External classification from exhibitions/associations that already categorize this way (e.g. Stockholm Craft Week, Konsthantverkscentrum)
3. The maker's own site self-description (e.g. "founded in 2023")
4. Manual override for edge cases

This triage logic likely needs to generalize as a reusable mechanism across multiple categories (e.g. the established/small split within Craftspeople), not just Makers.

## Drops page (planned)

Limited-run/time-limited products. Richer detail (price, sale date, "limited run" flag). Paid placement, clearly labeled.

**Hard rule: links out only to a maker's own site/e-commerce infrastructure (Shopify, WooCommerce, etc.) — never Instagram**, even though some makers sell exclusively there. Reasoning:
- Technical: Shopify/WooCommerce expose structured, scrapable data; Instagram doesn't
- Commercial: a real checkout path already exists to link to
- Strategic: positions Formground, not Instagram, as the destination worth being found on

## Homepage & search

Category-first, not search-first: named entry points (**Makers**, **Architects & Designers**, **Joiners & Craftspeople**) presented above the fold, unified search box below as a secondary path ("search everything at once"). Header kept minimal — wordmark plus small Resources/About links; no traditional nav bar, since category cards carry primary navigation.

**Search architecture (current thinking, not finalized):**
- Per-category search boxes are the primary, lower-risk build (extends existing proven search)
- Homepage's unified box: classify-then-dispatch — one call to pick domain, then hand off to that domain's existing extraction pipeline (not one monolithic prompt)
- Two safety nets: a clarifying question for low-confidence/ambiguous queries, and result-page tabs (Products / Architects & Designers / Joiners) so a misroute costs one click, not a dead end

## Resources page

Single shared page for all groups, organized by **named trade** (Makers, Architects & Designers, Joiners & Craftspeople) plus a "Shared" section for cross-cutting topics (SEO, hosting, agentic-search readiness) — not generic labels like "For Makers"/"For Professionals," since people identify with their actual trade.

**Editorial principle:** stay impartial and honest about the landscape, including platforms' downsides, while recommending what's genuinely in makers' interest. This is core to Formground's success, not a content nicety.

- Add a fit-note to 1stDibs/Pamono (vetted, application-based, better for established makers) rather than removing them
- Reflect Etsy's real downsides honestly (rising fees/ads, AI-generated listing competition, algorithm volatility, account-suspension risk) rather than presenting it neutrally
- Gaps to add: SEO basics, hosting, agentic/AI-search readiness

**Affiliate programs — confirmed fits** (reward referring the right party): Shopify, Squarespace, Klaviyo, Ankorstore
**Poor fits:** Etsy and Faire (pay for referring shoppers/retailers, not sellers); Big Cartel and WooCommerce have no program

Long-term: this page may evolve into its own searchable directory (materials/suppliers, production-partners) once content/traffic justify it.

## Standing product principles (apply across Formground, Brandvue, and any future product)

1. **Future-proof selectively**, not universally — design to allow pivots where the cost is low and lock-in risk is real; don't build for speculative trends before they're proven
2. **Build on existing infrastructure** (Shopify, payment providers, compliance tooling) rather than replicating it — keep the product focused on its actual differentiation
3. **Prioritize a validated niche** over broad ambition — assume competition exists everywhere (Houzz, Dorunner, 1stDibs, etc. all already exist); the real opportunity is in **execution quality for underserved segments** (no pay-to-rank, no review manipulation, honest presentation, serving smaller/overlooked players), not finding an empty category

---

*Open items not yet decided: whether "Archframe" survives as any kind of internal label, final search UX between per-category and unified boxes, paid-enhancement tier design for Architects & Designers.*
