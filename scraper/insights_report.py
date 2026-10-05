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
  6. Clicks by source - outbound clicks per page, split by where the visit came from: the ad
                        (utm_source), else the referring website, else direct. Referrer comes from
                        the visit's page views via the visit id, so it only covers visits after
                        the visit id went live (2026-10-05).
  7. Clicks by maker  - per maker: clicks sent to their own site, week by week (this week and the
                        seven before; use --days 56 or more to see them all). The advertiser pitch.
  8. Maker reach      - per maker: how often they appeared in results/on pages, how many clicks that
                        produced and the click rate. "Appearances" counts a maker once per search or
                        page view in which they were shown.

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
    ("6. Outbound clicks per page by source", """
SELECT
  c.page_path,
  COALESCE(c.utm_source, v.referrer_host, '(direct)') AS source,
  COUNT(*) AS outbound_clicks
FROM ev c
LEFT JOIN (
  SELECT visit_id, ANY_VALUE(referrer_host) AS referrer_host
  FROM ev WHERE event_type = 'pageview' AND referrer_host IS NOT NULL AND visit_id IS NOT NULL
  GROUP BY visit_id
) v ON v.visit_id = c.visit_id
WHERE c.event_type = 'click'
GROUP BY 1, 2
ORDER BY outbound_clicks DESC
LIMIT 40
""", []),
    ("7. Clicks sent to each maker, by week (0 = this week)", """
SELECT
  brand,
  ANY_VALUE(brand_tier) AS tier,
  COUNT(*) AS clicks,
  COUNTIF(wk = 0) AS wk0, COUNTIF(wk = 1) AS wk1, COUNTIF(wk = 2) AS wk2, COUNTIF(wk = 3) AS wk3,
  COUNTIF(wk = 4) AS wk4, COUNTIF(wk = 5) AS wk5, COUNTIF(wk = 6) AS wk6, COUNTIF(wk = 7) AS wk7
FROM (
  SELECT brand, brand_tier,
         DATE_DIFF(CURRENT_DATE(), DATE(timestamp), WEEK(MONDAY)) AS wk
  FROM ev WHERE event_type = 'click' AND brand IS NOT NULL
)
GROUP BY brand
ORDER BY clicks DESC
LIMIT 50
""", []),

    ("8. Maker reach: appearances, clicks and click rate", """
, shown AS (
  SELECT JSON_VALUE(pair, '$[0]') AS brand, COUNT(*) AS appearances
  FROM ev, UNNEST(JSON_QUERY_ARRAY(result_brands)) AS pair
  WHERE event_type IN ('search', 'discover', 'pageview') AND result_brands IS NOT NULL
  GROUP BY 1
),
sent AS (
  SELECT brand, COUNT(*) AS clicks FROM ev
  WHERE event_type = 'click' AND brand IS NOT NULL GROUP BY brand
)
SELECT
  COALESCE(shown.brand, sent.brand) AS brand,
  COALESCE(shown.appearances, 0) AS appearances,
  COALESCE(sent.clicks, 0) AS clicks,
  ROUND(100 * SAFE_DIVIDE(COALESCE(sent.clicks, 0), shown.appearances), 2) AS click_pct
FROM shown FULL OUTER JOIN sent ON shown.brand = sent.brand
ORDER BY clicks DESC, appearances DESC
LIMIT 50
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
