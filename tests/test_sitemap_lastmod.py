"""scraper/sitemap_lastmod.py: lastmod is the date a page's content really changed, not the build date."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))

import sitemap_lastmod as sl  # noqa: E402

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://formground.com/</loc>
    <changefreq>weekly</changefreq>
  </url>
  <url>
    <loc>https://formground.com/work/chairs.html</loc>
    <lastmod>2026-10-06</lastmod>
    <changefreq>weekly</changefreq>
  </url>
</urlset>
"""


class LastmodTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "work").mkdir()
        (self.tmp / "index.html").write_text("<html>home ?v=11111111</html>")
        (self.tmp / "work" / "chairs.html").write_text("<html>chairs</html>")
        (self.tmp / "sitemap.xml").write_text(SITEMAP)
        self.store = self.tmp / "store.json"

    def run_apply(self, today):
        sl.apply(self.tmp, self.store, today)
        text = (self.tmp / "sitemap.xml").read_text()
        return dict(re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", text))

    def test_first_run_dates_everything_that_day(self):
        got = self.run_apply("2026-10-06")
        self.assertEqual(set(got.values()), {"2026-10-06"})
        self.assertEqual(len(got), 2)                      # the home page gets a date too

    def test_unchanged_pages_keep_their_date(self):
        self.run_apply("2026-10-06")
        got = self.run_apply("2026-10-20")
        self.assertEqual(set(got.values()), {"2026-10-06"})

    def test_changed_page_gets_the_new_date_only_for_itself(self):
        self.run_apply("2026-10-06")
        (self.tmp / "work" / "chairs.html").write_text("<html>chairs, one more piece</html>")
        got = self.run_apply("2026-10-20")
        self.assertEqual(got["https://formground.com/work/chairs.html"], "2026-10-20")
        self.assertEqual(got["https://formground.com/"], "2026-10-06")

    def test_a_stylesheet_version_bump_is_not_a_content_change(self):
        self.run_apply("2026-10-06")
        (self.tmp / "index.html").write_text("<html>home ?v=22222222</html>")
        got = self.run_apply("2026-10-20")
        self.assertEqual(got["https://formground.com/"], "2026-10-06")

    def test_urls_that_leave_the_sitemap_leave_the_record(self):
        self.run_apply("2026-10-06")
        (self.tmp / "sitemap.xml").write_text(SITEMAP.split("  <url>\n    <loc>https://formground.com/work")[0] + "</urlset>\n")
        self.run_apply("2026-10-20")
        self.assertEqual(list(json.loads(self.store.read_text())), ["https://formground.com/"])


if __name__ == "__main__":
    unittest.main()
