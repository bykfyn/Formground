"""Galleries (retailers.json kind "gallery"): their own page, "Shown at" on the pages of the makers and designers they show,
and never counted as stockists ("Where to buy")."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scraper"))

import generate_brand_pages as gbp  # noqa: E402


class Galleries(unittest.TestCase):
    def test_galleries_are_not_stockists(self):
        galleries = {g["name"] for g in gbp.load_galleries()}
        self.assertTrue(galleries)
        for groups in gbp.load_stockists_by_brand().values():
            self.assertFalse(galleries & {name for name, _ in groups})

    def test_galleries_for_matches_names_ignoring_case(self):
        self.assertTrue(any(g["name"] == "Studiotwentyseven" for g in gbp.galleries_for("de Sede")))
        self.assertEqual(gbp.galleries_for("A name no gallery shows"), [])

    def test_shown_at_links_to_the_gallery_page(self):
        section = gbp.render_galleries_section("Rooms", gbp.galleries_for("Rooms"))
        self.assertIn('href="/galleries/kolkhoze.html"', section)
        self.assertEqual(gbp.render_galleries_section("Nobody", []), "")

    def test_every_gallery_has_text_and_a_page_for_each_unlinked_designer(self):
        import creator_texts
        for g in gbp.load_galleries():
            self.assertIsNotNone(creator_texts.get("retailers", gbp.gallery_slug(g)), g["name"])
            self.assertTrue((ROOT / "docs" / "galleries" / f"{gbp.gallery_slug(g)}.html").exists(), g["name"])


if __name__ == "__main__":
    unittest.main()
