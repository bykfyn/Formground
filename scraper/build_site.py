"""
Builds the whole generated site in the one correct order (2026-10-06). Used by the scrape workflow and by hand,
so the order lives in one place instead of three (this list had drifted: the workflow lacked the designers,
architects, marketplace, For Creators and guides generators, so a weekly run would have dropped the guides
from the sitemap).

    python3 scraper/build_site.py

Order matters: generate_brand_pages.py rebuilds sitemap.xml from scratch and the generators after it append
their own URLs; the lastmod pass and the asset stamping run last. Hand-written pages (frontend/*.html) are
NOT copied here: copy them to docs/ yourself when you edit them.
"""

import subprocess
import sys
from pathlib import Path

SCRAPER = Path(__file__).parent

GENERATORS = [
    "generate_brand_pages",
    "generate_theme_landing_pages",
    "generate_browse_pages",
    "generate_themed_edit_pages",
    "generate_edits_page",
    "generate_guides_pages",
    "generate_designers_pages",
    "generate_architects_pages",
    "generate_marketplace_page",
    "generate_for_creators_page",
    "generate_agent_docs",
]


def main():
    for name in GENERATORS:
        print(f"== {name}")
        result = subprocess.run([sys.executable, str(SCRAPER / f"{name}.py")])
        if result.returncode != 0:
            print(f"build_site: {name} failed", file=sys.stderr)
            sys.exit(result.returncode)
    sys.path.insert(0, str(SCRAPER))
    import site_assets
    import sitemap_lastmod

    print(f"== stamp_html: {site_assets.stamp_html()} page(s) updated")
    sitemap_lastmod.apply()


if __name__ == "__main__":
    main()
