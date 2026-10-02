"""
Regression tests for the analytics dimensions added 2026-10-02: per-maker
traffic (pageview + result_brands), the search query log (search_id,
resolved category, counts), server-stamped maker classification, and
landing-page attribution. No network, no BigQuery - log_event is replaced
with a recorder. Skipped (not failed) if the backend's web dependencies
are not installed.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

try:
    import analytics
    import main
    from fastapi.testclient import TestClient
    HAVE_DEPS = True
except ImportError:  # fastapi / httpx / google-cloud-bigquery not installed
    HAVE_DEPS = False

BROWSER = {"user-agent": "Mozilla/5.0 (Macintosh) Safari/605"}


@unittest.skipUnless(HAVE_DEPS, "backend web dependencies not installed")
class BuildRowTests(unittest.TestCase):
    def test_keeps_only_schema_columns_and_coerces_ints(self):
        row = analytics.build_row("click", {"brand": "X", "position": "3", "bogus": 1, "result_count": "abc"})
        self.assertEqual(row["brand"], "X")
        self.assertEqual(row["position"], 3)
        self.assertNotIn("bogus", row)
        self.assertNotIn("result_count", row)  # not an integer -> dropped, never a crash

    def test_caller_cannot_override_timestamp_or_event_type(self):
        row = analytics.build_row("click", {"timestamp": "1999", "event_type": "evil"})
        self.assertEqual(row["event_type"], "click")
        self.assertNotEqual(row["timestamp"], "1999")

    def test_only_columns_the_live_table_has_are_sent(self):
        row = analytics.build_row("click", {"brand": "X", "page_path": "/p"}, allowed=analytics.LEGACY_FIELDS)
        self.assertIn("brand", row)
        self.assertNotIn("page_path", row)

    def test_empty_values_dropped_and_strings_truncated(self):
        row = analytics.build_row("search", {"query": "", "category": None, "material": "x" * 9000})
        self.assertNotIn("query", row)
        self.assertNotIn("category", row)
        self.assertEqual(len(row["material"]), analytics.MAX_STRING)


@unittest.skipUnless(HAVE_DEPS, "backend web dependencies not installed")
class PageClassificationTests(unittest.TestCase):
    def test_page_types(self):
        cases = {
            "/": "home", "/work.html": "work", "/brands/hay.html": "brand",
            "/browse/": "browse_hub", "/browse/sofas-2.html": "browse",
            "/designers/someone.html": "designer", "/designers.html": "directory",
            "/marketplace.html": "marketplace", "/round-dining-tables.html": "edit_or_category",
        }
        for path, expected in cases.items():
            self.assertEqual(main._page_type(path), expected, path)

    def test_clean_path_drops_query_and_fragment(self):
        self.assertEqual(main._clean_path("/brands/hay.html?utm_source=x#top"), "/brands/hay.html")
        self.assertIsNone(main._clean_path(None))

    def test_brand_dims_are_server_side_and_default_independent(self):
        self.assertEqual(main._brand_dims("Serax")["brand_tier"], "established")
        self.assertEqual(main._brand_dims("A Brand That Does Not Exist")["brand_tier"], "independent")
        self.assertEqual(main._brand_dims(None), {})


@unittest.skipUnless(HAVE_DEPS, "backend web dependencies not installed")
class EventEndpointTests(unittest.TestCase):
    def setUp(self):
        self.logged = []
        self._orig = main.log_event
        main.log_event = lambda event_type, **kw: self.logged.append((event_type, kw))
        self.client = TestClient(main.app)

    def tearDown(self):
        main.log_event = self._orig

    def post(self, payload, headers=BROWSER):
        return self.client.post("/event", json=payload, headers=headers)

    def test_click_is_attributed_to_page_landing_and_maker_tier(self):
        self.post({
            "event_type": "click", "brand": "Serax", "page_path": "/browse/vases.html?x=1",
            "landing_page": "/browse/sofas.html", "position": 7, "search_id": "abc123",
            "target_url": "https://serax.com/p/vase?utm=1#h",
        })
        event_type, kw = self.logged[-1]
        self.assertEqual(event_type, "click")
        self.assertEqual(kw["page_path"], "/browse/vases.html")
        self.assertEqual(kw["page_type"], "browse")
        self.assertEqual(kw["landing_page"], "/browse/sofas.html")
        self.assertEqual(kw["target_url"], "https://serax.com/p/vase")  # no query string
        self.assertEqual(kw["target_type"], "maker")
        self.assertEqual(kw["brand_tier"], "established")
        self.assertEqual(kw["search_id"], "abc123")

    def test_client_cannot_set_the_maker_tier(self):
        self.post({"event_type": "click", "brand": "Cozmo", "brand_tier": "established"})
        self.assertEqual(self.logged[-1][1]["brand_tier"], "independent")

    def test_marketplace_click_targets_a_retailer(self):
        self.post({"event_type": "click", "brand": "X", "page_path": "/marketplace.html"})
        self.assertEqual(self.logged[-1][1]["target_type"], "retailer")

    def test_pageview_lists_deduplicated_makers_with_server_tier(self):
        self.post({"event_type": "pageview", "page_path": "/browse/sofas.html",
                   "result_brands": ["Serax", "Cozmo", "Serax"], "referrer_host": "www.google.com"})
        event_type, kw = self.logged[-1]
        self.assertEqual(event_type, "pageview")
        self.assertEqual(kw["result_brands"], '[["Serax","established"],["Cozmo","independent"]]')
        self.assertIsNone(kw["target_type"])  # only clicks have a target

    def test_known_crawlers_are_not_logged(self):
        self.post({"event_type": "pageview", "page_path": "/"}, headers={"user-agent": "Googlebot/2.1"})
        self.assertEqual(self.logged, [])

    def test_search_logs_resolved_intent_counts_and_search_id(self):
        orig = main.search_full
        main.search_full = lambda q, tier=None: {
            "results": [{"brand": "Serax"}, {"brand": "Cozmo"}], "total_matches": 40, "total_brands": 9,
            "intent": {"category": "vase", "material": "glass", "countries": ["Belgium"], "tier": tier},
        }
        try:
            body = self.client.get("/search", params={"q": "glass vase", "landing_page": "/browse/vases.html"},
                                   headers=BROWSER).json()
        finally:
            main.search_full = orig
        event_type, kw = self.logged[-1]
        self.assertEqual(event_type, "search")
        self.assertEqual(kw["search_id"], body["search_id"])
        self.assertEqual((kw["category"], kw["material"], kw["intent_countries"]), ("vase", "glass", "Belgium"))
        self.assertEqual((kw["total_matches"], kw["total_brands"], kw["result_count"]), (40, 9, 2))
        self.assertEqual(kw["landing_page"], "/browse/vases.html")
        self.assertEqual(kw["surface"], "work")

    def test_agent_search_is_logged_and_not_bot_filtered(self):
        orig = main.search_full
        main.search_full = lambda q, tier=None: {
            "results": [], "total_matches": 0, "total_brands": 0, "intent": {"category": "sofa"},
        }
        try:
            self.client.get("/agent/search", params={"q": "sofa"}, headers={"user-agent": "ChatGPT-User bot"})
        finally:
            main.search_full = orig
        event_type, kw = self.logged[-1]
        self.assertEqual((event_type, kw["surface"], kw["category"]), ("search", "agent", "sofa"))


if __name__ == "__main__":
    unittest.main()
