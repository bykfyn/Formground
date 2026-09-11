"""
Regression tests for backend/query_engine.py.

WHY THESE, SPECIFICALLY:
  Not a general test suite - scope is deliberately narrow, per the
  project's own "small regression-test suite" decision (see project
  memory): the exact spots that have already broken silently once,
  where a future change could quietly break them again without anyone
  noticing until a real search looked wrong. Individual brand
  extractors are NOT covered here - those are network-dependent and
  better caught by spot-checking real output, per that same decision.

RUNNING THESE:
    python3 -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import query_engine as qe  # noqa: E402


class CategoryMatchesTests(unittest.TestCase):
    """
    Covers the real bug from 2026-09-08: "chunky table" was surfacing
    lamps and a carafe because a plain substring match treated "Table
    Lamps"/"Table and Glassware"/"Phone & Tablet Sleeves" as if they
    were tables. _category_matches() fixed this with a word-boundary,
    tag-must-end-with-the-word rule - these tests exist so a future
    change to that logic can't reintroduce the same failure mode
    without a test going red.
    """

    def test_bare_word_matches_itself(self):
        self.assertTrue(qe._category_matches("Table", "table"))

    def test_plural_tag_matches_singular_query(self):
        self.assertTrue(qe._category_matches("Tables", "table"))

    def test_singular_tag_matches_plural_query(self):
        # The category-chip case that motivated trying both forms -
        # "tables" (plural, from a chip) must still match a brand
        # whose own tag is the bare singular "Table".
        self.assertTrue(qe._category_matches("Table", "tables"))

    def test_modifier_prefix_matches(self):
        self.assertTrue(qe._category_matches("Coffee Table", "table"))

    def test_table_lamps_does_not_match_table(self):
        self.assertFalse(qe._category_matches("Table Lamps", "table"))

    def test_tableware_does_not_match_table(self):
        self.assertFalse(qe._category_matches("Table and Glassware", "table"))

    def test_tablet_sleeves_does_not_match_table(self):
        self.assertFalse(qe._category_matches("Phone & Tablet Sleeves", "table"))

    def test_compound_query_still_matches_real_category(self):
        # "brass table lamp" style queries pass the *whole* wanted
        # phrase through - this must still work once it's a real,
        # matching compound category, not just avoid false positives.
        self.assertTrue(qe._category_matches("Table Lamps", "table lamp"))

    def test_hypernym_lighting_matches_specific_tag(self):
        self.assertTrue(qe._category_matches("Sconce", "lighting"))

    def test_hypernym_furniture_does_not_match_unrelated_tag(self):
        self.assertFalse(qe._category_matches("Vase", "furniture"))


class CapPerBrandTests(unittest.TestCase):
    """
    Covers "brand is the minimum unit of inclusion" - a brand with a
    huge catalog must not be able to crowd out a brand with only a
    couple of matching products.
    """

    def _products(self, brand, count):
        return [{"brand": brand, "id": i} for i in range(count)]

    def test_large_brand_gets_capped(self):
        products = self._products("BigBrand", 50)
        result = qe.cap_per_brand(products, max_per_brand=3)
        self.assertEqual(len(result), 3)

    def test_small_brand_keeps_everything(self):
        products = self._products("SmallBrand", 2)
        result = qe.cap_per_brand(products, max_per_brand=3)
        self.assertEqual(len(result), 2)

    def test_small_brand_not_crowded_out_by_large_one(self):
        products = self._products("BigBrand", 50) + self._products("SmallBrand", 1)
        result = qe.cap_per_brand(products, max_per_brand=3)
        brands_present = {p["brand"] for p in result}
        self.assertIn("SmallBrand", brands_present)
        self.assertEqual(sum(1 for p in result if p["brand"] == "BigBrand"), 3)


if __name__ == "__main__":
    unittest.main()
