# Formground SEO strategy (DRAFT, 2026-10-17)

Private working document. Written because Search Console says little when a site has almost no traffic (about 18 Google visits in 14 days on 15 Oct), and because requesting indexing by hand is only a nudge: 10 a day, one page at a time. This is the plan that indexing belongs inside.

## 1. Where we really are
- About 750 addresses in the sitemap: 67 Work pages, 31 Edits, 20 Guides, about 240 brand pages (with continuation pages), about 340 designer pages (with continuation pages), 45 architect pages.
- Indexed on 15 Oct: 866 pages (803 on 12 Oct). A crawl queue, not a defect: new sites are crawled slowly, and about 290 addresses arrived at once on 5 Oct.
- Strengths already in place: clean static pages, fast, canonical addresses, breadcrumbs and item lists as structured data, a sitemap with real dates, an `llms.txt` and an agent endpoint, editorial pages (Edits, Guides, profile texts) that are not copied from anywhere.
- The honest limit: almost every product page lives on someone else's site, so what we own is the arrangement, the words and the images' context. Our job is to be the best page for "a design-led way to find X", not to out-rank the maker for its own name.

## 2. Goal (12 months)
Be found for **discovery searches** (what someone types when they do not yet know the brand): "round oak coffee table", "Scandinavian pendant lamp", "rugs by artists", "modern houses in Sweden", "chairs by Børge Mogensen". Success is not rank for brand names; it is people and AI assistants landing on a Formground page and clicking through to a maker.

## 3. Which page does which job
| Page type | Search job | What it needs to be worth indexing |
|---|---|---|
| Type pages (Work: rugs, stools, sofas ...) | Head and mid terms with buying or browsing intent | A short real intro (the About blocks), a clear title with the count and the angle, the best 60 pieces first, links to related types and Edits |
| Edits and Guides | Long-tail and "best of" terms, the pages other sites link to | Distinct point of view, real picks with reasons, updated dates |
| Brand pages | Navigational and long-tail for small makers (little competition); little chance against a well-known brand's own site | A real profile text and facts, not just a grid |
| Designer pages | "[designer] chairs / lamps" and "who designed X" | Own-site link, a profile text, the pieces and makers, Further work where it exists |
| Architect and house pages | Image and inspiration searches (Google Images, Pinterest), "architect-designed houses in [place]" | Good photos with real captions, the location and the architect |
| Home, Work hub, category hubs | Authority hubs: they pass attention down to everything else | Strong internal links to the types and Edits that matter most |

## 4. The rules we work by
1. **Fewer, better pages beat more pages.** A page without its own words or a clear purpose does not get indexed and can pull a neighbour down. New page types need a profile text or intro before they are requested.
2. **Titles and descriptions say what is distinct** (count, makers, the angle), not a template that fits every page.
3. **Internal links are the real indexing request.** Every new page is linked from a hub, a related type and an Edit or Guide the same day, so it is found by crawling, not only by the sitemap.
4. **Dates are true.** The sitemap's last-changed date moves only when a page really changes (already done); a pushed batch that changes many pages is requested in priority order, not all at once.
5. **No payment to rank** (existing rule): optimisation never touches the order of results.
6. **Respect the makers**: no machine-readable promises we cannot keep, no use of their text beyond facts and short quotes.

## 5. The indexing system (what "indexing" means here)
1. **Sitemap** is the base: kept accurate, resubmitted when a big batch lands.
2. **Manual requests (Google, 10 a day)** are spent in this order: (a) type pages and hubs that changed most, (b) Edits and Guides, (c) profile-text brand and designer pages of small makers, (d) well-known brand pages last. Done criteria: 90% of type pages, Edits and Guides indexed before spending requests on brand pages.
3. **IndexNow** (free, instant, no daily limit) for Bing, Yandex and others: to build, a few lines in the deploy step that pings the addresses changed in each push. Bing Webmaster Tools gives a second, more generous view of what is indexed.
4. **Internal linking** (rule 3) and **fresh content** (a scheduled Edit every few days gives a regular crawl reason).
5. **Weekly check**: indexed count (Search Console Pages report), plus `insights_report.py` for visits by landing page. Targets are on the number of pages indexed and the pages that get a first visit, not on clicks, until there is traffic to measure.

## 6. Measuring with almost no traffic
- Indexed pages per page type (a weekly number in one table).
- First-visit pages: which pages got any visit from Google, Bing or an AI assistant (our own events, `landing_page` and source).
- Crawl activity from the server side (Cloudflare analytics: how often Googlebot and Bingbot fetch which paths).
- Query tests by hand every month: 30 target phrases, whether we appear in the first three pages. A short list kept in this file.

## 7. Work plan
Now to end of October
- Request the revised Day 7 and Day 8 lists (type pages first).
- Build IndexNow in the deploy.
- Write unique titles and descriptions for the 20 biggest type pages (count and angle).
- Link every new maker and designer from a hub and a related type.
- 26 Oct: check indexed counts and the insights report against the 15 Oct baseline.

November
- A Guide or Edit for each of the 10 most searched types that does not have one (what to look for, makers worth knowing, real picks).
- Profile texts for the top 60 designers and every maker with 40 or more pieces.
- Decide whether continuation pages (page 2 and up) stay indexable or point their canonical to page 1.
- Organic Pinterest: boards from Edits and houses, linking to the page (images are the strongest unpaid route for design).

December onward
- Outreach with something worth linking to: the Guides and the balance report (for example "who really makes plates": data journalism), sent to design writers, not to makers.
- Wikidata and a plain "about" description so assistants can describe Formground correctly.
- Review the whole plan in January with real data.

## 8. Decisions (17 Oct)
1. **Focus:** the audience is dispersed, so no country focus. If one creator type leads, it is **makers**; if one product area leads, it is **lighting**. So: lighting editorial first, and every maker page made a real page (profile text) before any other page type.
2. **Continuation pages** (open): 409 brand and 333 Work continuation pages exist (page 2 and up). They are not in the sitemap, are self-canonical and indexable. Proposal: mark them `noindex, follow`, so the crawl and the index go to the first pages; the links on them still work.
3. **Editorial over catalogue:** more Guides and Edits, lighting first (missing Guides: wall lamps, ceiling lamps, chandeliers; then purpose-led lighting Guides), and profile texts for the remaining makers (89 of 269 brands have none).
4. **IndexNow and Bing Webmaster Tools:** reasoning written up in the conversation; pending go-ahead.
