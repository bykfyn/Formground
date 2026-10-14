"""
Guards for the 2026-10-04 URL restructure: type pages under /work/, Edits under
/edits/, every old address a redirect stub, one taxonomy feeding the menu.

    python3 -m unittest discover tests
"""

import glob
import os
import json
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
        self.assertIn("/brands/serax.html", sm)
        self.assertNotIn("/brands/serax-2.html", sm)                    # continuation pages: linked and crawlable, not in the sitemap
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
        # a big designer credited at ONE maker is paged at 60 (a designer across several makers has one page with
        # brand chips instead: see DesignerBrandFilterTests)
        first = (DOCS / "designers" / "hella-jongerius.html").read_text()
        self.assertNotIn('id="brand-filters"', first)
        grid = first[first.index('<div class="grid" data-listing-grid>'):]
        grid = grid[:grid.index('<div class="load-more-row">')]
        self.assertEqual(len(re.findall(r'<a class="card"', grid)), 60)
        self.assertIn('href="/designers/hella-jongerius-2.html"', first)
        second = (DOCS / "designers" / "hella-jongerius-2.html").read_text()
        self.assertIn('<p class="earlier-results"><a href="/designers/hella-jongerius.html" rel="prev">', second)
        self.assertNotIn("/designers/hella-jongerius-2.html", (DOCS / "sitemap.xml").read_text())   # continuation pages: not in the sitemap
        small = (DOCS / "designers" / "claire-vos.html").read_text()
        self.assertNotIn('id="see-more"', small)

    def test_sitemap_lists_primary_pages_only_not_numbered_continuation_pages(self):
        sm = (DOCS / "sitemap.xml").read_text()
        for url in ("/work/sofas.html", "/brands/serax.html", "/designers/hella-jongerius.html"):
            self.assertIn(url, sm, url)
        for url in ("/work/sofas-2.html", "/work/chairs-24.html", "/brands/serax-2.html", "/designers/hella-jongerius-2.html"):
            self.assertNotIn(url, sm, url)
            self.assertTrue((DOCS / url.lstrip("/")).exists(), url)       # the pages themselves still exist (and stay linked)
        self.assertLess(sm.count("<loc>"), 800)

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
        self.assertNotRegex(austria, r'<p class="card-detail">[^<]+</p>')                  # no location or year under the firm (2026-10-12)
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

    def test_pendant_lamps_edit_shows_twelve_pieces(self):
        # the paid-test pins say "Twelve pendant lamps": keep the page honest if the cap ever changes
        page = (DOCS / "edits" / "pendant-lamps.html").read_text()
        grid = page.split('<section class="edit-notes">')[0]
        self.assertEqual(len(re.findall(r'class="edit-feature"', grid)) or len(re.findall(r'<figure class="edit-card', grid)) or grid.count('data-product='), 12)

    def test_edit_pages_have_original_notes_and_guide_links(self):
        pend = (DOCS / "edits" / "pendant-lamps.html").read_text()
        self.assertEqual(pend.count('<section class="edit-notes">'), 1)
        self.assertIn("How this Edit is chosen", pend)
        self.assertIn('href="/guides/pendant-lamps.html">Read the full buying guide', pend)
        self.assertRegex(pend, r"from [\d,]+ pendant lamps")                  # the count grows as makers are added
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

    def test_no_independent_claim_in_page_descriptions_and_no_tier_chips_on_makers(self):
        # "independent" is a rough internal flag (default for every brand not hand-marked established), so it is
        # not claimed in descriptions, and the Independent/Established chips are off the Makers directory
        import glob as _g
        bad = []
        for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            if _is_stub(text):
                continue
            for m in re.finditer(r'<meta [^>]*(?:description)[^>]*content="([^"]*)"', text):
                if re.search(r"(?i)\bindependent makers\b", m.group(1)):
                    bad.append(os.path.relpath(f, DOCS))
        self.assertEqual(bad[:5], [])
        makers = (DOCS / "makers.html").read_text()
        self.assertNotIn('data-tier="independent">Independent Makers', makers)
        self.assertNotIn('data-tier="established">Established Makers', makers)

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


class BrandDesignerLinkTests(unittest.TestCase):
    """The "Designers who work with X" section on maker pages links only to designer pages that exist."""

    CHIP = re.compile(r'class="designer-chip" href="(/designers/[^"]+)"')

    def _brand_pages(self):
        return sorted(glob.glob(str(DOCS / "brands" / "*.html")))

    def test_every_designer_link_points_at_a_real_page(self):
        broken = []
        for path in self._brand_pages():
            for href in self.CHIP.findall(Path(path).read_text()):
                if not (DOCS / href.split("?")[0].lstrip("/")).exists():
                    broken.append((os.path.basename(path), href))
        self.assertEqual(broken, [])

    def test_section_exists_on_makers_that_credit_designers(self):
        with_section = [p for p in self._brand_pages() if "Designers who work with" in Path(p).read_text()]
        self.assertGreaterEqual(len(with_section), 10)

    def test_section_only_on_a_makers_first_page_and_never_empty(self):
        for path in self._brand_pages():
            text = Path(path).read_text()
            name = os.path.basename(path)
            numbered = re.match(r"^(.*)-\d{1,2}\.html$", name)    # "x-2.html" (but not "ghidini-1961.html")
            if numbered and (DOCS / "brands" / f"{numbered.group(1)}.html").exists() and "Designers who work with" in text:
                self.fail(f"{name}: designers section repeated on a numbered page")
            if "Designers who work with" in text:
                self.assertTrue(self.CHIP.search(text), f"{name}: heading with no designers")

    def test_no_designer_listed_twice_on_one_page(self):
        for path in self._brand_pages():
            links = self.CHIP.findall(Path(path).read_text())
            self.assertEqual(len(links), len(set(links)), os.path.basename(path))


class DesignerBrandFilterTests(unittest.TestCase):
    """A designer credited across 2+ makers has one page with brand chips; a maker's link opens it filtered."""

    def _multi_brand_pages(self):
        return [p for p in sorted(glob.glob(str(DOCS / "designers" / "*.html"))) if 'id="brand-filters"' in Path(p).read_text()]

    def test_there_are_multi_brand_pages_with_chips_and_script(self):
        pages = self._multi_brand_pages()
        self.assertGreaterEqual(len(pages), 20)
        for p in pages:
            text = Path(p).read_text()
            self.assertIn('data-slug=""', text, os.path.basename(p))        # the "All" chip
            self.assertIn("brand-filters", text.split("<script>")[-1] if "<script>" in text else "", os.path.basename(p))

    def test_every_chip_matches_cards_and_every_card_has_a_slug(self):
        for p in self._multi_brand_pages():
            text = Path(p).read_text()
            chip_slugs = set(re.findall(r'class="filter-chip[^"]*" data-slug="([^"]+)"', text))
            card_slugs = re.findall(r'<a class="card"[^>]*data-slug="([^"]*)"', text)
            self.assertGreaterEqual(len(chip_slugs), 2, os.path.basename(p))
            self.assertEqual(set(card_slugs), chip_slugs, os.path.basename(p))

    def test_multi_brand_designers_have_no_numbered_pages(self):
        for p in self._multi_brand_pages():
            base = os.path.basename(p)[:-5]
            self.assertEqual(glob.glob(str(DOCS / "designers" / f"{base}-[0-9]*.html")), [], base)

    def test_maker_links_carry_the_brand_only_for_multi_brand_designers(self):
        multi = {os.path.basename(p) for p in self._multi_brand_pages()}
        for path in glob.glob(str(DOCS / "brands" / "*.html")):
            for href in re.findall(r'class="designer-chip" href="(/designers/[^"]+)"', Path(path).read_text()):
                page = os.path.basename(href.split("?")[0])
                self.assertEqual("?brand=" in href, page in multi, f"{os.path.basename(path)}: {href}")
                if "?brand=" in href:
                    brand_slug = href.split("?brand=")[1]
                    self.assertIn(f'data-slug="{brand_slug}"', (DOCS / "designers" / page).read_text(), href)


class CreatorsPageTests(unittest.TestCase):
    """The Creators page: one column per category with a weekly-rotating sample of real profiles."""

    def _page(self):
        return (DOCS / "creators.html").read_text()

    def test_each_category_has_five_profile_links_that_exist(self):
        page = self._page()
        for group in ("architects", "designers", "makers"):
            block = page[page.index(f"<!--PROFILES:{group}-->"):page.index(f"<!--/PROFILES:{group}-->")]
            hrefs = re.findall(r'<a class="pf-row" href="([^"]+)"', block)
            self.assertEqual(len(hrefs), 5, group)
            self.assertEqual(len(set(hrefs)), 5, group)
            for href in hrefs:
                self.assertTrue((DOCS / href.lstrip("/")).exists(), href)
            self.assertIn(f'href="{group}.html">See all', block)

    def test_no_placeholder_text_and_every_profile_slot_links_to_a_real_edit(self):
        page = self._page()
        self.assertNotIn("Placeholder", page)
        slugs = re.findall(r'<a class="ed-card" href="/edits/([a-z0-9-]+)\.html"', page)
        self.assertEqual(len(slugs), page.count(">In profile<"))          # a label never appears without its card
        for slug in slugs:
            self.assertTrue((DOCS / "edits" / f"{slug}.html").exists(), slug)

    def test_the_sample_is_stable_within_a_week_and_changes_between_weeks(self):
        import datetime
        import generate_creators_page as gc
        cards = gc.read_cards("makers")
        a = gc.sample(cards, "makers", datetime.date(2026, 10, 12))
        self.assertEqual(a, gc.sample(cards, "makers", datetime.date(2026, 10, 15)))     # same ISO week
        self.assertNotEqual(a, gc.sample(cards, "makers", datetime.date(2026, 10, 19)))  # next week

    def test_a_profile_edit_shows_with_links_to_its_page_and_to_all_edits(self):
        import datetime
        import generate_creators_page as gc
        saved = dict(gc.PROFILE_EDITS)
        gc.PROFILE_EDITS.clear()
        gc.PROFILE_EDITS["makers"] = {"slug": "kallemo", "name": "Källemo", "line": "A line.", "image": "https://x/y.jpg"}
        try:
            out = gc.column_html("makers", gc.read_cards("makers"), datetime.date(2026, 10, 12), 205)
        finally:
            gc.PROFILE_EDITS.clear(); gc.PROFILE_EDITS.update(saved)
        self.assertIn('href="/edits/kallemo.html"', out)
        self.assertIn('href="/edits.html">All Edits', out)
        self.assertIn("In profile", out)

    def test_the_profiled_creator_is_not_also_in_the_list_below_it(self):
        page = self._page()
        for group in ("architects", "designers", "makers"):
            block = page[page.index(f"<!--PROFILES:{group}-->"):page.index(f"<!--/PROFILES:{group}-->")]
            featured = re.search(r'<a class="ed-card" href="/edits/([a-z0-9-]+)\.html"', block)
            if featured:
                self.assertNotIn(f'/{featured.group(1)}.html"', block.split('class="pf-list"')[1])

    def test_phone_shows_three_entries(self):
        self.assertIn(".pf-list .pf-row:nth-child(n+4) { display: none; }", self._page())


class CreatorTextTests(unittest.TestCase):
    """The creator profile text follows docs/formground-creator-text-template.md; scheduled entries stay hidden until their day."""

    def setUp(self):
        import creator_texts
        self.ct = creator_texts
        self.all = creator_texts.load_all()          # every creator text (all live on their pages at once)
        self.live = creator_texts.load()             # entries whose profile Edit is live on the build date
        self.edits = {k: v for k, v in self.all.items() if v.get("edit")}

    def test_there_are_texts_and_each_is_60_to_120_words_in_2_or_3_paragraphs(self):
        self.assertGreaterEqual(len(self.all), 10)
        for key, e in self.all.items():
            words = sum(len(p.split()) for p in e["paragraphs"])
            self.assertTrue(60 <= words <= 120, (key, words))
            self.assertIn(len(e["paragraphs"]), (2, 3), key)

    def test_text_is_in_our_own_voice_and_has_no_materials_row(self):
        import re
        attribution = re.compile(r"\b(its own site|their own site|the site (says|names|describes|lists)|it says|says it|"
                                 r"who say|(its|the) own profile)\b", re.I)
        for key, e in self.all.items():
            self.assertFalse(attribution.search(" ".join(e["paragraphs"])), key)
            self.assertNotIn("Materials", [k for k, _ in e["facts"]], key)

    def test_card_bg_is_a_hex_colour_when_set(self):
        for key, entry in self.all.items():
            bg =(entry.get("edit") or {}).get("card_bg")
            if bg:
                self.assertRegex(bg, r"^#[0-9a-fA-F]{6}$", key)

    def test_no_independent_or_established_label_and_no_superlatives(self):
        banned = ("independent", "established", "world-famous", "award-winning", "the best", "leading")
        for key, e in self.all.items():
            blob = (" ".join(e["paragraphs"]) + " " + " ".join(f"{k} {v}" for k, v in e["facts"])).lower()
            for word in banned:
                if word == "established" and e["group"] == "architects" and "established in 20" in blob:
                    blob = blob.replace("established in 20", "founded in 20")      # a founding year, not the label
                self.assertNotIn(word, blob, (key, word))

    def test_every_text_has_facts_in_the_template_order_and_named_sources(self):
        order = ["Country", "City", "Type", "Products", "Work", "Founded", "Made to order", "Website"]
        for key, e in self.all.items():
            labels = [k for k, _ in e["facts"]]
            self.assertEqual(labels, sorted(labels, key=order.index), key)
            self.assertTrue({"Type", "Website"} <= set(labels), key)          # Country and City only when we know them
            self.assertTrue(e["sources"] and all(u.startswith("https://") for _, u in e["sources"]), key)

    def _page(self, e):
        folder = {"architects": "architects", "makers": "brands", "designers": "designers"}[e["group"]]
        return (DOCS / folder / f"{e['page_slug']}.html").read_text()

    def test_every_text_is_on_its_creators_page_at_once_and_unknown_facts_are_left_out(self):
        for e in self.all.values():
            page = self._page(e)
            self.assertIn('class="creator-text"', page, e["name"])
            self.assertNotIn("Written by Formground", page, e["name"])       # the sourcing line is not shown on the page
            self.assertNotIn("{count}", page)
            self.assertNotIn(">Unknown<", page, e["name"])

    def test_a_creators_page_links_to_its_profile_edit_only_once_it_is_live(self):
        for key, e in self.edits.items():
            has_link = f'href="/edits/{e["edit"]["slug"]}.html">Read the profile Edit' in self._page(e)
            self.assertEqual(has_link, key in self.live, key)

    def test_a_live_profile_edit_has_its_page_picks_hub_tile_and_sitemap_entry(self):
        self.assertGreaterEqual(len(self.live), 10)
        for e in self.live.values():
            edit = (DOCS / "edits" / f"{e['edit']['slug']}.html").read_text()
            self.assertIn("In profile", edit)
            self.assertGreaterEqual(len(re.findall(r'class="(?:card|maker-card)"', edit)), 6, e["name"])
            self.assertIn(f'/edits/{e["edit"]["slug"]}.html', (DOCS / "edits.html").read_text())
            self.assertIn(f"/edits/{e['edit']['slug']}.html", (DOCS / "sitemap.xml").read_text())

    def test_a_scheduled_edit_is_not_on_the_site_before_its_day_but_its_text_is(self):
        for key, e in self.edits.items():
            if key in self.live:
                continue
            slug = e["edit"]["slug"]
            self.assertFalse((DOCS / "edits" / f"{slug}.html").exists(), slug)
            self.assertNotIn(f"/edits/{slug}.html", (DOCS / "edits.html").read_text(), slug)
            self.assertNotIn(f"/edits/{slug}.html", (DOCS / "sitemap.xml").read_text(), slug)
            self.assertIn('class="creator-text"', self._page(e), slug)              # the creator's page text is live

    def test_the_publish_date_decides_what_is_live(self):
        import datetime
        import os
        key = next((k for k, e in self.edits.items() if e.get("publish") and datetime.date.fromisoformat(e["publish"]) > datetime.date(2026, 10, 12)), None)
        self.assertIsNotNone(key)
        e = self.edits[key]
        before = datetime.date.fromisoformat(e["publish"]) - datetime.timedelta(days=1)
        try:
            os.environ["FG_TODAY"] = before.isoformat()
            self.assertNotIn(key, self.ct.load())
            os.environ["FG_TODAY"] = e["publish"]
            self.assertIn(key, self.ct.load())
        finally:
            os.environ.pop("FG_TODAY", None)

    def test_scheduled_dates_are_unique_per_day_and_the_daily_workflow_exists(self):
        dates = [e["publish"] for e in self.edits.values() if e.get("publish") and e["publish"] > "2026-10-11"]
        self.assertEqual(len(dates), len(set(dates)))
        wf = (ROOT / ".github" / "workflows" / "publish_scheduled.yml").read_text()
        self.assertIn('cron: "0 7 * * *"', wf)
        self.assertIn("python scraper/build_site.py", wf)
        self.assertIn("unittest discover tests", wf)
        self.assertLess(wf.index("unittest discover tests"), wf.index("git push"))       # tests run before anything is pushed


class PortfolioDesignerTests(unittest.TestCase):
    """Designers shown by their own work (data/portfolio_designers.json), like architects' houses."""

    def setUp(self):
        self.designers = json.loads((ROOT / "data" / "portfolio_designers.json").read_text())

    def test_each_has_a_page_a_card_on_the_index_and_a_sitemap_entry(self):
        index = (DOCS / "designers.html").read_text()
        sitemap = (DOCS / "sitemap.xml").read_text()
        for d in self.designers:
            slug = re.sub(r"[^a-z0-9]+", "-", d["name"].lower().replace("é", "e")).strip("-")
            self.assertTrue((DOCS / "designers" / f"{slug}.html").exists(), d["name"])
            self.assertIn(f'href="/designers/{slug}.html"', index, d["name"])
            self.assertIn(f"/designers/{slug}.html", sitemap, d["name"])

    def test_every_work_has_a_name_an_image_and_a_link_to_the_designers_own_site(self):
        for d in self.designers:
            self.assertGreaterEqual(len(d["works"]), 2, d["name"])
            host = re.sub(r"^https?://(www\.)?", "", d["url"]).split("/")[0]
            for w in d["works"]:
                self.assertTrue(w["name"].strip(), d["name"])
                self.assertTrue(w["image"].startswith("https://"), (d["name"], w["name"]))
                self.assertIn(host, w["url"], (d["name"], w["name"]))

    def test_creators_page_counts_them(self):
        n = len(re.findall(r'<a class="maker-card" href="/designers/', (DOCS / "designers.html").read_text()))
        self.assertIn(f'group-count">{n:,} designers', (DOCS / "creators.html").read_text())


class SheerdFooterLinkTests(unittest.TestCase):
    def test_every_footer_links_to_sheerd(self):
        import glob as _g
        missing = []
        for f in _g.glob(str(DOCS / "**" / "*.html"), recursive=True):
            text = Path(f).read_text()
            if "&copy; 2026 Formground" not in text:
                continue                                   # redirect stubs have no footer
            if 'href="https://sheerd.com" target="_blank" rel="noopener">Powered by Sheerd</a>' not in text:
                missing.append(os.path.relpath(f, DOCS))
        self.assertEqual(missing[:5], [])


class PhotoSafetyTests(unittest.TestCase):
    def test_broken_photo_fallback_ships_with_the_shared_script(self):
        front = (ROOT / "frontend" / "fg-track.js").read_text()
        self.assertIn("Broken-photo fallback", front)
        self.assertEqual(front, (DOCS / "fg-track.js").read_text())

    def test_curated_photo_check_finds_the_photos_on_the_pages_people_see_first(self):
        import sys
        sys.path.insert(0, str(ROOT / "scraper"))
        import check_curated_images as c
        photos = c.photos_by_page()
        self.assertGreater(len(photos), 150)
        self.assertTrue(any("index.html" in pages for pages in photos.values()))
        self.assertTrue(any(p.startswith("edits/") for pages in photos.values() for p in pages))
        self.assertIn("check_curated_images.py", (ROOT / ".github" / "workflows" / "check_links.yml").read_text())


class LookEditTests(unittest.TestCase):
    """Look Edits (data/looks.json, generate_look_pages.py): a room from pieces by different makers, on one grid board."""

    @classmethod
    def setUpClass(cls):
        cls.looks = json.loads((ROOT / "data" / "looks.json").read_text())

    def test_every_look_has_a_page_a_board_tile_and_a_card_per_piece_and_is_in_the_sitemap_and_hub(self):
        sitemap = (DOCS / "sitemap.xml").read_text()
        hub = (DOCS / "edits.html").read_text()
        self.assertGreaterEqual(len(self.looks), 2)
        for look in self.looks:
            page = (DOCS / "edits" / f"{look['slug']}.html").read_text()
            n = len(look["picks"])
            self.assertEqual(len(re.findall(r'<a class="look-tile', page)), n, look["slug"])
            self.assertEqual(len(re.findall(r'<p class="look-role">', page)), n, look["slug"])
            self.assertEqual(page.count('<a class="card"'), n, look["slug"])
            self.assertIn(f"/edits/{look['slug']}.html", sitemap)
            self.assertIn(f'href="/edits/{look["slug"]}.html"', hub)
            self.assertIn(look["title"], hub)

    def test_board_tiles_link_out_to_the_maker_and_carry_tracking_attributes(self):
        for look in self.looks:
            page = (DOCS / "edits" / f"{look['slug']}.html").read_text()
            for tile in re.findall(r'<a class="look-tile[^>]*>', page):
                self.assertIn('target="_blank"', tile)
                self.assertIn('rel="noopener noreferrer"', tile)
                self.assertIn("data-brand=", tile)
                self.assertIn("data-product=", tile)
                self.assertRegex(tile, r'href="https?://')

    def test_every_pick_has_a_board_area_and_no_two_tiles_overlap(self):
        for look in self.looks:
            taken = set()
            for pick in look["picks"]:
                c0, c1, r0, r1 = look["areas"][pick["slot"]]
                cells = {(c, r) for c in range(c0, c1) for r in range(r0, r1)}
                self.assertFalse(cells & taken, (look["slug"], pick["slot"]))
                taken |= cells
                self.assertTrue(1 <= c0 < c1 <= 13, look["slug"])

    def test_look_pages_use_the_shared_board_grid_and_one_card_row(self):
        for look in self.looks:
            page = (DOCS / "edits" / f"{look['slug']}.html").read_text()
            self.assertIn("grid-template-columns: repeat(12, 1fr)", page)
            self.assertIn("gap: 8px", page)
            self.assertIn('<p class="eyebrow">Edit &middot; ', page)


class FooterOrderTests(unittest.TestCase):
    def test_footer_lists_edits_in_the_same_order_as_the_main_nav(self):
        """The header nav reads Work, Creators, Edits; the footer follows that order (a page leaves out its own link)."""
        for name in ("index.html", "about.html", "creators.html", "brands/hay.html", "work/sofas.html", "edits/chairs.html"):
            page = (DOCS / name).read_text()
            footer = page[page.index("&copy; 2026 Formground"):]
            footer = footer[:footer.index("Powered by Sheerd")]
            links = re.findall(r'<a href="/([a-z-]+)\.html">', footer)
            present = [l for l in ("work", "creators", "edits") if l in links]
            self.assertEqual(links[links.index(present[0]):links.index(present[0]) + len(present)], present, name)
            if "marketplace" in links and "edits" in links:
                self.assertLess(links.index("edits"), links.index("marketplace"), name)


class TypeTileImageTests(unittest.TestCase):
    def test_hand_picked_type_tile_photos_are_used_on_the_furniture_hub(self):
        page = (DOCS / "work" / "furniture.html").read_text()
        for slug, needle in (("folding-chairs", "beech_NL0.jpg"), ("office-chairs", "wick-swivel-ash-wheels.jpg")):
            tile = re.search(rf'<a class="maker-card" href="/work/{slug}\.html">(.*?)</a>', page, re.S).group(1)
            self.assertIn(needle, tile, slug)


class CategoryHubTests(unittest.TestCase):
    """/work/furniture|lighting|objects: the home page's look at category scale (generate_category_hubs.py)."""

    def _page(self, slug):
        return (DOCS / "work" / f"{slug}.html").read_text()

    def test_each_hub_has_the_sections_in_order_one_hidden_h1_and_the_menu_with_the_category_current(self):
        order = ["Popular types", "Browse every type", "New in ", "Edits in ", "Buying guides"]
        for slug in ("furniture", "lighting", "objects"):
            page = self._page(slug)
            body = page[page.index("<body"):]
            main = body[body.index("<main"):body.index("</main>")]
            positions = [main.index(f"<h2>{h}" if h in ("Popular types", "Browse every type") else h) for h in order]
            self.assertEqual(positions, sorted(positions), slug)
            self.assertEqual(len(re.findall(r"<h1[\s>]", main)), 1, slug)
            self.assertIn('<h1 class="sr-only">', main)
            self.assertIn(f'class="work-menu-cat is-current"', main)
            self.assertLess(main.index('class="search-wide"'), main.index('class="work-menu"'))
            self.assertLess(main.index('class="work-menu"'), main.index("<h2>Popular types"))      # search and chips come first

    def test_each_hub_lists_every_type_a_new_row_and_edits(self):
        for slug, tiles in (("furniture", 27), ("lighting", 7), ("objects", 10)):
            page = self._page(slug)
            self.assertGreaterEqual(page.count('class="maker-card"'), tiles, slug)
            self.assertEqual(page.count('class="recent-card"') >= 8, True, slug)
            self.assertIn('class="duo-col"', page, slug)
            self.assertIn('class="guide-card"', page, slug)

    def test_popular_types_is_a_five_tile_bento_and_the_closing_text_is_off(self):
        import json as _json
        popular = _json.loads((ROOT / "data" / "hub_popular.json").read_text())
        for slug, cat in (("furniture", "Furniture"), ("lighting", "Lighting"), ("objects", "Objects")):
            page = self._page(slug)
            self.assertEqual(page.count('class="bento"'), 1, slug)
            self.assertEqual(page.count('class="maker-card bt bt-big"'), 1, slug)
            self.assertEqual(page.count('class="maker-card bt"'), 4, slug)
            self.assertNotIn('class="feature-banner-frame banner-carousel"', page, slug)
            for s in [popular[cat]["big"]["slug"]] + popular[cat]["types"]:
                self.assertIn(f'class="maker-card bt', page[page.index('class="bento"'):])
                self.assertIn(f'href="/work/{s}.html"', page[page.index('class="bento"'):page.index("Browse every type")], s)
            self.assertNotIn('class="hub-about"', page, slug)             # the closing paragraph is switched off for now
            self.assertEqual(page.count('class="duo-col"'), 2, slug)       # two Edits, one row

    def test_hub_head_is_intact_and_houses_keeps_its_own_page(self):
        for slug in ("furniture", "lighting", "objects"):
            page = self._page(slug)
            self.assertRegex(page, r'<meta name="description" content="[^"]+">')
            self.assertIn(f'<link rel="canonical" href="https://formground.com/work/{slug}.html">', page)
        houses = (DOCS / "work" / "houses.html").read_text()
        self.assertNotIn("Popular types", houses)
