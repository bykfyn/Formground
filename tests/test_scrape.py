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

    def test_brands_first_scrape_leaves_first_seen_null(self):
        # A brand's very first scrape has no prior rows to carry
        # first_seen forward from - confirmed live 2026-09-28: 91 brands
        # onboarded the same day each had their entire back-catalog
        # stamped "new today," making an established brand's years-old
        # catalog look like a mass product launch. The real add-date for
        # a freshly-onboarded brand's existing catalog is genuinely
        # unknown, same as any other pre-existing product with an
        # unknown real date - it must stay NULL, not get "new today"
        # just because Formground happened to start tracking it now.
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        self.assertIsNone(self._first_seen_for("Alpha", "Bench"))

    def test_new_product_on_an_already_tracked_brand_is_stamped_with_todays_date(self):
        # The genuine "new arrival" case: Alpha is already a known brand
        # (scraped once before with just "Bench") - a second run adding
        # "Stool" for the first time is a real new arrival and should be
        # stamped today, unlike the brand's own first scrape above.
        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()

        scrape.EXTRACTORS = {
            "Alpha": lambda brand: [self._product("Alpha", "Bench"), self._product("Alpha", "Stool")],
            "Beta": lambda brand: [self._product("Beta", "Vase")],
        }
        scrape.run()
        today = datetime.date.today().isoformat()
        self.assertEqual(self._first_seen_for("Alpha", "Stool"), today)
        self.assertIsNone(self._first_seen_for("Alpha", "Bench"))

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


class PriceFromPageTests(unittest.TestCase):
    """The shared page-price step (scrape._price_from_page_html)."""

    def test_jsonld_offer_gives_price_and_currency(self):
        page = '<script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer","price":"899.00","priceCurrency":"EUR"}}</script>'
        self.assertEqual(scrape._price_from_page_html("Gubi", page), (899.0, "EUR"))

    def test_jsonld_without_currency_gives_nothing(self):
        page = '<script type="application/ld+json">{"offers":{"price":"899.00"}}</script>'
        self.assertEqual(scrape._price_from_page_html("Gubi", page), (None, None))

    def test_visible_price_needs_two_occurrences(self):
        self.assertEqual(scrape._price_from_page_html("Muhly", "<p>$295</p>"), (None, None))
        self.assertEqual(scrape._price_from_page_html("Muhly", "<p>$295</p><b>$295.00</b>"), (295.0, "USD"))

    def test_danny_kaplan_takes_the_first_price_before_related_products(self):
        page = "<h1>Agnes Lamp</h1> $2,200 USD <h2>Related Products</h2> Astor $2,200 USD Globe $1,950 USD"
        self.assertEqual(scrape._price_from_page_html("Danny Kaplan Studio", page), (2200.0, "USD"))
        one_off = "<h1>Facet Dining Chair</h1> $3,000 USD <h2>Related Products</h2> Brion $6,500 USD"
        self.assertEqual(scrape._price_from_page_html("Danny Kaplan Studio", one_off), (3000.0, "USD"))

    def test_price_split_across_sibling_elements_is_still_read(self):
        # the live markup: number and currency in separate elements
        page = '<h1>Agnes Lamp</h1><span class="p">$2,200</span> <span>USD</span><h2>Related</h2><span>$1,950</span><span>USD</span>'
        self.assertEqual(scrape._price_from_page_html("Danny Kaplan Studio", page), (2200.0, "USD"))

    def test_coco_flip_uses_structured_offer_only_never_from_prices_in_text(self):
        text_only = "<p>Chorus Wall Light From $715 Explore</p>"
        self.assertEqual(scrape._price_from_page_html("Coco Flip", text_only), (None, None))
        offer = '<script type="application/ld+json">{"offers":{"price":"2750","priceCurrency":"AUD"}}</script>'
        self.assertEqual(scrape._price_from_page_html("Coco Flip", offer), (2750.0, "AUD"))

    def test_visible_zero_placeholder_ignored(self):
        page = "<p>$4,925.00</p><p>$4,925.00</p><p>$0.00</p><p>$0.00</p>"
        self.assertEqual(scrape._price_from_page_html("Workstead", page), (4925.0, "USD"))

    def test_price_formats(self):
        self.assertEqual(scrape._parse_price("1.234,50"), 1234.5)
        self.assertEqual(scrape._parse_price("1,234.50"), 1234.5)
        self.assertEqual(scrape._parse_price("DKK\xa03,995"), 3995.0)


class TidyCategoryTests(unittest.TestCase):
    def test_strips_trailing_separators_only(self):
        self.assertEqual(scrape._tidy_category("Chair/"), "Chair")
        self.assertEqual(scrape._tidy_category("Chair/ "), "Chair")
        self.assertEqual(scrape._tidy_category("Sofa, Armchair"), "Sofa, Armchair")
        self.assertEqual(scrape._tidy_category("Coat/Hat Stand"), "Coat/Hat Stand")
        self.assertEqual(scrape._tidy_category(None), "")


class StockistLeadsParseTests(unittest.TestCase):
    """scrape_stockist_leads.parse_magis_stores on a minimal copy of Magis's real markup."""

    HTML = """
    <div class="marker" data-icon="retailer" data-lat="40.83" data-lng="17.36"><h4 class="title">Baco Arredamenti</h4>
      <p class="address">Via Santa Margherita, 38<br/>72015 Fasano - Italy<br/>T 080-4426949<br/>
      <a href="mailto:info@baco.it">Email</a><br/><a href="https://www.google.com/maps/dir/">Directions</a></p></div>
    <div class="marker" data-icon="headquarter" data-lat="45.70" data-lng="12.69"><h4 class="title">Magis Headquarter</h4>
      <p class="address">Via Triestina Accesso E - Z.I, Via Tezze, 30020 Torre di Mosto VE, Italy</p></div>
    <div class="marker" data-icon="retailer" data-lat="39.9" data-lng="32.8"><h4 class="title">Mozaik</h4>
      <p class="address">Cinnah Cad. 66<br/>Ankara - Turchia</p></div>
    <div class="marker" data-icon="agente" data-lat="1" data-lng="2"><h4 class="title">Magis France</h4></div>
    """

    def test_parses_fields_and_countries(self):
        import scrape_stockist_leads as sl
        rows = {r["name"]: r for r in sl.parse_magis_stores(self.HTML)}
        self.assertEqual(rows["Baco Arredamenti"]["country"], "Italy")
        self.assertEqual(rows["Baco Arredamenti"]["phone"], "080-4426949")
        self.assertEqual(rows["Baco Arredamenti"]["email"], "info@baco.it")
        self.assertEqual(rows["Magis Headquarter"]["country"], "Italy")   # dash inside the street must not win
        self.assertEqual(rows["Mozaik"]["country"], "Turkey")             # "Turchia" normalised
        self.assertIsNone(rows["Magis France"]["address"])                # sales agents carry no address


if __name__ == "__main__":
    unittest.main()


class ChairSubtypeTests(unittest.TestCase):
    """_refine_chair_subtype (2026-10-04): a chair whose only tag is generic gets a sub-type from its NAME."""

    def test_the_name_decides_and_the_brand_tags_are_kept(self):
        f = scrape._refine_chair_subtype
        self.assertEqual(f("ELLIOT DINING CHAIR", "chair"), "dining chair, chair")
        self.assertEqual(f("Era Armchair", "Chair"), "armchair, Chair")
        self.assertEqual(f("Slipper Chair", "chair"), "lounge chair, chair")
        self.assertEqual(f("Task chair 3", "chair"), "office chair, chair")
        self.assertEqual(f("Folding Flat Chair | Ash", "chairs"), "folding chair, chairs")
        self.assertEqual(f("Chaise de jardin PANORAMA", "chair"), "garden chair, chair")
        self.assertEqual(f("Arno Club Chair", "Chair, sillas"), "lounge chair, Chair, sillas")

    def test_no_change_when_there_is_nothing_to_read_or_a_specific_tag_exists(self):
        f = scrape._refine_chair_subtype
        for name, cat in [("Soft Edge 82", "chair"), ("Substance", "chair"), ("Gray", "chair"),
                          ("Aaron Dining Chair", "Dining Chair"), ("Era Armchair", "Lounge chair, chair"),
                          ("Floor lamp", "Lamp"), ("Eternity Swivel | Black", "chair")]:
            self.assertEqual(f(name, cat), cat, name)

    def test_parts_and_hardware_are_not_chairs(self):
        f = scrape._refine_chair_subtype
        self.assertEqual(f("DS12 Wall mount for folding chairs", "chair"), "chair")
        self.assertEqual(f("Seat cushion for dining chair", "chair"), "chair")

    def test_it_is_idempotent(self):
        once = scrape._refine_chair_subtype("ELLIOT DINING CHAIR", "chair")
        self.assertEqual(scrape._refine_chair_subtype("ELLIOT DINING CHAIR", once), once)


class ReleasedAtTests(unittest.TestCase):
    """released_at (2026-10-04): the maker's own date for a piece, as YYYY-MM-DD."""

    def test_earliest_of_created_and_published(self):
        self.assertEqual(scrape._earliest_date(["2026-09-21T15:34:28+02:00", "2026-06-02T12:16:42+02:00"]), "2026-06-02")

    def test_ignores_missing_and_malformed_values(self):
        self.assertEqual(scrape._earliest_date([None, "", "yesterday", "2025-01-05"]), "2025-01-05")
        self.assertIsNone(scrape._earliest_date([None, ""]))
        self.assertIsNone(scrape._earliest_date([]))

    def test_the_products_table_has_the_column_and_save_product_stores_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = scrape.DB_PATH
            scrape.DB_PATH = Path(tmp) / "t.db"
            try:
                conn = scrape.setup_database()
                scrape.save_product(conn, {"brand": "B", "brand_url": "https://b.example", "product_name": "P",
                                           "product_url": "https://b.example/p", "released_at": "2026-05-01"})
                self.assertEqual(conn.execute("SELECT released_at FROM products").fetchone()[0], "2026-05-01")
                scrape.save_product(conn, {"brand": "B", "brand_url": "https://b.example", "product_name": "Q",
                                           "product_url": "https://b.example/q"})
                self.assertIsNone(conn.execute("SELECT released_at FROM products WHERE product_name='Q'").fetchone()[0])
            finally:
                scrape.DB_PATH = old


class DesignerCreditTests(unittest.TestCase):
    """designer_credits.split_credit (2026-10-04): one credit string -> the designers it names."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))
        import designer_credits
        self.split = designer_credits.split_credit
        self.counts = designer_credits.credited_counts

    def test_joined_credits_name_each_designer(self):
        self.assertEqual(self.split("Marcello Jori, Massimo Giacon"), ["Marcello Jori", "Massimo Giacon"])
        self.assertEqual(self.split("Ben van Berkel / UNStudio"), ["Ben van Berkel", "UNStudio"])

    def test_stray_spaces_do_not_make_a_second_designer(self):
        self.assertEqual(self.split("LPWK , Marcello Jori"), self.split("LPWK, Marcello Jori"))
        self.assertEqual(self.split("Marta Sansoni,  LPWK"), ["Marta Sansoni", "LPWK"])

    def test_catch_all_and_empty_credits_name_nobody(self):
        for raw in ("Aa.Vv.", " ", "", None):
            self.assertEqual(self.split(raw), [])

    def test_studio_duos_and_single_names_stay_whole(self):
        self.assertEqual(self.split("Tham & Videg\u00e5rd"), ["Tham & Videg\u00e5rd"])
        self.assertEqual(self.split("Pierre Sindre"), ["Pierre Sindre"])

    def test_hand_checked_overrides(self):
        self.assertEqual(self.split("French designer brothers Ronan and Erwan Bouroullec"), ["Ronan Bouroullec", "Erwan Bouroullec"])
        self.assertEqual(self.split("Franco and Franca Albini and Helg"), ["Franco Albini", "Franca Helg"])
        self.assertEqual(self.split("Stockholm-based TAF Studio"), ["TAF Studio"])

    def test_counts_aggregate_across_spellings(self):
        c = self.counts([("LPWK, Marcello Jori", 8), ("LPWK , Marcello Jori", 2), ("Marcello Jori, Massimo Giacon", 32)])
        self.assertEqual(c["Marcello Jori"], 42)
        self.assertEqual(c["LPWK"], 10)
