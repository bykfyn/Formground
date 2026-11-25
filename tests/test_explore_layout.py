"""The maker/designer page layout: facts as one line, linked tags, "A selection" with the full list behind a button,
and pieces named in the profile text linking to their card."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))

import creator_texts  # noqa: E402
import generate_brand_pages as gbp  # noqa: E402


def piece(name, category, n=0):
    return {"brand": "Acme", "product_name": name, "category": category, "image_url": f"https://x.test/{name}.jpg",
            "product_url": f"https://acme.test/{name}", "brand_url": "https://acme.test", "link_dead": 0, "thin": 0, "designer": ""}


class TagLinks(unittest.TestCase):
    def test_types_country_and_ceramics(self):
        self.assertEqual(gbp.tag_href("Furniture", "France"), "/work/furniture.html")
        self.assertEqual(gbp.tag_href("Ceramics", "France"), "/work.html?q=ceramics")
        self.assertEqual(gbp.tag_href("New Zealand", "New Zealand"), "/work.html?q=from+New+Zealand")


class MetaLine(unittest.TestCase):
    def setUp(self):
        self._load = creator_texts.load_all
        creator_texts.load_all = lambda: {
            "makers:a": {"group": "makers", "facts": [["Country", "France"], ["City", "Marseille"], ["Type", "Publisher"],
                                                     ["Website", "a.com"], ["Founded", "2019"], ["Made to order", "Yes (stated)"]]},
            "designers:b": {"group": "designers", "facts": [["Country", "Italy"], ["City", "Milan"], ["Type", "Designer"]]},
            "designers:c": {"group": "designers", "facts": [["Country", "Italy"], ["Type", "Design studio"], ["Made to order", "Unknown"]]},
        }

    def tearDown(self):
        creator_texts.load_all = self._load

    def test_maker_line_drops_country_website_and_repeated_type(self):
        self.assertIn("Marseille · Founded 2019 · Made to order", creator_texts.meta_line_html("makers", "a"))
        self.assertNotIn("Publisher", creator_texts.meta_line_html("makers", "a"))

    def test_designer_line_has_country_and_drops_designer(self):
        self.assertIn(">Milan, Italy<", creator_texts.meta_line_html("designers", "b", with_country=True))

    def test_type_that_adds_something_stays(self):
        self.assertIn("Italy · Design studio", creator_texts.meta_line_html("designers", "c", with_country=True))

    def test_country_tag_takes_the_one_country_and_skips_several(self):
        creator_texts.load_all = lambda: {
            "designers:a": {"group": "designers", "facts": [["Country", "Italy (Spanish designer)"]]},
            "designers:b": {"group": "designers", "facts": [["Country", "Italy and Sweden (Italian designer)"]]},
            "designers:c": {"group": "designers", "facts": [["Type", "Designer"]]},
        }
        self.assertEqual(creator_texts.country_of("designers", "a"), "Italy")
        self.assertEqual(creator_texts.country_of("designers", "b"), "")
        self.assertEqual(creator_texts.country_of("designers", "c"), "")
        self.assertEqual(creator_texts.country_of("designers", "nobody"), "")

    def test_no_entry_no_line(self):
        self.assertEqual(creator_texts.meta_line_html("makers", "nobody"), "")


class SelectionLayout(unittest.TestCase):
    def layout(self, text="<p>Known for the Alba lamp and the Soren chair.</p>"):
        products = [piece(f"Item {i}", ["Chair", "Lamp", "Vase"][i % 3]) for i in range(20)]
        products += [piece("Alba lamp", "Lamp"), piece("Soren chair", "Chair")]
        rest = "".join(gbp.product_card_html(p, share=True) for p in products)
        return gbp.explore_layout(products, lambda p: gbp.product_card_html(p, share=True), text,
                                  f'<div class="grid" data-listing-grid>{rest}</div>', len(products))

    def test_selection_size_and_phone_cut(self):
        _, block = self.layout()
        selection = block.split('class="show-all-row"')[0]
        self.assertEqual(selection.count('<a class="card'), gbp.SELECTION_SIZE)
        self.assertEqual(selection.count("card-extra-m"), gbp.SELECTION_SIZE - gbp.SELECTION_PHONE)
        self.assertIn("A selection", selection)
        self.assertIn("Show all 22 pieces", block)

    def test_selected_pieces_are_not_repeated_in_the_list(self):
        _, block = self.layout()
        rest = block.split('class="rest-block"')[1]
        self.assertEqual(rest.count("in-selection"), gbp.SELECTION_SIZE)

    def test_selection_grid_is_not_the_listing_grid(self):
        # listing.js appends "See more" cards to the first [data-listing-grid]: that must be the full list
        _, block = self.layout()
        self.assertLess(block.index('class="rest-block"'), block.index("data-listing-grid"))

    def test_named_pieces_link_to_a_card_with_that_id(self):
        text, block = self.layout()
        self.assertEqual(text.count('class="piece-link"'), 2)
        for pid in ("piece-1", "piece-2"):
            if f'href="#{pid}"' in text:
                self.assertIn(f'id="{pid}"', block)

    def test_profile_edit_link_paragraph_untouched(self):
        text, _ = self.layout('<p class="creator-more"><a href="/edits/x.html">Alba</a></p>')
        self.assertNotIn("piece-link", text)


if __name__ == "__main__":
    unittest.main()
