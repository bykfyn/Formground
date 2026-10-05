"""
Is Formground doing its job? One command answers it from the anonymous event log.

    python3 scraper/insights_report.py                 # last 14 days, everything
    python3 scraper/insights_report.py --days 7 --campaign spring_chairs

Needs Google Cloud credentials for the project that holds the BigQuery table
formground_analytics.events (`gcloud auth application-default login`). Read-only.

What it reports (definitions are the thresholds to agree BEFORE the ads start):
  1. Search success   - share of searches (human, Work page) that led to a click to a
                        maker's own site, share with no results, and the visitors' own
                        "How were these results?" answers.
  2. Unmet demand     - queries that returned nothing or almost nothing. This list is
                        the scraping to-do list.
  3. Rewording        - of visits whose first search got no click, how many searched again.
  4. By campaign/page - per landing page: visits, visits that searched, visits that clicked
                        through to a maker.
  5. By category      - which kinds of search succeed and which don't.

Visits are grouped by the random per-tab visit id (see frontend/fg-track.js): it describes
one visit in one tab, never a person, and cannot be linked across visits.
"""

import argparse

from google.cloud import bigquery

DATASET, TABLE = "formground_analytics", "events"

# Every query starts from the same window; {t} is the fully qualified table.
WINDOW = """
WITH ev AS (
  SELECT * FROM `{t}`
  WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
    AND (@campaign IS NULL OR utm_campaign = @campaign)
),
searches AS (
  SELECT * FROM ev WHERE event_type = 'search' AND surface = 'work'
),
clicked AS (
  SELECT DISTINCT search_id FROM ev WHERE event_type = 'click' AND search_id IS NOT NULL
),
rated AS (
  SELECT search_id, ARRAY_AGG(rating ORDER BY timestamp DESC LIMIT 1)[OFFSET(0)] AS rating
  FROM ev WHERE event_type = 'feedback' AND search_id IS NOT NULL AND rating IS NOT NULL
  GROUP BY search_id
)
"""

REPORTS = [
    ("1. Search success", """
SELECT
  COUNT(*) AS searches,
  COUNTIF(s.total_matches = 0) AS no_results,
  COUNTIF(c.search_id IS NOT NULL) AS led_to_click,
  COUNTIF(r.search_id IS NOT NULL) AS rated,
  COUNTIF(r.rating = 'spot_on') AS spot_on,
  COUNTIF(r.rating = 'close') AS close_,
  COUNTIF(r.rating = 'not_wanted') AS not_wanted,
  COUNTIF(c.search_id IS NOT NULL AND r.rating = 'not_wanted') AS clicked_but_not_wanted
FROM searches s
LEFT JOIN clicked c ON c.search_id = s.search_id
LEFT JOIN rated r ON r.search_id = s.search_id
""", [("no_results", "searches"), ("led_to_click", "searches"), ("rated", "searches")]),

    ("2. Unmet demand: searches with 0-3 matches", """
SELECT LOWER(TRIM(query)) AS query, COUNT(*) AS times, MAX(total_matches) AS matches
FROM searches
WHERE total_matches <= 3 AND query IS NOT NULL
GROUP BY query
ORDER BY times DESC
LIMIT 25
""", []),

    ("3. Rewording after a search with no click", """
, s AS (
  SELECT visit_id, search_id,
         ROW_NUMBER() OVER (PARTITION BY visit_id ORDER BY timestamp) AS n
  FROM searches WHERE visit_id IS NOT NULL
),
first_s AS (
  SELECT s.visit_id, c.search_id IS NOT NULL AS clicked
  FROM s LEFT JOIN clicked c ON c.search_id = s.search_id WHERE s.n = 1
)
SELECT
  COUNT(*) AS visits_that_searched,
  COUNTIF(clicked) AS first_search_clicked,
  COUNTIF(NOT clicked) AS first_search_no_click,
  COUNTIF(NOT clicked AND EXISTS (SELECT 1 FROM s s2 WHERE s2.visit_id = first_s.visit_id AND s2.n = 2))
    AS searched_again_after_no_click
FROM first_s
""", [("first_search_clicked", "visits_that_searched"),
      ("searched_again_after_no_click", "first_search_no_click")]),

    ("4. By campaign and landing page", """
SELECT
  COALESCE(utm_campaign, '(none)') AS campaign,
  landing_page,
  COUNT(DISTINCT visit_id) AS visits,
  COUNT(DISTINCT IF(event_type IN ('search', 'discover'), visit_id, NULL)) AS visits_that_searched,
  COUNT(DISTINCT IF(event_type = 'click', visit_id, NULL)) AS visits_that_clicked_through
FROM ev
WHERE visit_id IS NOT NULL
GROUP BY campaign, landing_page
ORDER BY visits DESC
LIMIT 30
""", []),

    ("5. By search category", """
SELECT
  COALESCE(s.category, '(none recognised)') AS category,
  COUNT(*) AS searches,
  COUNTIF(c.search_id IS NOT NULL) AS led_to_click,
  ROUND(100 * SAFE_DIVIDE(COUNTIF(c.search_id IS NOT NULL), COUNT(*)), 1) AS click_pct
FROM searches s LEFT JOIN clicked c ON c.search_id = s.search_id
GROUP BY 1
HAVING searches >= 3
ORDER BY searches DESC
LIMIT 25
""", []),
]


def print_table(rows, ratios):
    if not rows:
        print("  (no data in this window)")
        return
    cols = list(rows[0].keys())
    widths = [max(len(c), *(len(str(r[c])) for r in rows)) for c in cols]
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  " + "  ".join(str(r[c]).ljust(w) for c, w in zip(cols, widths)))
    if len(rows) == 1:
        r = rows[0]
        for num, den in ratios:
            if r[den]:
                print(f"  {num} / {den}: {100 * r[num] / r[den]:.1f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--campaign", default=None, help="only events carrying this utm_campaign")
    args = ap.parse_args()

    client = bigquery.Client()
    table = f"{client.project}.{DATASET}.{TABLE}"
    config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("days", "INT64", args.days),
        bigquery.ScalarQueryParameter("campaign", "STRING", args.campaign),
    ])
    print(f"Formground insights, last {args.days} days" + (f", campaign {args.campaign}" if args.campaign else ""))
    for title, sql, ratios in REPORTS:
        # the window CTE ends before the first SELECT; report 3 adds its own CTEs with a leading comma
        body = WINDOW.format(t=table) + sql
        print(f"\n{title}")
        print_table([dict(r) for r in client.query(body, job_config=config).result()], ratios)


if __name__ == "__main__":
    main()
