import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))
from image_sizes import CARD, sized  # noqa: E402


class SizedTests(unittest.TestCase):
    def test_shopify_adds_width_and_keeps_version(self):
        out = sized("https://cdn.shopify.com/s/files/1/0/files/a.jpg?v=123", CARD)
        self.assertIn("v=123", out)
        self.assertIn("width=500", out)

    def test_shopify_replaces_an_existing_width(self):
        out = sized("https://cdn.shopify.com/s/files/a.jpg?v=1&width=1500", 480)
        self.assertEqual(out.count("width="), 1)
        self.assertIn("width=480", out)

    def test_squarespace_format(self):
        self.assertIn("format=500w", sized("https://images.squarespace-cdn.com/content/v1/x/a.jpg", 500))
        self.assertIn("format=500w", sized("https://static1.squarespace.com/static/x/a.jpg?format=1500w", 500))

    def test_datocms_swaps_height_for_width(self):
        out = sized("https://www.datocms-assets.com/1/2-a.png?h=800", 500)
        self.assertNotIn("h=800", out)
        self.assertIn("w=500", out)

    def test_contentful_and_fogia(self):
        self.assertIn("w=500", sized("https://images.ctfassets.net/a/b/c/x.jpg", 500))
        self.assertIn("w=500", sized("https://images.fogia.com/x/y.png?auto=format&w=2000&q=90", 500))

    def test_framer_rule_drops_the_non_resizing_width_height_and_asks_for_scale_down_to(self):
        self.assertEqual(
            sized("https://framerusercontent.com/images/AA7i.jpg?width=2200&height=3000", 500),
            "https://framerusercontent.com/images/AA7i.jpg?scale-down-to=500")

    def test_hay_gubi_sanity_and_wix_rules(self):
        self.assertEqual(sized("https://www.hay.com/img/a.jpg", 500), "https://www.hay.com/img/a.jpg?w=500")
        self.assertEqual(sized("https://cdn.thorcommerce.io/x/a.png?w=2000", 500), "https://cdn.thorcommerce.io/x/a.png?w=500")
        self.assertEqual(sized("https://cdn.sanity.io/images/p/d/abc-3000x2000.jpg", 500),
                         "https://cdn.sanity.io/images/p/d/abc-3000x2000.jpg?w=500&auto=format")
        self.assertEqual(sized("https://static.wixstatic.com/media/a1_b~mv2.jpg/v1/fill/w_1000,h_600/x.jpg", 500),
                         "https://static.wixstatic.com/media/a1_b~mv2.jpg/v1/fit/w_500,h_500,q_80/file.jpg")
        self.assertEqual(sized("https://static.wixstatic.com/media/a1.png", 500),
                         "https://static.wixstatic.com/media/a1.png/v1/fit/w_500,h_500,q_80/file.png")
        self.assertEqual(sized("https://static.wixstatic.com/media/a1.pdf", 500), "https://static.wixstatic.com/media/a1.pdf")

    def test_unknown_hosts_and_non_urls_are_untouched(self):
        for u in ("https://www.ligne-roset.com/img/a.jpg", "/images/architects/x.jpg", "", None):
            self.assertEqual(sized(u, CARD), u)


if __name__ == "__main__":
    unittest.main()
