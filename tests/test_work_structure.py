"""
Guards for the 2026-10-04 URL restructure: type pages under /work/, Edits under
/edits/, every old address a redirect stub, one taxonomy feeding the menu.

    python3 -m unittest discover tests
"""

import glob
import os
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "backend"))

EDIT_SLUGS = ["two-seater-sofas", "round-dining-tables", "round-coffee-tables", "scandinavian-dining-tables",
              "pendant-lamps", "table-lamps", "wall-lamps", "ceiling-lamps", "portable-lamps"]
OLD_HREF = re.compile(r"^/(browse/|floor-lamps\.html|new\.html|(%s)\.html)" % "|".join(EDIT_SLUGS))


def _is_stub(text):
    # also skips private review sheets (docs/_*.html, gitignored, never published)
    return ('http-equiv="refresh"' in text and "Formground has moved this page" in text) or "Edit review (not published)" in text


def _resolves(href):
    path = href.split("#")[0].split("?")[0]
    if path.endswith("/"):
        path += "index.html"
    return (DOCS / path.lstrip("/")).exists()


def _stub_target(text):
    return re.search(r'http-equiv="refresh" content="0; url=([^"]+)"', text).group(1)


class TaxonomyTests(unittest.TestCase):
    def test_every_browse_group_belongs_to_exactly_one_category(self):
        import generate_browse_pages as g
        import work_menu
        in_menu = [grp for groups in work_menu.TAXONOMY.values() for grp in groups]
        self.assertEqual(len(in_menu), len(set(in_menu)), "a group is listed under two categories")
        for c in g.BROWSE_CATEGORIES:
            self.assertIn(c["group"], in_menu, c["slug"])

    def test_type_slugs_are_unique_and_do_not_shadow_a_category_page(self):
        import generate_browse_pages as g
        import work_menu
        slugs = [c["slug"] for c in g.BROWSE_CATEGORIES]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertFalse(set(slugs) & set(work_menu.CATEGORY_SLUGS.values()))


class HouseCountryTests(unittest.TestCase):
    def test_stated_country_is_read_from_the_end_of_a_location(self):
        import generate_browse_pages as g
        self.assertEqual(g.stated_country("Aarhus, Denmark"), "Denmark")
        self.assertEqual(g.stated_country("Veddinge, Zeeland, Denmark"), "Denmark")
        self.assertEqual(g.stated_country("Cambridge (Cambridgeshire)"), None)
        self.assertEqual(g.stated_country("Devon"), None)
        self.assertEqual(g.stated_country(None), None)

    def test_a_house_is_filed_where_it_stands_not_where_its_architect_is_based(self):
        import generate_browse_pages as g
        by_name = {h["name"]: h for h in g.load_houses()}
        self.assertEqual(by_name["Casa Kiké"]["country"], "Costa Rica")       # UK practice
        self.assertEqual(by_name["House with a hidden atrium"]["country"], "Denmark")  # Swedish practice
        self.assertEqual(by_name["Velamsund"]["country"], "Sweden")           # no change
        for h in g.load_houses():
            self.assertTrue(h["country"], f"{h['name']} has no country at all")


class StructureTests(unittest.TestCase):
    def test_every_old_address_is_a_stub_pointing_at_a_real_page(self):
        old = [DOCS / f"{s}.html" for s in EDIT_SLUGS] + [DOCS / "floor-lamps.html", DOCS / "new.html"]
        old += [Path(p) for p in glob.glob(str(DOCS / "work" / "recently-added*.html"))]   # the short-lived first-seen pages
        old += [Path(p) for p in glob.glob(str(DOCS / "browse" / "*.html"))]
        old += [DOCS / f"{s}.html" for s in ("furniture", "lighting", "objects", "ceramics")]
        self.assertTrue(len(old) > 40)
        for f in old:
            text = f.read_text()
            self.assertTrue(_is_stub(text), f"{f.name} should be a redirect stub")
            self.assertTrue(_resolves(_stub_target(text)), f"{f.name} -> {_stub_target(text)} does not exist")

    def test_edits_live_under_edits_and_types_under_work(self):
        for s in EDIT_SLUGS:
            self.assertFalse(_is_stub((DOCS / "edits" / f"{s}.html").read_text()), s)
        for s in ("table-lamps", "floor-lamps", "portable-lamps", "sofas", "furniture", "lighting", "objects", "houses", "houses-sweden"):
            self.assertFalse(_is_stub((DOCS / "work" / f"{s}.html").read_text()), s)

    def test_no_live_page_links_to_an_old_address_and_no_internal_link_is_broken(self):
        old_links, broken = [], []
        for f in glob.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            if _is_stub(text):
                continue
            for href in set(re.findall(r'href="([^"]+)"', text)):
                if href.startswith(("http", "mailto:", "#", "tel:", "data:")):
                    continue
                href = href if href.startswith("/") else "/" + href
                if OLD_HREF.match(href):
                    old_links.append((os.path.relpath(f, DOCS), href))
                if not _resolves(href):
                    broken.append((os.path.relpath(f, DOCS), href))
        self.assertEqual(old_links[:5], [])
        self.assertEqual(broken[:5], [])

    def test_sitemap_lists_only_real_pages(self):
        sm = (DOCS / "sitemap.xml").read_text()
        for loc in re.findall(r"<loc>([^<]+)</loc>", sm):
            path = urlparse(loc).path
            self.assertTrue(_resolves(path), f"{loc} is in the sitemap but does not exist")
            if path.endswith(".html"):
                self.assertFalse(_is_stub((DOCS / path.lstrip("/")).read_text()), f"{loc} is a redirect stub")
        self.assertNotIn("/browse/", sm)

    def test_type_pages_look_like_the_work_page(self):
        """Every type page (Table Lamps shown here; the next test covers all) is built from the Work page's own pieces: nav with Work current, the
        search form to /work.html, the four chips, the shared stylesheet and Work-style cards."""
        text = (DOCS / "work" / "table-lamps.html").read_text()
        self.assertIn('<a href="/work.html" class="current">Work</a>', text)
        self.assertIn('action="/work.html"', text)
        self.assertEqual(text.count('<button type="button" class="work-menu-cat'), 4)
        self.assertIn('class="work-menu-cat is-current"', text)
        self.assertIn("/work-results.css?v=", text)
        self.assertIn('class="results-grid"', text)
        self.assertIn('class="share-btn"', text)
        self.assertIn("/share.js?v=", text)
        # the Work page links the same stylesheet, so the two cannot drift apart
        self.assertIn("/work-results.css?v=", (DOCS / "work.html").read_text())
        self.assertEqual((ROOT / "frontend" / "work-results.css").read_text(), (DOCS / "work-results.css").read_text())

    def test_type_pages_hold_60_cards_with_see_more_and_a_compact_pager(self):
        pages = sorted(glob.glob(str(DOCS / "work" / "table-lamps*.html")), key=lambda f: (len(f), f))
        counts = [len(re.findall(r'<a class="card"', Path(f).read_text())) for f in pages]
        self.assertTrue(len(pages) >= 10, "table lamps should be many 60-card pages")
        self.assertTrue(all(c == 60 for c in counts[:-1]), counts)
        self.assertTrue(1 <= counts[-1] <= 60)
        first = (DOCS / "work" / "table-lamps.html").read_text()
        self.assertIn('id="see-more"', first)
        self.assertIn('href="/work/table-lamps-2.html"', first)
        self.assertIn('class="gap"', first)                       # the pager elides the middle pages
        self.assertIn('rel="next"', first)
        last = Path(pages[-1]).read_text()
        self.assertNotIn('id="see-more"', last)                   # nothing left to load
        self.assertNotIn('rel="next"', last)
        # rolled out to every type (2026-10-04): no type page holds more than 60 cards, all use the template
        for f in glob.glob(str(DOCS / "work" / "*.html")):
            text = Path(f).read_text()
            if 'class="results-grid"' not in text or "/work/houses" in f or "houses" in Path(f).name:
                continue
            self.assertLessEqual(len(re.findall(r'<a class="card"', text)), 60, f)
            self.assertIn("/work-results.css?v=", text, f)
        for slug in ("sofas", "chairs", "vases", "rugs"):
            self.assertEqual(len(re.findall(r'<a class="card"', (DOCS / "work" / f"{slug}.html").read_text())), 60, slug)

    def test_new_lives_inside_each_category_like_a_type(self):
        """"New" (new from the maker) is not a chip: each category (Furniture, Lighting, Objects) lists "New" first among its types,
        in the dropdown and on its category page, linking to /work/new-<category>.html - a standard listing page.
        /work/new.html is a small hub the home page's New heading lands on; /new.html is a stub."""
        self.assertEqual(_stub_target((DOCS / "new.html").read_text()), "/work/new.html")
        menu = (DOCS / "work.html").read_text()
        self.assertNotIn("work-menu-act is-current", menu)
        self.assertEqual(menu.count('href="/work/new.html"'), 0)          # no top-level chip for it
        for cat in ("furniture", "lighting", "objects"):
            self.assertIn(f'<li><a href="/work/new-{cat}.html"', menu)
            text = (DOCS / "work" / f"new-{cat}.html").read_text()
            self.assertIn('class="results-grid"', text, cat)
            self.assertIn('class="share-btn"', text, cat)
            self.assertIn('aria-current="page"', text, cat)                # New marked in the dropdown/list
            self.assertLessEqual(len(re.findall(r'<a class="card"', text)), 60, cat)
            page = (DOCS / "work" / f"{cat}.html").read_text()
            self.assertIn(f'href="/work/new-{cat}.html"', page)            # a tile on the category page
        # no maker fills a New view: at most 10 pieces per maker in each (smaller makers are not crowded out)
        for cat in ("furniture", "lighting", "objects"):
            per_maker = {}
            for f in glob.glob(str(DOCS / "work" / f"new-{cat}*.html")):
                for brand in re.findall(r'<a class="card"[^>]*data-brand="([^"]*)"', Path(f).read_text()):
                    per_maker[brand] = per_maker.get(brand, 0) + 1
            self.assertTrue(per_maker and max(per_maker.values()) <= 10, (cat, max(per_maker.values())))
        self.assertNotIn("new-houses", menu)                               # houses carry no added-date
        hub = (DOCS / "work" / "new.html").read_text()
        self.assertEqual(hub.count('class="maker-card"'), 3)
        self.assertNotIn('class="results-grid"', hub)
        sm = (DOCS / "sitemap.xml").read_text()
        self.assertIn("/work/new.html", sm)
        self.assertIn("/work/new-furniture.html", sm)
        self.assertNotIn("formground.com/new.html", sm)

    def test_see_more_is_the_one_visible_way_on_with_javascript(self):
        """With JavaScript the numbered pager is hidden (it stays in the HTML for crawlers and no-JS visitors),
        the address follows what was loaded, and a page 2+ visitor gets an 'Earlier results' link."""
        css_and_js = (ROOT / "frontend" / "listing.js").read_text()
        self.assertIn("has-load-more", css_and_js)
        self.assertIn("replaceState", css_and_js)
        first = (DOCS / "work" / "rugs.html").read_text()
        third = (DOCS / "work" / "rugs-3.html").read_text()
        for page in (first, third):
            self.assertIn(".has-load-more .pager { display: none; }", page)
            self.assertIn('<nav class="pager"', page)                 # still there for crawlers / no JavaScript
            self.assertIn('data-start="', page)
        self.assertNotIn('<p class="earlier-results">', first)
        self.assertIn('<p class="earlier-results"><a href="/work/rugs-2.html" rel="prev">', third)
        self.assertIn('data-start="120"', third)

    def test_new_from_sits_at_the_top_of_a_maker_page_and_only_when_there_is_something(self):
        with_new = (DOCS / "brands" / "ferm-living.html").read_text()
        body = with_new[with_new.index('<main data-brand='):]
        self.assertLess(body.index("New from Ferm Living"), body.index("All of Ferm Living"))
        self.assertLess(body.index("All of Ferm Living"), body.index('<div class="grid" data-listing-grid>', body.index("All of Ferm Living")))
        without = (DOCS / "brands" / "gubi.html").read_text()
        body = without[without.index('<main data-brand='):]
        self.assertNotIn("New from Gubi", body)
        self.assertNotIn("All of Gubi", body)                  # no empty space, no extra heading, just the range

    def test_maker_pages_have_the_share_button_and_no_stockist_section(self):
        import glob as _g
        text = (DOCS / "brands" / "gubi.html").read_text()
        self.assertIn('<button class="share-btn"', text)
        self.assertIn('data-product="62 Desk" data-brand="Gubi"', text)
        self.assertIn("/share.js?v=", text)
        self.assertIn(".share-btn.copied::after", text)                 # the shared button styles are embedded
        for f in _g.glob(str(DOCS / "brands" / "*.html")):
            page = Path(f).read_text()
            self.assertNotIn('class="stockist-item"', page, f)
            self.assertNotIn('<p class="brand-section-title">Where to buy', page, f)

    def test_maker_pages_are_paged_at_60_cards_with_see_more(self):
        import glob as _g
        first = (DOCS / "brands" / "serax.html").read_text()
        grid = first[first.index('<div class="grid" data-listing-grid>'):]
        grid = grid[:grid.index('<div class="load-more-row">')]
        self.assertEqual(len(re.findall(r'<a class="card"', grid)), 60)
        self.assertIn('id="see-more"', first)
        self.assertIn('href="/brands/serax-2.html"', first)
        self.assertIn('<nav class="pager"', first)                      # kept in the HTML for crawlers
        second = (DOCS / "brands" / "serax-2.html").read_text()
        self.assertIn('<p class="earlier-results"><a href="/brands/serax.html" rel="prev">', second)
        self.assertIn('<link rel="canonical" href="https://formground.com/brands/serax-2.html">', second)
        self.assertNotIn("New from Serax", second)                      # the New strip is page 1 only
        small = (DOCS / "brands" / "oven-editions.html").read_text()
        self.assertNotIn('id="see-more"', small)                        # 60 pieces or fewer: one page
        sm = (DOCS / "sitemap.xml").read_text()
        self.assertIn("/brands/serax-2.html", sm)
        for f in _g.glob(str(DOCS / "brands" / "*.html")):
            self.assertLess(Path(f).stat().st_size, 400_000, f)         # was 1.9 MB for the biggest maker

    def test_architect_pages_have_share_buttons_and_no_left_hand_tagline(self):
        firm = (DOCS / "architects" / "bernardo-bader-architekten.html").read_text()
        body = firm[firm.index("<main>"):]
        self.assertNotIn('<p class="page-tagline">Architects.</p>', body)
        self.assertNotIn('Browse every house on Work', body)
        self.assertNotIn('each pulled from their own project page', body)
        self.assertIn('<button class="share-btn"', body)
        self.assertIn('data-brand="Bernardo Bader Architekten"', body)
        self.assertIn("/share.js?v=", firm)
        houses = (DOCS / "work" / "houses.html").read_text()
        self.assertIn('<button class="share-btn"', houses)

    def test_the_designers_index_lists_designers_not_a_placeholder(self):
        for folder in ("docs", "frontend"):
            page = (ROOT / folder / "designers.html").read_text()
            self.assertGreater(page.count('class="maker-card"'), 100, folder)
            self.assertNotIn("coming soon", page.lower(), folder)

    def test_designer_pages_use_the_standard_product_card_with_share(self):
        page = (DOCS / "designers" / "claire-vos.html").read_text()
        self.assertGreaterEqual(page.count('<a class="card"'), 2)
        self.assertEqual(page.count('<a class="card"'), page.count('<button class="share-btn"'))
        self.assertNotIn('class="maker-card"', page)
        self.assertIn("/share.js?v=", page)

    def test_big_designer_pages_are_paged_at_60(self):
        first = (DOCS / "designers" / "jaime-hayon.html").read_text()
        grid = first[first.index('<div class="grid" data-listing-grid>'):]
        grid = grid[:grid.index('<div class="load-more-row">')]
        self.assertEqual(len(re.findall(r'<a class="card"', grid)), 60)
        self.assertIn('href="/designers/jaime-hayon-2.html"', first)
        third = (DOCS / "designers" / "jaime-hayon-3.html").read_text()
        self.assertIn('<p class="earlier-results"><a href="/designers/jaime-hayon-2.html" rel="prev">', third)
        self.assertIn("/designers/jaime-hayon-3.html", (DOCS / "sitemap.xml").read_text())
        small = (DOCS / "designers" / "claire-vos.html").read_text()
        self.assertNotIn('id="see-more"', small)

    def test_houses_pages_are_listing_pages_with_the_standard_card(self):
        for name in ("houses-austria", "houses", "houses-sweden"):
            page = (DOCS / "work" / f"{name}.html").read_text()
            self.assertIn('class="results-grid"', page, name)
            self.assertIn('<h1 class="listing-title">', page, name)
            self.assertIn('class="work-menu-cat is-current"', page, name)         # the Houses chip is selected
            self.assertNotIn('type-grid--houses', page, name)
            self.assertLessEqual(len(re.findall(r'<a class="card"', page)), 60, name)
            self.assertEqual(len(re.findall(r'<a class="card"', page)), page.count('<button class="share-btn"'), name)
        austria = (DOCS / "work" / "houses-austria.html").read_text()
        self.assertRegex(austria, r'<p class="card-detail">[^<]*Austria[^<]*20\d\d</p>')   # location . year, as in search
        self.assertIn('<h2><a href="/architects.html">Architects &rarr;</a></h2>', austria)
        self.assertIn('/architects/bernardo-bader-architekten.html', austria)
        houses = (DOCS / "work" / "houses.html").read_text()
        self.assertIn('id="see-more"', houses)
        self.assertIn('href="/work/houses-2.html"', houses)

    def test_seo_hygiene_of_every_real_page(self):
        """Unique titles, one H1, a description short enough to show whole in search results (2026-10-04 audit)."""
        import glob as _g
        import html as _h
        titles, problems = {}, []
        for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            name = os.path.relpath(f, DOCS)
            if _is_stub(text) or name == "search.html":
                continue
            title = re.search(r"<title>(.*?)</title>", text, re.S).group(1).strip()
            if title in titles:
                problems.append(f"duplicate title {title!r}: {name} and {titles[title]}")
            titles[title] = name
            body = re.sub(r"<style.*?</style>|<script.*?</script>|<!--.*?-->", "", text, flags=re.S)
            if len(re.findall(r"<h1[\s>]", body)) != 1:
                problems.append(f"{name}: not exactly one h1")
            desc = re.search(r'<meta name="description" content="([^"]*)"', text)
            if not desc:
                problems.append(f"{name}: no description")
            elif len(_h.unescape(desc.group(1))) > 160:
                problems.append(f"{name}: description over 160 characters")
        self.assertEqual(problems[:8], [])

    def test_no_joined_or_catch_all_designer_pages(self):
        import glob as _g
        names = []
        for f in _g.glob(str(DOCS / "designers" / "*.html")):
            names.append(re.search(r'<h1 class="maker-name">(.*?)</h1>', Path(f).read_text()).group(1))
        self.assertFalse([n for n in names if re.search(r"aa\.?vv|,| / ", n, re.I)])
        self.assertFalse((DOCS / "designers" / "aa-vv.html").exists())
        self.assertTrue((DOCS / "designers" / "erwan-bouroullec.html").exists())     # the Bouroullec credits were split
        index = (DOCS / "designers.html").read_text()
        self.assertNotIn("Aa.Vv.", index)

    def test_a_lone_search_result_is_a_normal_sized_card(self):
        css = (ROOT / "frontend" / "work-results.css").read_text()
        rule = css[css.index("  .results-grid {"):]
        rule = rule[:rule.index("}")]
        self.assertIn("auto-fill", rule)          # auto-fit stretched one result ("pawson") across the whole row
        self.assertNotIn("auto-fit", rule)
        self.assertEqual(css, (DOCS / "work-results.css").read_text())

    def test_every_page_has_a_social_preview_image(self):
        import glob as _g
        from PIL import Image
        self.assertEqual(Image.open(DOCS / "og-default.png").size, (1200, 630))
        self.assertEqual((ROOT / "frontend" / "og-default.png").read_bytes(), (DOCS / "og-default.png").read_bytes())
        problems = []
        for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            name = os.path.relpath(f, DOCS)
            if _is_stub(text) or name == "search.html":
                continue
            m = re.search(r'property="og:image" content="([^"]*)"', text)
            if not m:
                problems.append(f"{name}: no og:image")
            elif "favicon" in m.group(1):
                problems.append(f"{name}: favicon as preview")
            if 'name="twitter:image"' not in text and not name.startswith("brands/"):
                problems.append(f"{name}: no twitter:image")
        self.assertEqual(problems[:6], [])

    def test_maker_pages_use_the_default_preview_not_the_makers_photo(self):
        for name in ("hay.html", "serax.html", "graypants.html"):
            page = (DOCS / "brands" / name).read_text()
            self.assertIn('property="og:image" content="https://formground.com/og-default.png"', page, name)
            self.assertIn('name="twitter:image" content="https://formground.com/og-default.png"', page, name)

    def test_results_feedback_and_visit_id_are_wired_and_disclosed(self):
        work = (DOCS / "work.html").read_text()
        self.assertEqual(work.count('id="results-feedback"'), 1)
        js = (DOCS / "search.js").read_text()
        for value in ("not_wanted", "close", "spot_on"):
            self.assertIn(value, js)
        self.assertEqual(js, (ROOT / "frontend" / "search.js").read_text())
        self.assertIn("visit_id", (DOCS / "fg-track.js").read_text())
        privacy = (DOCS / "privacy.html").read_text()
        self.assertIn("random visit number", privacy)
        self.assertIn("How were these results?", privacy)

    def test_page_titles_are_unique_descriptive_and_not_too_long(self):
        import glob as _g, html as _h
        seen, problems = {}, []
        for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            if _is_stub(text):
                continue
            name = os.path.relpath(f, DOCS)
            title = _h.unescape(re.search(r"<title>(.*?)</title>", text, re.S).group(1).strip())
            if len(title) > 70:
                problems.append(f"{name}: title is {len(title)} characters")
            if title in seen:
                problems.append(f"{name}: same title as {seen[title]}")
            seen[title] = name
            if re.match(r"(work|brands|designers|architects)/[^/]+\.html$", name) and name.count("-") >= 0:
                if title.split(" — ")[0].strip().lower() in ("work", "makers", "designers", "architects"):
                    problems.append(f"{name}: title is only a section name")
        self.assertEqual(problems[:6], [])
        chairs = (DOCS / "work" / "chairs.html").read_text()
        self.assertIn("<title>Chairs from independent and established makers — Formground</title>", chairs)
        hay = (DOCS / "brands" / "hay.html").read_text()
        self.assertRegex(hay, r"<title>HAY: [a-z, ]+ — Formground</title>")

    def test_listing_pages_do_not_mark_up_linked_out_items_as_priced_products(self):
        import glob as _g
        bad = []
        for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            if '"@type":"Product"' in text.replace(" ", "") or '"@type":"Offer"' in text.replace(" ", ""):
                bad.append(os.path.relpath(f, DOCS))
        self.assertEqual(bad[:5], [])
        chairs = (DOCS / "work" / "chairs.html").read_text()
        self.assertIn('"@type":"ItemList"', chairs.replace(" ", ""))

    def test_every_generated_page_loads_the_tracker(self):
        import glob as _g
        missing = []
        for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            name = os.path.relpath(f, DOCS)
            if _is_stub(text) or name in ("search.html", "404.html"):
                continue
            if "fg-track.js" not in text:
                missing.append(name)
        self.assertEqual(missing[:6], [])

    def test_feedback_event_carries_the_campaign_tags(self):
        js = (DOCS / "search.js").read_text()
        line = [l for l in js.splitlines() if 'event_type: "feedback"' in l][0]
        self.assertIn("...UTM", line)

    def test_events_are_posted_with_fetch_not_sendbeacon(self):
        # sendBeacon is always credentialed; the server's wildcard CORS answer makes browsers refuse it
        for name in ("fg-track.js", "search.js"):
            text = (DOCS / name).read_text()
            code = "\n".join(l for l in text.splitlines() if not l.strip().startswith(("//", "*", "/*")))
            self.assertNotIn("navigator.sendBeacon(", code, name)
            self.assertIn('credentials: "omit"', code, name)
            self.assertIn("keepalive: true", code, name)

    def test_team_browsers_can_opt_out_of_tracking(self):
        track = (DOCS / "fg-track.js").read_text()
        self.assertIn("fg_internal", track)
        search = (DOCS / "search.js").read_text()
        self.assertIn("internal=1", search)
        self.assertIn("INTERNAL", search)

    def test_buying_guides_hub_pages_and_type_page_text(self):
        hub = (DOCS / "guides.html").read_text()
        sitemap = (DOCS / "sitemap.xml").read_text()
        self.assertIn("https://formground.com/guides.html", sitemap)
        for slug in ("pendant-lamps", "dining-tables", "sofas", "portable-lamps", "table-lamps", "floor-lamps", "chairs"):
            self.assertIn(f"/guides/{slug}.html", hub)
            self.assertIn(f"https://formground.com/guides/{slug}.html", sitemap)
            guide = (DOCS / "guides" / f"{slug}.html").read_text()
            self.assertIn("Sources and further reading", guide)
            self.assertIn(f'href="/work/{slug}.html"', guide)              # back to the type page
            visible = re.sub(r"<style.*?</style>|<script.*?</script>", "", guide, flags=re.S)
            self.assertNotRegex(re.sub(r"<[^>]+>", " ", visible), r"(?i)\breal\b")
            type_page = (DOCS / "work" / f"{slug}.html").read_text()
            self.assertEqual(type_page.count('<section class="listing-about">'), 1)
            self.assertIn(f'href="/guides/{slug}.html"', type_page)
            self.assertIn('<p class="listing-intro">', type_page)
        # page 2+ and other types stay as they were
        self.assertEqual((DOCS / "work" / "pendant-lamps-2.html").read_text().count('<section class="listing-about">'), 0)
        self.assertEqual((DOCS / "work" / "vases.html").read_text().count('<section class="listing-about">'), 0)

    def test_guide_source_links_are_https_and_labelled_as_not_endorsements(self):
        import guides_content
        for g in guides_content.GUIDES:
            self.assertTrue(g["sources"], g["slug"])
            for label, href in g["sources"]:
                self.assertTrue(href.startswith("https://"), href)
                self.assertTrue(label.strip())
        self.assertIn("not endorsements", guides_content.LABEL_NOTE)

    def test_every_footer_links_to_the_guides(self):
        import glob as _g
        missing = []
        for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            if _is_stub(text):
                continue
            if "privacy.html\">Privacy" in text and 'href="/guides.html">Guides' not in text:
                missing.append(os.path.relpath(f, DOCS))
        self.assertEqual(missing[:5], [])

    def test_no_page_has_double_escaped_ampersands_in_urls(self):
        # "&amp;amp;width=800" reads as a query parameter called "amp;width", so the image resize silently stops working
        import glob as _g
        bad = [os.path.relpath(f, DOCS) for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True)
               if "&amp;amp;" in Path(f).read_text()]
        self.assertEqual(bad[:5], [])

    def test_edit_pages_have_original_notes_and_guide_links(self):
        pend = (DOCS / "edits" / "pendant-lamps.html").read_text()
        self.assertEqual(pend.count('<section class="edit-notes">'), 1)
        self.assertIn("How this Edit is chosen", pend)
        self.assertIn('href="/guides/pendant-lamps.html">Read the full buying guide', pend)
        self.assertIn("from 1,078 pendant lamps", pend)
        rd = (DOCS / "edits" / "round-dining-tables.html").read_text()
        self.assertRegex(rd, r"pieces from \d+ round dining tables")           # the Edit's own set, not the whole type
        self.assertIn('href="/guides/dining-tables.html"', rd)
        vases = (DOCS / "edits" / "vases.html").read_text()                      # no guide for vases yet
        self.assertIn("How this Edit is chosen", vases)
        self.assertNotIn("Read the full buying guide", vases)

    def test_operator_identity_is_on_about_contact_and_privacy(self):
        for page in ("about", "contact", "privacy"):
            text = (DOCS / f"{page}.html").read_text()
            self.assertIn("Formground AB, Sweden", text, page)
            self.assertIn("info@formground.com", text, page)
        self.assertIn("Swedish Authority for", (DOCS / "privacy.html").read_text())

    def test_home_page_explains_the_site_above_the_footer(self):
        home = (DOCS / "index.html").read_text()
        self.assertEqual(home.count('<p class="foot-about">'), 1)
        self.assertIn("Every piece links straight to the maker's own site.", home)
        self.assertIn('href="/about.html">Read more about Formground', home)
        self.assertEqual(home, (ROOT / "frontend" / "index.html").read_text())
        self.assertNotRegex(re.sub(r"<[^>]+>", " ", home.split('<p class="foot-about">')[1].split("</p>")[0]), r"(?i)\breal\b")

    def test_designer_pages_have_no_left_hand_tagline(self):
        page = (DOCS / "designers" / "claire-vos.html").read_text()
        self.assertNotIn("Looking for who made it?", page)

    def test_surprise_me_is_a_chip_not_part_of_the_search_box(self):
        work = (DOCS / "work.html").read_text()
        self.assertEqual(work.count('id="discover-chip"'), 1)          # search.js shuffles via this id
        self.assertEqual(work.count("Surprise me</span>"), 1)
        box = work[work.index('class="ask-box"'):work.index("</form>")]
        self.assertNotIn("Surprise me", box)                              # the search box only searches
        self.assertNotIn("inline-chip", work)
        for page in ("work/table-lamps.html", "work/furniture.html", "work/houses.html"):
            text = (DOCS / page).read_text()
            self.assertIn('class="work-menu-act" href="/work.html"', text, page)
            self.assertNotIn("Surprise me", text[text.index('class="ask-box"'):text.index("</form>")] if 'class="ask-box"' in text else "", page)

    def test_work_page_has_the_menu_with_four_categories(self):
        text = (DOCS / "work.html").read_text()
        self.assertEqual(text.count('<button type="button" class="work-menu-cat'), 4)
        # Houses first, as on the home page bento
        self.assertTrue(text.index('href="/work/houses.html"') < text.index('href="/work/furniture.html"'))
        for cat in ("houses", "furniture", "lighting", "objects"):
            self.assertIn(f'href="/work/{cat}.html"', text)
        self.assertIn("/work-menu.css?v=", text)
        self.assertIn("/work-menu.js?v=", text)


if __name__ == "__main__":
    unittest.main()
