"""
Guards for the icon CSS that replaced the Tabler icon font (2026-10-04).

Every `ti-NAME` class the pages or scripts use must be drawn by frontend/icons.css
(ti-vase silently drew nothing for months because the font had no such icon), and
every page that shows an icon must link the stylesheet.

    python3 -m unittest discover tests
"""

import glob
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
ICON_RE = re.compile(r"\bti-([a-z0-9]+(?:-[a-z0-9]+)*)")


class IconTests(unittest.TestCase):
    def test_every_icon_class_in_use_is_defined(self):
        css = (ROOT / "frontend" / "icons.css").read_text()
        defined = set(re.findall(r"\.ti-([a-z0-9-]+)\s*\{", css))
        sources = (glob.glob(str(ROOT / "frontend" / "*.html")) + glob.glob(str(ROOT / "frontend" / "*.js"))
                   + glob.glob(str(ROOT / "scraper" / "generate_*.py")))
        used = set()
        for f in sources:
            used |= set(ICON_RE.findall(Path(f).read_text()))
        self.assertEqual(sorted(used - defined), [], "icon classes used but not drawn by icons.css")

    def test_pages_with_icons_link_the_stylesheet_and_not_the_font(self):
        missing, font = [], []
        for f in glob.glob(str(ROOT / "docs" / "**" / "*.html"), recursive=True):
            s = Path(f).read_text()
            if 'class="ti ti-' in s and "/icons.css?v=" not in s:
                missing.append(f)
            if "tabler-icons" in s or "cdn.jsdelivr.net" in s:
                font.append(f)
        self.assertEqual(missing, [])
        self.assertEqual(font, [])

    def test_icons_css_is_mirrored_to_docs(self):
        self.assertEqual((ROOT / "frontend" / "icons.css").read_text(), (ROOT / "docs" / "icons.css").read_text())


if __name__ == "__main__":
    unittest.main()
