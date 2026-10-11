import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))
import image_fit  # noqa: E402


class CardFitTests(unittest.TestCase):
    def setUp(self):
        self.saved = image_fit._cache
        image_fit._cache = {}

    def tearDown(self):
        image_fit._cache = self.saved

    def put(self, url, **info):
        image_fit._cache[url] = {"ratio": 0.67, "bg": "#f0f0f0", "edge_std": 3.0, **info}
        return image_fit.fit_for_card(url)

    def test_unknown_photo_is_left_alone(self):
        self.assertEqual(image_fit.fit_for_card("https://x/none.jpg"), ("", "", ""))

    def test_square_or_busy_photos_keep_the_normal_crop(self):
        self.assertEqual(self.put("a", ratio=1.0, box=[0.2, 0.2, 0.8, 0.8]), ("", "", ""))
        self.assertEqual(self.put("b", edge_std=40, box=[0.2, 0.2, 0.8, 0.8]), ("", "", ""))

    def test_a_small_piece_in_a_tall_photo_keeps_full_size_with_the_window_moved_onto_it(self):
        cls, box_style, img_style = self.put("c", box=[0.3, 0.30, 0.7, 0.62])      # 32% tall, window is 67%
        self.assertEqual((cls, box_style), ("", ""))
        self.assertTrue(img_style.startswith("object-position:50% "))
        pct = float(img_style.split("50% ")[1].rstrip("%"))
        self.assertTrue(0 <= pct <= 100)

    def test_a_piece_too_tall_for_the_window_is_shown_whole_on_its_own_colour(self):
        cls, box_style, img_style = self.put("d", box=[0.3, 0.05, 0.7, 0.95])      # 90% tall, window is 67%
        self.assertEqual(cls, "contain-fit")
        self.assertEqual(box_style, "background:#f0f0f0")
        self.assertEqual(img_style, "")

    def test_a_wide_photo_moves_the_window_sideways(self):
        _, _, img_style = self.put("e", ratio=1.5, box=[0.4, 0.1, 0.62, 0.9])
        self.assertTrue(img_style.endswith(" 50%"))

    def test_without_a_measured_box_an_off_square_flat_photo_is_shown_whole(self):
        self.assertEqual(self.put("f")[0], "contain-fit")


if __name__ == "__main__":
    unittest.main()
