"""
Formground link checker.

WHAT THIS DOES:
  A lightweight, separate pass over the existing database - not a
  re-scrape. For every product already saved, sends a quick HEAD
  request to its product_url and flags it "link_dead" if the page
  truly 404s. The frontend then links a flagged card to the brand's
  homepage instead of the dead product page, so browsing never ends
  in a 404 - without needing to wait for that brand's next full
  scrape (which only runs weekly) to clear it.

  Only a confirmed 404 sets link_dead=1. A confirmed 200 clears it
  (a brand can un-discontinue or fix a broken link). Anything
  ambiguous - timeout, connection error, 5xx, redirects, etc. -
  leaves the existing flag untouched rather than guessing, since a
  transient hiccup shouldn't get treated the same as a genuine 404.

WHO RUNS THIS:
  The GitHub Action at .github/workflows/check_links.yml, on its own
  daily schedule - deliberately more frequent than the weekly full
  scrape (.github/workflows/scrape.yml), since its whole purpose is
  to catch a broken link in the gap between full scrapes. You can
  also run it yourself with:

    python scraper/check_links.py
"""

import time

import requests

from scrape import DB_PATH, HEADERS, setup_database

MAX_TOTAL_RUNTIME_SECONDS = 25 * 60  # same safety-ceiling principle as scrape.py - just a
                                      # bigger budget since this is only lightweight HEAD
                                      # requests, not full page fetches/pagination
REQUEST_TIMEOUT = 10


def check_all_links():
    conn = setup_database()
    rows = conn.execute("SELECT id, product_url, link_dead FROM products").fetchall()

    start_time = time.monotonic()
    checked = 0
    newly_dead = 0
    newly_revived = 0
    stopped_early = False

    for product_id, product_url, currently_dead in rows:
        if time.monotonic() - start_time > MAX_TOTAL_RUNTIME_SECONDS:
            print(f"Hit the {MAX_TOTAL_RUNTIME_SECONDS // 60}-minute safety limit - "
                  f"stopping here, remaining links get checked next run.")
            stopped_early = True
            break

        try:
            resp = requests.head(
                product_url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True
            )
            status = resp.status_code
        except requests.RequestException as e:
            # Ambiguous (network hiccup, timeout, DNS blip) - don't touch
            # the existing flag either way.
            checked += 1
            continue

        checked += 1
        if status == 404 and not currently_dead:
            conn.execute("UPDATE products SET link_dead = 1 WHERE id = ?", (product_id,))
            conn.commit()
            newly_dead += 1
        elif status == 200 and currently_dead:
            conn.execute("UPDATE products SET link_dead = 0 WHERE id = ?", (product_id,))
            conn.commit()
            newly_revived += 1

    conn.close()
    total_seconds = round(time.monotonic() - start_time, 1)
    print(f"Checked {checked}/{len(rows)} links in {total_seconds}s. "
          f"{newly_dead} newly flagged dead, {newly_revived} revived."
          + (" (stopped early)" if stopped_early else ""))


if __name__ == "__main__":
    check_all_links()
