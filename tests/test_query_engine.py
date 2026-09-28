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

    def test_hypernym_ceramics_matches_specific_tag(self):
        self.assertTrue(qe._category_matches("Vase", "ceramics"))

    def test_hypernym_ceramics_does_not_match_unrelated_tag(self):
        self.assertFalse(qe._category_matches("Chair", "ceramics"))

    def test_objects_matches_tag_outside_named_categories(self):
        # "Objects" isn't a real tag anyone uses - it's this site's own
        # catch-all, matched by exclusion (see generate_brand_pages.py's
        # DEFAULT_UMBRELLA). A tag that isn't furniture/lighting should
        # match it.
        self.assertTrue(qe._category_matches("Accessories", "objects"))

    def test_objects_includes_ceramics(self):
        # The homepage's Objects tile folded Ceramics into it 2026-09-20
        # (see project memory) - the Objects catch-all has to actually
        # include real ceramics products for that merge to be real, not
        # just a UI label change contradicted by the search results.
        self.assertTrue(qe._category_matches("Vase", "objects"))

    def test_objects_does_not_match_named_category_tag(self):
        self.assertFalse(qe._category_matches("Chair", "objects"))
        self.assertFalse(qe._category_matches("Sconce", "objects"))


class ResolveIntentTests(unittest.TestCase):
    """
    Covers the 2026-09-20 fix for the homepage's category tiles, which
    send a bare umbrella word ("furniture", "ceramics", ...) as the whole
    query. Confirmed live: the LLM often leaves category null for these
    (too generic to pick a specific object type), which skipped the
    category filter entirely and returned the whole unfiltered catalog;
    for "ceramics" specifically, the LLM sometimes echoed the same word
    into material too, which - correctly ANDed with category for a real
    query like "black chair" - cut real results down to a handful for
    this single-word one instead.
    """

    def test_browse_word_overrides_null_category(self):
        llm_intent = {"category": None, "material": None}
        self.assertEqual(qe._resolve_intent("furniture", llm_intent), {"category": "furniture"})

    def test_browse_word_overrides_redundant_material(self):
        llm_intent = {"category": "ceramics", "material": "ceramic"}
        self.assertEqual(qe._resolve_intent("ceramics", llm_intent), {"category": "ceramics"})

    def test_non_browse_query_keeps_llm_intent(self):
        llm_intent = {"category": "chair", "material": "black"}
        self.assertEqual(qe._resolve_intent("black chair", llm_intent), llm_intent)

    # 2026-09-28 fix: the same null-category failure the bare-word case
    # above works around also happens for a real multi-word query built
    # around one of these umbrella words - confirmed live via the actual
    # /search API: "furniture" alone and "handmade furniture" correctly
    # resolve category="furniture", but "furniture makers", "Scandinavian
    # furniture", and "independent furniture makers" all came back
    # category=null, which meant filter_products() skipped its category
    # filter and returned the whole unfiltered catalog (~25,645 products)
    # instead of real furniture.

    def test_browse_word_inside_multi_word_query_overrides_null_category(self):
        # "Scandinavian" used to just sit in style_descriptors doing
        # nothing useful (no product name literally contains it) - as of
        # the 2026-09-28 geography fix it's now also recognized as a
        # real country filter, so it correctly moves to `countries`
        # instead of staying as inert style text. See
        # GeographyRecognitionTests below for that fix's own coverage.
        llm_intent = {"category": None, "style_descriptors": ["Scandinavian"]}
        resolved = qe._resolve_intent("Scandinavian furniture design", llm_intent)
        self.assertEqual(resolved["category"], "furniture")
        self.assertEqual(set(resolved["countries"]), {"Sweden", "Denmark", "Norway"})
        self.assertEqual(resolved["style_descriptors"], [])

    def test_browse_word_inside_multi_word_query_preserves_other_fields(self):
        llm_intent = {"category": None, "style_descriptors": ["independent"]}
        resolved = qe._resolve_intent("independent furniture makers", llm_intent)
        self.assertEqual(resolved, {"category": "furniture", "style_descriptors": ["independent"]})

    def test_real_category_wins_over_multi_word_browse_fallback(self):
        # The LLM DID find a specific category here - the broader
        # umbrella-word fallback must never override a real one.
        llm_intent = {"category": "coffee table", "material": None}
        self.assertEqual(
            qe._resolve_intent("modern furniture coffee table", llm_intent), llm_intent
        )

    def test_browse_word_substring_is_not_matched(self):
        # "object" must not match inside "objection" - word-boundary only.
        llm_intent = {"category": None}
        self.assertEqual(qe._resolve_intent("objection handling course", llm_intent), llm_intent)

    def test_no_browse_word_present_keeps_null_category(self):
        llm_intent = {"category": None, "style_descriptors": ["sculptural"]}
        self.assertEqual(
            qe._resolve_intent("something warm-toned and sculptural", llm_intent), llm_intent
        )

    # 2026-09-28: "new"/"new arrivals" recognition, so a query like "new
    # chairs" behaves like the dedicated New Arrivals page instead of
    # falling through to a literal text-match against product names.

    def test_bare_new_sets_new_only_flag(self):
        llm_intent = {"category": None, "style_descriptors": ["new"]}
        resolved = qe._resolve_intent("new", llm_intent)
        self.assertTrue(resolved["new_only"])
        self.assertEqual(resolved["style_descriptors"], [])

    def test_new_combined_with_category_sets_both(self):
        llm_intent = {"category": "chair", "style_descriptors": ["new"]}
        resolved = qe._resolve_intent("new chairs", llm_intent)
        self.assertEqual(resolved["category"], "chair")
        self.assertTrue(resolved["new_only"])
        self.assertEqual(resolved["style_descriptors"], [])

    def test_new_arrival_phrases_also_recognized(self):
        for query in ("new arrivals", "newly added", "recently added"):
            with self.subTest(query=query):
                resolved = qe._resolve_intent(query, {"category": None, "style_descriptors": []})
                self.assertTrue(resolved["new_only"])

    def test_renew_does_not_trigger_new_only(self):
        # "new" must be a whole word - "renew" is unrelated.
        llm_intent = {"category": "chair", "style_descriptors": ["renewed"]}
        resolved = qe._resolve_intent("renew my chair", llm_intent)
        self.assertNotIn("new_only", resolved)

    def test_new_only_preserves_other_style_descriptors(self):
        llm_intent = {"category": "chair", "style_descriptors": ["new", "sculptural"]}
        resolved = qe._resolve_intent("new sculptural chair", llm_intent)
        self.assertTrue(resolved["new_only"])
        self.assertEqual(resolved["style_descriptors"], ["sculptural"])

    # 2026-09-28: geography recognition, so "Scandinavian dining table"
    # actually filters by real brand country instead of silently doing
    # nothing (product search never used `location` at all before this -
    # only house search did).

    def test_scandinavian_region_word_sets_countries(self):
        llm_intent = {"category": "dining table", "style_descriptors": ["scandinavian"]}
        resolved = qe._resolve_intent("scandinavian dining table", llm_intent)
        self.assertEqual(resolved["category"], "dining table")
        self.assertEqual(set(resolved["countries"]), {"Sweden", "Denmark", "Norway"})
        self.assertEqual(resolved["style_descriptors"], [])

    def test_nordic_includes_finland(self):
        llm_intent = {"category": None, "style_descriptors": ["nordic"]}
        resolved = qe._resolve_intent("nordic lighting", llm_intent)
        self.assertEqual(set(resolved["countries"]), {"Sweden", "Denmark", "Norway", "Finland"})

    def test_single_country_demonym(self):
        llm_intent = {"category": "chair", "style_descriptors": ["swedish"]}
        resolved = qe._resolve_intent("swedish chair", llm_intent)
        self.assertEqual(resolved["countries"], ["Sweden"])
        self.assertEqual(resolved["style_descriptors"], [])

    def test_llm_location_field_also_recognized(self):
        # The simple case - LLM already extracts a bare country name
        # into `location` - should still resolve without needing the
        # word to also appear literally in the query text.
        llm_intent = {"category": "chair", "location": "Sweden"}
        resolved = qe._resolve_intent("a chair from Sweden", llm_intent)
        self.assertEqual(resolved["countries"], ["Sweden"])

    def test_no_geography_word_leaves_intent_unchanged(self):
        llm_intent = {"category": "chair", "color": "red", "style_descriptors": []}
        self.assertEqual(qe._resolve_intent("a red chair", llm_intent), llm_intent)

    def test_geography_combines_with_new_only(self):
        llm_intent = {"category": "lamp", "style_descriptors": ["new", "danish"]}
        resolved = qe._resolve_intent("new danish lamp", llm_intent)
        self.assertTrue(resolved["new_only"])
        self.assertEqual(resolved["countries"], ["Denmark"])
        self.assertEqual(resolved["style_descriptors"], [])


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
