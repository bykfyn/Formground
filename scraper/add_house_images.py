"""
Second pass over the houses already extracted by scrape_architect_projects.py:
visits each qualifying house's real URL again and finds one real, verified
photo, reusing the exact vision-relevance check already proven in
scrape_architects.py (is this photo really a building exterior/interior, not
a logo, rendering, or unrelated scene).

Kept as a separate pass rather than folded into the first script - text
extraction and image verification are different concerns, and re-running
just this pass doesn't require re-discovering/re-classifying every page.

RUN: python3 add_house_images.py
"""

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from scrape_architects import is_architecture_relevant, _looks_like_noise

SCRAPER_DIR = Path(__file__).parent
DATA_PATH = SCRAPER_DIR.parent / "data" / "architect_projects_test.json"
MAX_CANDIDATES_TO_TRY = 5


def extract_candidate_images(page, base_url):
    imgs = page.eval_on_selector_all(
        "img",
        """els => els.map(e => ({
            src: e.currentSrc || e.src || e.getAttribute('data-src') || '',
            width: e.naturalWidth,
            height: e.naturalHeight,
        }))""",
    )
    candidates = []
    for img in imgs:
        url = img["src"]
        if not url or url.startswith("data:"):
            continue
        if _looks_like_noise(url, img.get("width"), img.get("height")):
            continue
        # Real photos on these sites are large; thumbnails/icons are not.
        if img.get("width") and img["width"] < 300:
            continue
        if url not in candidates:
            candidates.append(url)
    return candidates


def main():
    data = json.loads(DATA_PATH.read_text())
    total_checked = 0
    total_found = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        for firm, projects in data.items():
            print(f"=== {firm} ===")
            for project in projects:
                if not project.get("is_house"):
                    continue
                total_checked += 1
                try:
                    page.goto(project["url"], timeout=15000, wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)
                    candidates = extract_candidate_images(page, project["url"])
                except Exception as e:
                    print(f"  fetch error {project['url']}: {e}")
                    project["image"] = None
                    continue

                found = None
                for candidate in candidates[:MAX_CANDIDATES_TO_TRY]:
                    if is_architecture_relevant(candidate):
                        found = candidate
                        break
                    time.sleep(0.2)

                project["image"] = found
                if found:
                    total_found += 1
                mark = "OK" if found else "none"
                print(f"  [{mark}] {project.get('name')} ({len(candidates)} candidates)")

        browser.close()

    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\n{total_found}/{total_checked} houses got a verified real image. Wrote {DATA_PATH}")


if __name__ == "__main__":
    main()
