# Formground — Strategy Source of Truth

*Last updated: 2026-09-27. This file is the canonical reference for Formground's structure and decisions. Replace the copy in the project repo with this version whenever it's regenerated — don't merge by hand.*

## What Formground is

Formground is the umbrella brand and single site, built on a shared scrape/extract/card engine (working name **Coreframe**). Live nav: **Work** (search/browse everything), **Creators** (Architects, Designers, Makers), **Marketplace** (paid, clearly-labeled featured listings), **For Creators** (curated resources + supplier/service directory).

**Brandvue** (working name) is fully separate: a B2B card/directory service sold to associations, sharing only the Coreframe engine.

## Site architecture

- **Formground** = end buyers (consumers, and Creators shopping for their own client work) buying from Creators (Architects, Designers, Makers)
- **For Creators** = a sub-brand where Creators become the buyers, purchasing products/services from the wider supply chain (Craftspeople, materials suppliers, tools/services) — same buyer/seller pattern one level down
- "Creators" is the umbrella term for Architects + Designers + Makers together
- Craftspeople (in progress) will live under For Creators as a supply-side adaptation of the Marketplace mechanic. Free/paid split: small/independent craftspeople free (same logic as Makers); established, larger production companies serving bigger practices are the monetizable tier
- "Designers" shown as "Coming soon" on the live Creators page

## Categories & core principles

| Category | Access | Notes |
|---|---|---|
| Makers | Free, always | Core mission — no visibility cost |
| Craftspeople (small/independent) | Free, always | Same logic as Makers |
| Craftspeople (established) | Monetizable | Vetted B2B supplier network for architecture practices |
| Architects & Designers | Free base + optional paid enhancement | Higher lead-gen value justifies a paid tier |

- A dedicated, additive page for new/independent makers is planned, modeled on trade exhibitions. Triage combines: Coreframe-scraped company age, external classification (exhibitions/associations), the maker's own self-description, and manual override. Not yet live — confirm status with Code.
- Drops/Marketplace principle: links out only to a maker's own site/e-commerce infrastructure, never Instagram.
- Search architecture (current thinking): per-category search boxes as primary; a unified box uses classify-then-dispatch with a clarifying question and result-page tabs as safety nets.

## For Creators page (live)

Organized by named trade (For Makers, For Architects, For Designers) plus a Shared section. Editorial principle: stay impartial and honest, including platforms' downsides (live: honest Etsy note, 1stDibs/Pamono fit-note). Includes a hedged EU Digital Product Passport section, SEO basics, and "being found by AI search & agentic tools."

**Affiliate-viable links identified but NOT YET LIVE:** Shopify, Squarespace, Klaviyo, Ankorstore, Faire. Etsy and Big Cartel/WooCommerce are honest, non-affiliate informational entries.

## About page (live)

States the core philosophy: no accounts, no rankings, zero burden on creators to be found, works the same for a human or an AI assistant searching.

---

## MONETIZATION

### Boundaries (firm, not just starting scope)

- **Core search/results stay pay-to-rank-free, always.** Work and Creators browse/search results are neutral, ranked only by relevance — never by payment. This applies to the search function itself, independent of anything built below.
- **Paid promotion/placement is confined to Marketplace and For Creators only.** It does not spread to any other part of the site.

### Organizing principle

Monetization splits by audience, matching the site's own architecture:
- **Marketplace** = product/point-of-sale monetization (consumer-facing side)
- **For Creators** = professional/B2B monetization (professional-facing side)

### 1. Marketplace — Retailers/Stockists (new)

Larger makers often sell through retailers rather than direct. Plan: identify retailers via stockist lists already published on makers' sites (typically clean, scrapable pages), give each retailer its own card under a dedicated **Retailer/Stockist tab** within Marketplace (not dual-placed under For Creators yet, though retailers conceptually straddle both sides — makers seek retailers to stock them, buyers seek retailers to purchase from — dual-placement may come later once there's usage data).

Monetization principle: link directly to a retailer's specific product page where possible, minimizing clicks to purchase, to support future affiliate-commission potential.

### 2. Marketplace — Promotions tab (freemium)

Considering scraping retailers' own promotions (sales, live offers) into a Promotions tab:
- **Free tier**: a few basic scraped promotions — also serves as a traffic-proof data point when pitching the paid tier
- **Paid tiers**, along three dimensions: **richer** (more images/detail), **priority** (better placement), or **both combined** as a top tier — mirrors Architonic's Gold/Silver membership logic

Open question: a retailer may be more comfortable with free, attributed scraping than a paid product built on their content without agreement — the paid tier likely needs actual retailer consent (Brandvue-style), while the free tier can remain simple attributed scraping (transparent, link-back, remove-on-request).

### 3. For Creators — B2B tiers

- Craftspeople (established tier), Architects & Designers paid enhancement — as above
- Affiliate links (Shopify, Squarespace, Klaviyo, Ankorstore, Faire) — need to be actually submitted/activated, not just identified
- **New (5th) lever**: tool/service providers already listed could pay for **premium/featured placement** in the list, independent of and stackable with affiliate commission (standard B2B media/sponsorship economics, the Architonic pattern) — subject to the same sponsorship-labeling discipline below

### 4. Insights (new, distinct fourth category)

Aggregate market/demand data — not a single Creator's own stats (that's a bundled tier feature), but cross-platform intelligence only Formground can see: trends by product type/color/material/season; search term trends; geographic demand patterns (including mismatches between where demand originates and where makers are based); established vs. unestablished maker performance (a byproduct of the new-makers triage system, unique to Formground).

**Benchmark: WGSN** (trend forecasting, sold for £700M in 2024, 6,500+ clients, includes WGSN Interiors) confirms this is a large, real, standalone monetizable category. Formground's structural advantage: WGSN's data comes from analyst inference; Formground's would come from actual revealed buyer behavior (real search/click data) — harder to fake, once real volume exists.

**Architecture**: one underlying data engine, tiered *access* as the variable — not two separate products. A slice bundled into paid Marketplace/For Creators tiers now; a standalone paid product (WGSN-style) remains an option later once volume justifies it.

### Shared sponsorship/placement primitive

Decided that paid/sponsored placement labeling ("Sponsored"/"Partner" tag — simple, transparent, easy to opt into, honest) should be built **once, as a shared Coreframe/Brandvue-level primitive**, not duplicated per surface. The same mechanism a Brandvue client (e.g. an association) could offer its own members for paid featured placement within their directory — extending Brandvue's value proposition at no extra build cost.

### Pricing sketch (internal reference, not published)

| Item | Suggested starting price |
|---|---|
| Promotions — Richer | ~200-400 kr/promotion or /month |
| Promotions — Priority | ~300-500 kr/promotion or /month |
| Promotions — Richer + Priority | ~500-800 kr/promotion or /month |
| Craftspeople (established) | ~300-600 kr/month |
| Architects & Designers enhancement | ~200-400 kr/month |
| For Creators premium tool placement | ~500-1,500 kr/month |
| Retailer/affiliate commission | Not set by us — depends on each retailer's own program (typically 3-10% for home/design goods) |

Start low across all tiers; raise once real traffic/case-study evidence accumulates (via the free Promotions tier's traffic-proof mechanism). Resist pricing high before proof of value.

### Competitive landscape (checked)

- **Trouva** (UK, took commission/held transactions, sold 5 times in ~3 years, repeatedly failed to pay retailers, paused trading Jan 2025) — cautionary case validating "no transactions, no commission."
- **The Oblist, Frank Bros, Adorno, Alcova, Obakki, Kalinko, Abask, Artemest** (largest: €15M raised, 60,000+ products, 1,300+ artisans) — all curated/selective, transactional (commission), higher-end. A competitor's own blog post ("Beyond Artemest," by The Oblist) explicitly calls for broader-geography, genuine small-maker discovery beyond what exists — independent validation of Formground's gap.
- **Atelier100** (London, funded by Ingka Group/IKEA and H&M) — not a competitor, a designer incubator; a strong sourcing target.
- **Architonic** — B2B media model, no transactions: Gold/Silver membership tiers, virtual showrooms, sponsored content/newsletters/trade-fair marketing, 1,500+ partners. **Closest structural cousin** to Formground's planned model; strongest proof that pure visibility/advertising works at scale in an adjacent industry.
- **Pamono** (curated, commission-based, opaque fees "varying by cooperation type," recently absorbed into Chairish) and **Faire** (commission + separate retailer-referral program) — both reinforce, by contrast, the value of no-commission/no-transaction design.

**Net conclusion**: Formground's "comprehensive, non-gated, non-transactional, zero-burden" position is a repeated gap across every competitor reviewed — held as a hypothesis to test with real traffic, not a settled conclusion. The gap "may not need filling" — this is something to find out empirically.

### Investor-lens review (self-assessment, not seeking external investment)

**Key risks identified:**
- No defensible moat beyond first-mover diligence — Coreframe's mechanic is replicable
- All monetization currently unproven — zero live revenue as of this review
- "Comprehensive, non-gated" positioning may cap pricing power vs. curated competitors who charge more precisely because of scarcity
- Nearly every revenue lever (Insights, cross-platform ads, Architects/Designers paid tier) depends on traffic that doesn't yet exist
- Solo-founder capacity spread across Formground, Brandvue, Bearings, and Stafetten — real key-person/focus risk

**Conclusion**: rather than relying solely on organic/SEO growth, plans a deliberate, bounded, time-boxed **paid-traffic experiment** — a small, defined budget, success metric decided in advance, aimed at the least-proven part of the model (Marketplace/Promotions). Framed explicitly as a go/no-go decision gate on continued time investment, not open-ended marketing spend.

### Go-to-market sequencing (decided)

1. **Ship the paid mechanisms first** (Marketplace Promotions tiers, Retailer/Stockist tab, activate affiliate programs, working sign-up/payment flow) — before any external push, so generated interest can actually convert
2. **Direct maker outreach for organic sharing — rejected.** Small brands would share for free but aren't valuable revenue sources yet. Large, valuable brands have no incentive to promote until value is proven, and contacting them risks prompting takedown requests for already-scraped listings — a real downside (weakening the catalog) that outweighs the weak signal gained.
3. **Paid traffic experiment**, once #1 ships — generates real click-through data (revealed preference) rather than solicited favors. Budget, time-box, and success metric to be defined as a separate, bounded exercise.

---

## Paid-traffic experiment — prep status (2026-09-28, from Code)

Pre-flight testing of the ad plan's exact search phrases surfaced and fixed real blockers before any spend:

- Fixed: multi-word furniture queries ("Scandinavian furniture design," "furniture makers") were returning the whole unfiltered catalog instead of real matches.
- Fixed: "new"/"new arrivals" now filters correctly instead of falling through to junk text-matching.
- Fixed: a scrape artifact had wrongly flagged 71% of the catalog as "new" — corrected to a believable 854 new items.
- Shipped (local build, not yet live): homepage "New" section plus themed groupings, each linking to a real working search query — Chairs (23), Vases (23), Lamps (14), and long-tail category+material/shape combos chosen because they're already fully supported today with real brand-diverse inventory (e.g. Floor Lamps: 40 brands/219 items; Round Dining Tables: 10 brands/29 items).
- Standing principle agreed this session: **advertising should drive content, not just the reverse** — a keyword worth advertising but with thin catalog behind it is now a scraping/onboarding priority, not a reason to pick a different keyword.

**Catalog-validated keyword candidates** (inventory confirmed by Code; search-volume/CPC/competition research is this chat's job, not yet done for these specific terms):
- Google-style: "wood sofa," "round dining table," "wood dining table," "wood side table," "round coffee table," "floor lamp," "independent furniture makers."
- Pinterest-style: same inventory, framed as "[X] ideas" / numbered-list content.

**Known gap relevant to campaign targeting**: the plan's stated geography (Sweden/Scandinavia) can't be used as a search filter yet — `location` filtering exists only for house search, not wired into product search. A phrase like "Scandinavian dining table" would silently fail to filter geographically today. Flagged as a real backend priority, not started.

**Still in the pipeline (not built)**:
- Dedicated per-theme landing pages for ad clicks to land on (homepage groupings exist; a full "Wood Sofas" collection page does not yet)
- Geography/location product filtering (above)
- Hand-picked "Independent Makers" spotlight module — resolved as buildable via manual curation, not automated; waiting on which makers to feature
- The paid-traffic experiment itself (~€400/month, Pinterest+Google, 4-6 weeks) — not yet launched; pre-flight search-relevance blocker now cleared

**Next step for this chat**: once the geography-filtering gap is resolved (or a decision is made to launch without it), take the catalog-validated keyword list above and run real CPC/competition checks against it before committing budget. *(Superseded — see keyword research results below, 2026-09-28. Geography-filtering fix shipped 2026-09-28 (commit cedd0af) - "Scandinavian dining table," "Swedish chair," "Nordic lighting" now all work. Seat-count filtering also shipped the same day (commit b712dc1) - "two seater sofa" and "three seater sofa" now work: 56 and 50 real matches respectively.)*

### Keyword research results (2026-09-28, Google Keyword Planner, Sweden, 12-month)

Locked shortlist — real search volume + workable CPC, sized for ~€400/month across Google + Pinterest:

- **Lighting (strongest cluster — prioritize content here)**: floor lamp (100–1K/mo, €0.16–0.67 CPC), designer table lamp (10–100/mo, €0.31–0.63 CPC) — both confirmed. Small test budget on minimalist table lamp and contemporary lighting — both show genuine emerging (+∞) trend, no bid data yet.
- **Tables**: round dining table (100–1K/mo, €0.18–0.69), round coffee table (10–100/mo, +900% trend, €0.21–0.69), scandinavian dining table — bare, no "new" qualifier (10–100/mo; real volume once the qualifier was dropped — landing copy needs to do the new-vs-vintage disambiguation, not the keyword)
- **Seating**: two seater sofa (10–100/mo, €0.16–0.92)
- **Ceramics**: modern vase (10–100/mo — matches confirmed 23-item vase catalog), contemporary ceramics (10–100/mo, **Low** competition — cheapest opportunity tested)
- **General**: contemporary furniture (10–100/mo)

Second-wave / retest candidates (real volume, incomplete bid data): contemporary coffee table, contemporary sideboard (catalog depth unchecked), globe table lamp, modern pendant lighting, wood sofa, wood side table, sustainable furniture, limited edition furniture.

**Firmly ruled out**: designer sofa (-90% trend, highest CPC tested at €0.60–0.96), unique furniture (high CPC, high competition for the volume), collectible furniture (-100% trend), contemporary vase / contemporary ceramic vase (-100% trend — "contemporary + material/vase" combos collapsed), contemporary candleholders (near-zero volume), felt sofa (-100% trend), independent furniture makers / furniture by independent makers (near-zero volume), "new scandinavian dining table" (zero data as a compound phrase), and brand/aspirational phrases (alternative to architonic, pinterest for furniture, where to discover modern furniture, lighting and objects) — all zero search volume.

**Key insight**: long-tail specificity is paying off — floor lamp and round dining table run 3–4x cheaper than the $3.97 industry-average "furniture" CPC. Lighting has the strongest combined signal (deepest confirmed catalog at 40 brands/219 items, plus two terms showing genuine emerging trend) and should get the next content/landing-page priority.

**Next step**: map each locked keyword to a landing page. Lighting needs the most new page-building — only floor lamp is currently in Code's confirmed homepage groupings; designer table lamp, minimalist table lamp, globe table lamp, and modern pendant lighting have no dedicated page yet.

---

## Engine

Working name "Coreframe" for the shared scrape/extract/card engine powering Formground and Brandvue.

---

*Open items not yet decided: final paid-traffic budget/metric/channel; whether Insights ever becomes a standalone product; whether retailers get dual-placement in For Creators; paid-enhancement tier design specifics for Architects & Designers; geography/location filtering for product search (blocks Scandinavia-specific ad phrasing); real CPC/competition research on the catalog-validated keyword list; which makers to feature in the Independent Makers spotlight.*
