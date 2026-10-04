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
OLD_HREF = re.compile(r"^/(browse/|floor-lamps\.html|(%s)\.html)" % "|".join(EDIT_SLUGS))


def _is_stub(text):
    return 'http-equiv="refresh"' in text and "Formground has moved this page" in text


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


class StructureTests(unittest.TestCase):
    def test_every_old_address_is_a_stub_pointing_at_a_real_page(self):
        old = [DOCS / f"{s}.html" for s in EDIT_SLUGS] + [DOCS / "floor-lamps.html"]
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
        for s in ("table-lamps", "floor-lamps", "portable-lamps", "sofas", "furniture", "lighting", "objects"):
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

    def test_work_page_has_the_menu_with_three_categories(self):
        text = (DOCS / "work.html").read_text()
        self.assertEqual(text.count('class="work-menu-cat"'), 3)
        for cat in ("furniture", "lighting", "objects"):
            self.assertIn(f'href="/work/{cat}.html"', text)
        self.assertIn("/work-menu.css?v=", text)
        self.assertIn("/work-menu.js?v=", text)


if __name__ == "__main__":
    unittest.main()
