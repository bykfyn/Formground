"""
Regression tests for scraper/scrape.py.

Scope is the same as tests/test_query_engine.py - the specific spots
that have already broken silently once, not a general test suite.
Individual brand extractors (network-dependent) are deliberately not
covered here.

RUNNING THESE:
    python3 -m unittest discover tests
"""

import datetime
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))

import scrape  # noqa: E402


class BaseNameTests(unittest.TestCase):
    """
    _base_name() collapses variant-as-separate-listing duplicates
    (confirmed on Pinch, Bitossi, GATOMIKIO, 101cph, In Common With,
    Another Country) back into one entry per real design.
    """

    def test_splits_on_slash(self):
        self.assertEqual(scrape._base_name("Black bronze / Plywood"), "Black bronze")

    def test_splits_on_dash_with_spaces(self):
        self.assertEqual(scrape._base_name("Gallon Side Table - Low"), "Gallon Side Table")

    def test_splits_on_comma(self):
        self.assertEqual(scrape._base_name("Coffee Table Two, Ash & Walnut"), "Coffee Table Two")

    def test_no_separator_stays_whole(self):
        self.assertEqual(scrape._base_name("Nero marquina marble"), "Nero marquina marble")

    def test_br_tag_treated_as_space_not_separator(self):
        # GATOMIKIO uses a literal "<br>" between category and name -
        # it must be normalized to a space, not left as a false
        # word-boundary the way the Roman-letter filter bug did.
        self.assertEqual(scrape._base_name("TSUMUGI<br>茶椀"), "TSUMUGI 茶椀")


class JorisPoggioliMaterialSplitTests(unittest.TestCase):
    """
    Covers the real "Fernando" bug (2026-09-11): the raw material field
    is free-text prose for ~20 of 74 products, not the site's more
    common "/"-delimited list, and a plain "/" split left the whole
    sentence as one giant blob instead of short tags.
    """

    def test_or_and_ampersand_conjunctions(self):
        raw = "Rosewood 100% gloss & cream velvet or Brushed stainless steel & dark olive green velvet"
        self.assertEqual(
            scrape._split_joris_poggioli_materials(raw),
            ["Rosewood 100% gloss", "cream velvet", "Brushed stainless steel", "dark olive green velvet"],
        )

    def test_drops_other_finishes_caveat(self):
        raw = "Old oak or onyx. Other finishes available upon request."
        self.assertEqual(scrape._split_joris_poggioli_materials(raw), ["Old oak", "onyx"])

    def test_no_dangling_conjunction_after_comma_or(self):
        # ", or " must not leave a leftover "or " stuck on the next
        # fragment once the comma's already been split on.
        raw = "Sculpted in massive oak, or massive sculpted burnt oak."
        self.assertEqual(
            scrape._split_joris_poggioli_materials(raw),
            ["Sculpted in massive oak", "massive sculpted burnt oak"],
        )

    def test_simple_slash_list_still_works(self):
        self.assertEqual(
            scrape._split_joris_poggioli_materials("Black bronze / Plywood / Onyx"),
            ["Black bronze", "Plywood", "Onyx"],
        )


class ClassListingTests(unittest.TestCase):
    def test_detects_swedish_class_keywords(self):
        self.assertTrue(scrape._looks_like_a_class_listing(
            "Keramikstudio kväll, alla tekniker, egna projekt, tisdagar"
        ))

    def test_real_product_not_flagged(self):
        self.assertFalse(scrape._looks_like_a_class_listing("Ljusstake"))


class CategoryInferenceTests(unittest.TestCase):
    """Bitossi Ceramiche names pieces after their Italian object type
    rather than tagging a real category - covers 55 of 88 products."""

    def test_infers_from_unhelpful_category(self):
        self.assertEqual(scrape._infer_category_from_name("Vaso Grande", "Classici"), "Vase")

    def test_infers_from_blank_category(self):
        self.assertEqual(scrape._infer_category_from_name("Scultura Piccola", ""), "Sculpture")

    def test_leaves_real_category_untouched(self):
        self.assertEqual(scrape._infer_category_from_name("Anything", "Chair"), "Chair")

    def test_unrecognized_first_word_falls_back_to_current(self):
        self.assertEqual(scrape._infer_category_from_name("Random Name", "Classici"), "Classici")


class CleanProductTypeTests(unittest.TestCase):
    """Pinch's product_type field holds certification marks, not a real
    category - confirmed live, caused duplicate listings when used for
    grouping."""

    def test_junk_value_becomes_blank(self):
        self.assertEqual(scrape._clean_product_type("UL"), "")

    def test_real_value_untouched(self):
        self.assertEqual(scrape._clean_product_type("Novità"), "Novità")


class ScrapeRunDeleteThenInsertTests(unittest.TestCase):
    """
    Covers the real Luke Hope "tanned walnut" paddle bug (2026-09-09):
    save_product() was pure INSERT, so every scheduled run re-inserted
    every still-live product as a duplicate and never cleared a
    genuinely discontinued one. run() now deletes a brand's existing
    rows immediately before inserting its freshly scraped set, scoped
    per-brand - these tests exercise run() itself (not just
    save_product()) with fake extractors, since the bug was in how run()
    orchestrated delete-then-insert, not in save_product() alone.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        tmp_path = Path(self.tmpdir.name)

        self.db_path = tmp_path / "test.db"
        self.brands_path = tmp_path / "brands.json"
        self.report_path = tmp_path / "report.json"

        brands = [
            {"name": "Alpha", "url": "https://alpha.example/", "scrapable": True},
            {"name": "Beta", "url": "https://beta.example/", "scrapable": True},
        ]
        self.brands_path.write_text(json.dumps(brands))

        # Monkeypatch the module's own paths/registry rather than
        # touching the real repo's brands.json/database - restored in
        # tearDown regardless of test outcome.
        self._orig_db_path = scrape.DB_PATH
        self._orig_brands_path = scrape.BRANDS_PATH
        self._orig_report_path = scrape.REPORT_PATH
        self._orig_extractors = scrape.EXTRACTORS
        scrape.DB_PATH = self.db_path
        scrape.BRANDS_PATH = self.brands_path
        scrape.REPORT_PATH = self.report_path

    def tearDown(self):
        scrape.DB_PATH = self._orig_db_path
        scrape.BRANDS_PATH = self._orig_brands_path
        scrape.REPORT_PATH = self._orig_report_path
        scrape.EXTRACTORS = self._orig_extractors
        self.tmpdir.cleanup()

    def _product(self, brand, name):
        return {
            "brand": brand, "brand_url": f"https://{brand.lower()}.example/",
            "product_name": name, "product_url": f"https://{brand.lower()}.example/{name}",
            "category": "", "material_options": [], "dimensions": "", "notes": "",
            "image_url": "https://example.com/img.jpg",
        }

    def _names_for(self, brand):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT product_name FROM products WHERE brand = ?", (brand,)).fetchall()
        conn.close()
        return {r[0] for r in rows}

    def test_discontinued_product_is_removed_on_next_run(self):
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench"), self._product("Alpha", "Paddle")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        self.assertEqual(self._names_for("Alpha"), {"Bench", "Paddle"})

        # "Paddle" was discontinued on the source site - the next run's
        # extractor no longer returns it.
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        self.assertEqual(self._names_for("Alpha"), {"Bench"})

    def test_still_live_product_is_not_duplicated(self):
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        scrape.run()
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE brand = 'Alpha' AND product_name = 'Bench'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_untouched_brand_keeps_data_when_another_brand_hits_zero(self):
        # A brand whose extractor returns zero products this run keeps
        # its existing rows rather than being wiped - treated as a
        # likely transient hiccup, not a real "removed every product"
        # signal (see run()'s own comment on this).
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()

        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [],
        }
        scrape.run()
        self.assertEqual(self._names_for("Beta"), {"Vase"})


class FirstSeenCarryForwardTests(ScrapeRunDeleteThenInsertTests):
    """
    Covers the "New" page's data source (2026-09-15): first_seen must
    survive run()'s delete-then-insert unchanged for anything that
    already existed, and only get stamped for a product genuinely new
    to that brand since the previous scrape - see run()'s
    old_first_seen carry-forward logic. Subclasses the delete-then-
    insert fixture above since it's the exact same setup/teardown.
    """

    def _first_seen_for(self, brand, name):
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT first_seen FROM products WHERE brand = ? AND product_name = ?",
            (brand, name),
        ).fetchone()
        conn.close()
        return row[0] if row else None

    def test_new_product_is_stamped_with_todays_date(self):
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        today = datetime.date.today().isoformat()
        self.assertEqual(self._first_seen_for("Alpha", "Bench"), today)

    def test_still_live_product_keeps_its_original_first_seen(self):
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        original = self._first_seen_for("Alpha", "Bench")

        # Same product, second run - must not be re-stamped with a
        # later date just because it went through delete-then-insert
        # again.
        scrape.run()
        self.assertEqual(self._first_seen_for("Alpha", "Bench"), original)

    def test_preexisting_row_with_null_first_seen_is_never_restamped(self):
        # Simulates the real rollout: a product already in the catalog
        # before this column existed has first_seen = NULL (what
        # ALTER TABLE ADD COLUMN with no DEFAULT does to existing rows)
        # - it must stay NULL forever, not get "new" just because it
        # happened to predate tracking.
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE products SET first_seen = NULL WHERE product_name = 'Bench'")
        conn.commit()
        conn.close()

        scrape.run()
        self.assertIsNone(self._first_seen_for("Alpha", "Bench"))

    def test_removed_then_reintroduced_product_counts_as_new_again(self):
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench"), self._product("Alpha", "Paddle")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()

        # Discontinued - Alpha's extractor still returns real products
        # (a non-empty list, so this is a genuine delete-then-insert,
        # not the separate "0 products = keep previous data" hiccup
        # path), just without Bench this time.
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Paddle")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        self.assertIsNone(self._first_seen_for("Alpha", "Bench"))

        # Reintroduced later - correctly treated as new again, not as
        # if it had been there all along.
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        self.assertEqual(self._first_seen_for("Alpha", "Bench"), datetime.date.today().isoformat())


if __name__ == "__main__":
    unittest.main()
