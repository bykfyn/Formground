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

    # 2026-09-29: Swedish equivalents (campaign rebuilt Swedish-first) -
    # bare "möbler" used to fall through to the same null-category/
    # whole-catalog bug this whole mechanism was built to fix for
    # English, since it wasn't recognized as an umbrella word at all.

    def test_swedish_browse_word_overrides_null_category(self):
        llm_intent = {"category": None, "material": None}
        self.assertEqual(qe._resolve_intent("möbler", llm_intent), {"category": "furniture"})

    def test_swedish_browse_word_maps_to_canonical_english_value(self):
        # The stored category value must be the canonical English word
        # ("lighting"), not the literal matched Swedish string - that's
        # what _category_matches()/HYPERNYM_WORDS actually know how to
        # expand against real product category tags.
        resolved = qe._resolve_intent("belysning", {"category": None})
        self.assertEqual(resolved["category"], "lighting")

    def test_swedish_browse_word_inside_multi_word_query(self):
        llm_intent = {"category": None, "style_descriptors": ["oberoende"]}
        resolved = qe._resolve_intent("oberoende möbler tillverkare", llm_intent)
        self.assertEqual(resolved["category"], "furniture")

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

    # 2026-09-29: Swedish equivalents (campaign rebuilt Swedish-first) -
    # confirmed live "skandinaviskt matbord" returned the same count as
    # bare "matbord", i.e. no geography filter was ever applying.

    def test_swedish_scandinavian_adjective_sets_countries(self):
        llm_intent = {"category": "dining table", "style_descriptors": ["skandinaviskt"]}
        resolved = qe._resolve_intent("skandinaviskt matbord", llm_intent)
        self.assertEqual(resolved["category"], "dining table")
        self.assertEqual(set(resolved["countries"]), {"Sweden", "Denmark", "Norway"})
        self.assertEqual(resolved["style_descriptors"], [])

    def test_swedish_nordic_word_includes_finland(self):
        llm_intent = {"category": None, "style_descriptors": ["nordisk"]}
        resolved = qe._resolve_intent("nordisk belysning", llm_intent)
        self.assertEqual(set(resolved["countries"]), {"Sweden", "Denmark", "Norway", "Finland"})

    def test_swedish_single_country_demonym(self):
        llm_intent = {"category": "stol", "style_descriptors": ["svensk"]}
        resolved = qe._resolve_intent("svensk stol", llm_intent)
        self.assertEqual(resolved["countries"], ["Sweden"])
        self.assertEqual(resolved["style_descriptors"], [])

    def test_two_seater_word_form_sets_seat_count(self):
        llm_intent = {"category": "sofa", "style_descriptors": ["two seater"]}
        resolved = qe._resolve_intent("two seater sofa", llm_intent)
        self.assertEqual(resolved["seat_count"], 2)
        self.assertEqual(resolved["style_descriptors"], [])

    def test_three_seater_word_form_sets_seat_count(self):
        llm_intent = {"category": "sofa", "style_descriptors": ["three seater"]}
        resolved = qe._resolve_intent("three seater sofa", llm_intent)
        self.assertEqual(resolved["seat_count"], 3)
        self.assertEqual(resolved["style_descriptors"], [])

    def test_digit_hyphen_form_sets_seat_count(self):
        llm_intent = {"category": "sofa", "style_descriptors": ["3-seater"]}
        resolved = qe._resolve_intent("3-seater sofa", llm_intent)
        self.assertEqual(resolved["seat_count"], 3)
        self.assertEqual(resolved["style_descriptors"], [])

    def test_no_seat_count_word_leaves_intent_unchanged(self):
        llm_intent = {"category": "chair", "color": "red", "style_descriptors": []}
        self.assertEqual(qe._resolve_intent("a red chair", llm_intent), llm_intent)

    def test_seat_count_combines_with_geography_and_new_only(self):
        llm_intent = {"category": "sofa", "style_descriptors": ["new", "swedish", "two seater"]}
        resolved = qe._resolve_intent("new swedish two seater sofa", llm_intent)
        self.assertTrue(resolved["new_only"])
        self.assertEqual(resolved["countries"], ["Sweden"])
        self.assertEqual(resolved["seat_count"], 2)
        self.assertEqual(resolved["style_descriptors"], [])

    def test_llm_echoing_whole_query_as_category_gets_cleaned(self):
        # Confirmed live 2026-09-29: the real LLM classifier sometimes
        # returns the whole raw query as `category` instead of isolating
        # the real category word ("two seater sofa" verbatim, not
        # "sofa") - collapsed 56 real matches down to 3-4 since almost no
        # product's category tag matches that whole phrase.
        llm_intent = {"category": "two seater sofa", "style_descriptors": []}
        resolved = qe._resolve_intent("two seater sofa", llm_intent)
        self.assertEqual(resolved["category"], "sofa")
        self.assertEqual(resolved["seat_count"], 2)

    def test_llm_echoing_numeral_form_as_category_gets_cleaned(self):
        llm_intent = {"category": "2-seater sofa", "style_descriptors": []}
        resolved = qe._resolve_intent("2-seater sofa", llm_intent)
        self.assertEqual(resolved["category"], "sofa")
        self.assertEqual(resolved["seat_count"], 2)

    def test_clean_llm_category_is_left_untouched(self):
        # The common/correct case - the LLM already isolated "sofa"
        # cleanly - shouldn't be altered by the new cleanup step.
        llm_intent = {"category": "sofa", "style_descriptors": ["two seater"]}
        resolved = qe._resolve_intent("two seater sofa", llm_intent)
        self.assertEqual(resolved["category"], "sofa")

    def test_bare_seat_word_without_er_suffix_still_matches(self):
        # Confirmed live 2026-09-29: "two seat sofa" (no "-er") returned
        # only 4 results - the query-side pattern required "seater(s)"
        # and missed the bare "seat(s)" phrasing a real searcher used,
        # even though no product name itself ever uses bare "seat".
        self.assertEqual(qe._wanted_seat_count("two seat sofa"), 2)
        self.assertEqual(qe._wanted_seat_count("2 seat sofa"), 2)
        self.assertEqual(qe._wanted_seat_count("two seats sofa"), 2)

    def test_loveseat_does_not_false_positive(self):
        self.assertIsNone(qe._wanted_seat_count("a loveseat sofa"))
        self.assertIsNone(qe._wanted_seat_count("seat cushion"))

    # 2026-09-29: Swedish equivalents (campaign rebuilt Swedish-first) -
    # "tvåsits" ("two-seat") is the real Swedish furniture term; "tvåsits
    # soffa" returned 0 results before this despite 58 real matches for
    # the equivalent English query.

    def test_swedish_word_form_sets_seat_count(self):
        llm_intent = {"category": "soffa", "style_descriptors": ["tvåsits"]}
        resolved = qe._resolve_intent("tvåsits soffa", llm_intent)
        self.assertEqual(resolved["seat_count"], 2)
        self.assertEqual(resolved["style_descriptors"], [])

    def test_swedish_digit_hyphen_form_sets_seat_count(self):
        self.assertEqual(qe._wanted_seat_count("2-sits soffa"), 2)
        self.assertEqual(qe._wanted_seat_count("tre-sits soffa"), 3)
        self.assertEqual(qe._wanted_seat_count("3 sits soffa"), 3)

    def test_swedish_seat_count_does_not_affect_product_name_matching(self):
        # The reverse int->word lookup used to match PRODUCT names must
        # stay English regardless of the query's own language - this
        # catalog's product names are English even when the query isn't.
        self.assertTrue(qe._product_matches_seat_count("Collar 2-seater", 2))


class ProductMatchesSeatCountTests(unittest.TestCase):
    def test_digit_form_matches(self):
        self.assertTrue(qe._product_matches_seat_count("Mogens 2-Seater Sofa", 2))

    def test_word_form_matches(self):
        self.assertTrue(qe._product_matches_seat_count("Mogens Two Seater Sofa", 2))

    def test_wrong_count_does_not_match(self):
        self.assertFalse(qe._product_matches_seat_count("Mogens Three Seater Sofa", 2))

    def test_no_seat_count_in_name_does_not_match(self):
        self.assertFalse(qe._product_matches_seat_count("Mogens Lounge Chair", 2))


class PortableLampRecognitionTests(unittest.TestCase):
    """
    2026-09-29 (campaign rebuilt Swedish-first) - "uppladdningsbar
    bordslampa"/"portable table lamp" are real, high-value ad keywords.
    "Portable" is a real naming convention 28 real products across 6
    brands already use for a cordless/rechargeable lamp - no structured
    battery/power-source field exists, same "read it from the name"
    shape as seat count.
    """

    def test_english_word_sets_portable_only(self):
        llm_intent = {"category": "table lamp", "style_descriptors": ["portable"]}
        resolved = qe._resolve_intent("portable table lamp", llm_intent)
        self.assertTrue(resolved["portable_only"])
        self.assertEqual(resolved["style_descriptors"], [])

    def test_swedish_word_sets_portable_only(self):
        llm_intent = {"category": "bordslampa", "style_descriptors": ["uppladdningsbar"]}
        resolved = qe._resolve_intent("uppladdningsbar bordslampa", llm_intent)
        self.assertTrue(resolved["portable_only"])
        self.assertEqual(resolved["style_descriptors"], [])

    def test_other_swedish_synonyms_also_recognized(self):
        for word in ("portabel", "sladdlös", "batteridriven"):
            with self.subTest(word=word):
                self.assertTrue(qe._wants_portable(f"{word} bordslampa"))

    def test_no_portable_word_leaves_intent_unchanged(self):
        llm_intent = {"category": "table lamp", "color": "black", "style_descriptors": []}
        self.assertEqual(qe._resolve_intent("black table lamp", llm_intent), llm_intent)

    def test_portable_combines_with_category(self):
        llm_intent = {"category": "table lamp", "style_descriptors": ["cordless"]}
        resolved = qe._resolve_intent("cordless table lamp", llm_intent)
        self.assertEqual(resolved["category"], "table lamp")
        self.assertTrue(resolved["portable_only"])


class ProductIsPortableTests(unittest.TestCase):
    def test_portable_in_name_matches(self):
        self.assertTrue(qe._product_is_portable("Margin Portable Table Lamp"))
        self.assertTrue(qe._product_is_portable("Beetle Portable Lamp"))

    def test_no_portable_in_name_does_not_match(self):
        # A real, known cordless lamp whose name doesn't say "portable" -
        # confirmed limitation, not a false negative bug: this recognizer
        # only catches the naming convention, not every cordless lamp.
        self.assertFalse(qe._product_is_portable("Alumina Multi-Use Lamp in Sapphire"))
        self.assertFalse(qe._product_is_portable("Mogens Lounge Chair"))


class IsModularComponentTests(unittest.TestCase):
    def test_numbered_module_matches(self):
        self.assertTrue(qe._is_modular_component("Shore Dining Curved End Left, Plinth, Module 41"))

    def test_sized_module_matches(self):
        self.assertTrue(qe._is_modular_component("Livello Middle Module 95cm"))

    def test_coded_module_matches(self):
        self.assertTrue(qe._is_modular_component("Catena Sofa Connect Corner Module L200"))

    def test_configuration_does_not_match(self):
        self.assertFalse(qe._is_modular_component("Shore Modular Sofa, Configuration 1"))

    def test_bare_module_word_does_not_match(self):
        self.assertFalse(qe._is_modular_component("Elogio Sofa Module"))

    def test_ordinary_name_does_not_match(self):
        self.assertFalse(qe._is_modular_component("Bolide Sofa"))


class IsProtectiveCoverTests(unittest.TestCase):
    def test_protection_cover_matches(self):
        self.assertTrue(qe._is_protective_cover("protection cover 2 seater rudolph"))

    def test_ordinary_name_does_not_match(self):
        self.assertFalse(qe._is_protective_cover("Bolide Sofa"))

    def test_unrelated_cover_word_does_not_match(self):
        # Only the literal "protection cover" phrase is excluded - a
        # real product legitimately named with just "cover" (e.g. a
        # standalone seat cover product) isn't affected.
        self.assertFalse(qe._is_protective_cover("Seat Cover"))


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


class AgentProductShapeTests(unittest.TestCase):
    """/agent/search's object shape: an Offer only with price AND currency,
    and priceStatus explaining the absence otherwise."""

    BASE = {
        "product_name": "Test Lamp", "brand": "SomeBrand", "brand_url": "https://b.example",
        "product_url": "https://b.example/p", "category": "Table Lamp", "link_dead": 0,
        "price": None, "currency": None, "image_url": "https://b.example/i.jpg",
        "material_options": "[]", "designer": None,
    }

    def shape(self, **over):
        return qe.shape_agent_product({**self.BASE, **over})

    def test_listed_has_offer_and_currency(self):
        out = self.shape(price=599.0, currency="EUR")
        self.assertEqual(out["priceStatus"], "listed")
        self.assertEqual(out["offers"], {"@type": "Offer", "price": "599.00", "priceCurrency": "EUR"})

    def test_price_without_currency_is_not_listed(self):
        out = self.shape(price=599.0, currency=None)
        self.assertEqual(out["priceStatus"], "unknown")
        self.assertNotIn("offers", out)

    def test_brand_pricing_status_applies_without_price(self):
        qe.BRAND_PRICING["POABrand"] = "on_request"
        try:
            out = self.shape(brand="POABrand")
            self.assertEqual(out["priceStatus"], "on_request")
            self.assertNotIn("offers", out)
            # a product-level price still wins over the brand-level status
            self.assertEqual(self.shape(brand="POABrand", price=10.0, currency="SEK")["priceStatus"], "listed")
        finally:
            del qe.BRAND_PRICING["POABrand"]

    def test_unknown_brand_without_price_is_unknown(self):
        self.assertEqual(self.shape()["priceStatus"], "unknown")

    def test_optional_fields_omitted_not_null(self):
        out = self.shape()
        for key in ("material", "creator", "makerCountry"):
            self.assertNotIn(key, out)
        out = self.shape(material_options='["Oak", "Brass"]', designer="A Designer")
        self.assertEqual(out["material"], ["Oak", "Brass"])
        self.assertEqual(out["creator"], {"@type": "Person", "name": "A Designer"})

    def test_dead_link_falls_back_to_brand_homepage(self):
        self.assertEqual(self.shape(link_dead=1)["url"], "https://b.example")

    def test_seeded_brands_json_values_are_valid(self):
        self.assertEqual(qe.BRAND_PRICING.get("Galerie Kreo"), "on_request")
        self.assertTrue(set(qe.BRAND_PRICING.values()) <= {"on_request", "dealer_priced"})


class BrandStatusTests(unittest.TestCase):
    """Sheerd listing state: "scraped" (default) or "approved" - only the
    exact value "approved" promotes; nothing is approved yet."""

    def test_default_is_scraped(self):
        self.assertEqual(qe.brand_status("A Brand With No Status"), "scraped")

    def test_values_in_brands_json_are_valid_and_nothing_is_approved_yet(self):
        import json
        brands = json.loads(qe.BRANDS_PATH.read_text())
        for b in brands:
            if "status" in b:
                self.assertIn(b["status"], qe.BRAND_STATUS_VALUES, b["name"])
        self.assertEqual(qe.BRAND_STATUS, {})  # update when the first brand is approved

    def test_agent_payload_does_not_expose_status_yet(self):
        out = qe.shape_agent_product({
            "product_name": "P", "brand": "B", "brand_url": "u", "product_url": "u", "category": "",
            "link_dead": 0, "price": None, "currency": None,
        })
        self.assertNotIn("status", out)


if __name__ == "__main__":
    unittest.main()


class SearchSpeedTests(unittest.TestCase):
    """Guards for the 2026-10-04 search-speed work: the optimised paths must
    return exactly what the original logic did, and a repeated query must not
    call the LLM again."""

    def test_repeat_query_skips_the_llm_and_ignores_case_and_spacing(self):
        calls = []

        def fake(system_prompt, raw_query):
            calls.append(raw_query)
            return '{"category": "zzz test", "material": null, "style_descriptors": [], "color": null, "location": null}'

        original = qe.LLM_CALLERS[qe.LLM_PROVIDER]
        qe.LLM_CALLERS[qe.LLM_PROVIDER] = fake
        try:
            a = qe.translate_query("Zzz   Test Thing")
            b = qe.translate_query("zzz test thing")
        finally:
            qe.LLM_CALLERS[qe.LLM_PROVIDER] = original
            qe._INTENT_CACHE.pop(qe._normalise_query("Zzz Test Thing"), None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(a, b)

    def test_cached_intent_is_a_copy(self):
        qe._intent_cache_put("zzz copy check", {"category": "chair", "style_descriptors": ["a"]})
        got = qe._intent_cache_get("zzz copy check")
        got["style_descriptors"].append("mutated")
        self.assertEqual(qe._intent_cache_get("zzz copy check")["style_descriptors"], ["a"])
        qe._INTENT_CACHE.pop("zzz copy check", None)

    def test_filter_by_name_equals_the_original_per_row_regex_logic(self):
        import json
        import re

        def reference(raw_query):
            stripped = raw_query.strip()
            out = []
            for row in qe._all_product_rows():
                if not row["image_url"] or row["brand"] in qe.HIDDEN_BRANDS:
                    continue
                name = row["product_name"]
                name_in_query = (
                    name.strip().lower() not in qe.GENERIC_PRODUCT_NAMES
                    and re.search(rf"\b{re.escape(name)}\b", raw_query, re.IGNORECASE)
                )
                query_in_name = len(stripped) >= 3 and re.search(rf"\b{re.escape(stripped)}\b", name, re.IGNORECASE)
                if name_in_query or query_in_name:
                    out.append(row["id"])
            return out

        for q in ("Boyd", "vaso", "table lamp", "pendant lamp Ø60", "über lamp", "Kantarell Pendant Lamp Ø60 black"):
            self.assertEqual([p["id"] for p in qe.filter_by_name(q)], reference(q), q)

    def test_shared_rows_are_not_mutated_by_a_search(self):
        qe.filter_products({"category": "table lamp"})
        qe.filter_by_name("lamp")
        sample = qe._all_product_rows()[0]
        self.assertIsInstance(sample["material_options"], str)


class DiscoverHousesTests(unittest.TestCase):
    """"Surprise me" includes a few houses (2026-10-04): 1 to 3 per browse, different practices, inside the cap."""

    def test_every_browse_has_one_to_three_houses_from_different_practices(self):
        for _ in range(15):
            results = qe.discover()
            houses = [r for r in results if r.get("type") == "house"]
            self.assertTrue(1 <= len(houses) <= qe.DISCOVER_HOUSES_MAX, len(houses))
            self.assertEqual(len({h["brand"] for h in houses}), len(houses))      # one house per practice
            self.assertLessEqual(len(results), qe.DISCOVER_TOTAL_CAP)
            for h in houses:
                self.assertTrue(h["image_url"] and h["product_url"] and h["product_name"])
                self.assertFalse(h["link_dead"])

    def test_houses_are_not_offered_under_a_maker_tier_chip(self):
        for tier in ("independent", "established"):
            self.assertFalse([r for r in qe.discover(tier=tier) if r.get("type") == "house"], tier)

    def test_houses_do_not_crowd_out_the_products(self):
        for _ in range(10):
            results = qe.discover()
            products = [r for r in results if r.get("type") != "house"]
            self.assertGreaterEqual(len(products), qe.DISCOVER_TOTAL_CAP - qe.DISCOVER_HOUSES_MAX)


class UnrecognisedQueryTests(unittest.TestCase):
    """2026-10-05: a query that set no filter returned the WHOLE catalog
    ("28,026 results for 'HAY'"). Brand names are now recognised, a query
    nothing recognises returns nothing, and a failed invented category falls
    back to its head noun. translate_query (the LLM) is stubbed."""

    def setUp(self):
        self._orig = qe.translate_query
        qe.translate_query = lambda q: {}

    def tearDown(self):
        qe.translate_query = self._orig

    def test_brand_name_returns_that_makers_work(self):
        for q in ("HAY", "hay", "Ligne Roset", "kallemo", "b&b italia", "Piet Hein Eek"):
            r = qe.search_full(q)
            self.assertGreater(r["total_matches"], 0, q)
            self.assertEqual(r["total_brands"], 1, q)
            self.assertTrue(r["brand_links"], q)

    def test_gibberish_matches_nothing(self):
        r = qe.search_full("xyzzyqwerty")
        self.assertEqual((r["total_matches"], r["results"]), (0, []))

    def test_blank_query_is_empty_not_an_error(self):
        for q in ("", "   "):
            self.assertEqual(qe.search_full(q)["total_matches"], 0)

    def test_ambiguous_brand_word_inside_a_description_is_not_a_brand(self):
        self.assertEqual(qe.detect_brands("oak grain table"), [])
        self.assertEqual(qe.detect_brands("grain"), ["Grain"])

    def test_pinch_pot_is_not_the_pinch_brand(self):
        # "Another Country Pottery Series Pinch Pot" must stay findable
        self.assertEqual(qe.detect_brands("pinch pot"), [])

    def test_brand_inside_longer_query_is_found(self):
        self.assertEqual(qe.detect_brands("serax vase"), ["Serax"])

    def test_a_brand_is_found_by_its_name_without_a_trailing_generic_word(self):
        # "Rieul Lighting" / "Tlachï Design" were found only by the full name (2026-10-09)
        self.assertEqual(qe.detect_brands("rieul"), ["Rieul Lighting"])
        self.assertEqual(qe.detect_brands("Tlachi"), ["Tlachï Design"])
        self.assertEqual(qe.detect_brands("tlachi chair"), ["Tlachï Design"])
        self.assertEqual(qe.detect_brands("rieul lighting"), ["Rieul Lighting"])

    def test_short_names_that_are_ordinary_words_only_match_on_their_own(self):
        self.assertEqual(qe.detect_brands("lemon"), ["Lemon Furniture"])
        self.assertEqual(qe.detect_brands("lemon squeezer"), [])
        self.assertEqual(qe.detect_brands("oven glove"), [])
        self.assertEqual(qe.detect_brands("kann"), ["Kann Design"])

    def test_a_brand_that_starts_with_a_generic_word_gets_no_short_name(self):
        self.assertEqual(qe.detect_brands("objects for"), [])
        self.assertNotIn("studio gameiro", [b.lower() for b in qe.detect_brands("studio")])

    def test_short_names_never_collide_with_a_real_brand_name(self):
        folds = qe._brand_folds()
        full = {qe._fold(b) for b in {r["brand"] for r in qe._all_product_rows()} if b not in qe.HIDDEN_BRANDS}
        for fold, brand in folds.items():
            if fold not in full:                          # it is a short name
                self.assertTrue(qe._fold(brand).startswith(fold + " "), (fold, brand))

    def test_invented_compound_category_falls_back_to_head_noun(self):
        qe.translate_query = lambda q: {"category": "bedroom lamp"}
        r = qe.search_full("lamp for bedroom")
        self.assertGreater(r["total_matches"], 0)
        self.assertEqual(r["intent"]["category"], "lamp")

    def test_brand_link_slugs_match_the_scraper_slugify(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))
        from generate_brand_pages import slugify
        for brand in qe._brand_folds().values():
            self.assertEqual(qe.brand_links({"brands": [brand]})[0]["slug"], slugify(brand), brand)
