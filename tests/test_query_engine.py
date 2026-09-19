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


class FilterHousesTests(unittest.TestCase):
    """
    Covers the backend search merge (2026-09-19): a house is only
    ever surfaced when the extracted category is house-like, never
    just because a query happened to name a place - and once
    triggered, location narrows on real free-text location/region
    strings, not a geocoded match. Synthetic house records, not real
    data/houses.json, so these stay correct regardless of what's
    actually been scraped.
    """

    def _houses(self):
        return [
            {"name": "H House", "firm": "Firm A", "location": "Malexander, Sweden",
             "region": "Other Sweden", "year": "2012", "image": "a.jpg", "url": "https://a.example/h-house"},
            {"name": "Villa Eslami", "firm": "Firm B", "location": "Stockholm",
             "region": "Stockholm", "year": "2009", "image": "b.jpg", "url": "https://b.example/villa-eslami"},
            {"name": "Serpiente", "firm": "Firm C", "location": "Benalmádena, Spain",
             "region": "International", "year": None, "image": "c.jpg", "url": "https://c.example/serpiente"},
        ]

    def test_non_house_category_returns_nothing(self):
        intent = {"category": "chair", "location": "Stockholm"}
        self.assertEqual(qe.filter_houses(intent, houses=self._houses()), [])

    def test_house_category_with_no_location_returns_all(self):
        intent = {"category": "house", "location": None}
        result = qe.filter_houses(intent, houses=self._houses())
        self.assertEqual(len(result), 3)

    def test_location_narrows_to_matching_region(self):
        intent = {"category": "house", "location": "Stockholm"}
        result = qe.filter_houses(intent, houses=self._houses())
        self.assertEqual([h["name"] for h in result], ["Villa Eslami"])

    def test_location_match_is_case_insensitive_substring(self):
        intent = {"category": "house", "location": "sweden"}
        result = qe.filter_houses(intent, houses=self._houses())
        names = {h["name"] for h in result}
        # Matches both the literal "Sweden" in H House's location and
        # Serpiente's "Spain" must NOT be swept in just for containing
        # a similar-looking substring.
        self.assertEqual(names, {"H House"})

    def test_villa_synonym_also_triggers_house_search(self):
        intent = {"category": "villa", "location": None}
        result = qe.filter_houses(intent, houses=self._houses())
        self.assertEqual(len(result), 3)

    def test_normalized_house_aliases_brand_to_firm(self):
        # cap_per_brand() only ever reads p["brand"] - this is the
        # whole reason a house can share that fairness cap with
        # products unmodified.
        intent = {"category": "house", "location": None}
        result = qe.filter_houses(intent, houses=self._houses())
        self.assertEqual({h["brand"] for h in result}, {"Firm A", "Firm B", "Firm C"})

    def test_name_match_finds_house_regardless_of_category(self):
        result = qe.filter_houses_by_name("tell me about H House", houses=self._houses())
        self.assertEqual([h["name"] for h in result], ["H House"])

    def test_name_match_is_word_bounded(self):
        # "H House" shouldn't match a query that only shares a
        # substring, not the real whole name.
        result = qe.filter_houses_by_name("a house somewhere", houses=self._houses())
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
