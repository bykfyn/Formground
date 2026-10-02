"""
Formground analytics logging.

WHAT THIS DOES:
  Fire-and-forget event logging to BigQuery - "search" (the query
  text), "click" (which brand/product got clicked through, and what
  query led there), and "discover" (the shuffle chip). No cookies, no
  user identifiers - just anonymous aggregate signal, matching the
  rest of the site's "no accounts, no tracking of individuals" stance.
  Feeds the eventual Phase 2 "how many people found you" brand-
  outreach summaries.

  Optional utm_source/utm_medium/utm_campaign fields (2026-09-24)
  attribute an event to an ad campaign, for a paid-traffic test. These
  aren't a privacy step up from the above: a UTM value is identical
  for every visitor who clicked the same ad - it describes the
  campaign, not the person, the same way the query text describes the
  search, not the searcher. No new identifier, no session concept.

  Widened 2026-10-02 so the history exists before the Insights /
  demand-trend features are built (see project memory). Still no
  cookie, no user identifier, no session id: every added field
  describes a PAGE, a SEARCH or a MAKER, never a person.
    - per-maker traffic: "pageview" events (page_path, page_type,
      brand on a maker's own page) and `result_brands` - the makers
      shown by a search or listing page - for per-maker impressions;
    - query log: category/material/country/tier-filter the search was
      resolved to, result counts, a random per-SEARCH `search_id` echoed
      back on the click so a click joins to the exact search, `surface`
      (work / agent / discover);
    - maker classification: `brand_tier` / `brand_country` stamped
      server-side at event time (never client-supplied), so the
      established-vs-independent comparison stays correct retroactively
      even if a maker's tier changes later;
    - landing-page attribution: `page_path` (where it happened),
      `landing_page` (the first page of that browser tab's visit, held
      in sessionStorage - identical for everyone arriving the same
      way), `referrer_host`, `position`, `target_url`/`target_type`.

WHY BIGQUERY, NOT THE PRODUCT DATABASE:
  Cloud Run instances are ephemeral and scale to zero - writes to the
  SQLite file baked into the container image wouldn't persist past
  that instance's lifetime. BigQuery is a real, durable, separately-
  hosted store, and it's built for exactly this "insert events,
  aggregate them later" pattern - Firestore was considered and set
  aside specifically because its aggregation model doesn't hold up
  well once there's real volume across hundreds of brands, which is
  the scale this project is deliberately designed for.

FAILURE HANDLING:
  Analytics must never break the actual product. Every call here
  swallows its own errors (logged, not raised) - a BigQuery outage or
  a missing IAM grant should never turn a search or a click into a
  broken request.
"""

import logging
import time

from google.cloud import bigquery

logger = logging.getLogger("formground.analytics")

DATASET_ID = "formground_analytics"
TABLE_ID = "events"

SCHEMA = [
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("query", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("brand", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("product_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("utm_source", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("utm_medium", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("utm_campaign", "STRING", mode="NULLABLE"),
    # --- added 2026-10-02 (all nullable; old rows read back null) ---
    bigquery.SchemaField("page_path", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("page_type", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("landing_page", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("referrer_host", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("surface", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("search_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("category", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("material", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("intent_countries", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("tier_filter", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("total_matches", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("total_brands", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("result_count", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("result_brands", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("position", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("target_url", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("target_type", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("brand_tier", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("brand_country", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("brand_status", "STRING", mode="NULLABLE"),  # scraped / approved, added 2026-10-02
]

_SCHEMA_TYPES = {f.name: f.field_type for f in SCHEMA}
LEGACY_FIELDS = {"timestamp", "event_type", "query", "brand", "product_name",
                 "utm_source", "utm_medium", "utm_campaign"}
MAX_STRING = 500
MAX_RESULT_BRANDS = 8000   # a JSON array of [brand, tier] pairs
_live_fields = None        # columns the real table has (set by _ensure_ready)

_client = None
_table_id = None
_ready = False


def _ensure_ready():
    """
    Lazily creates the dataset/table on first use, rather than
    requiring a manual console setup step beyond the one IAM grant
    (BigQuery Data Editor) documented in project-docs. Idempotent -
    safe to call on every request, no-ops once already set up.
    """
    global _client, _table_id, _ready
    if _ready:
        return
    try:
        _client = bigquery.Client()
        dataset_ref = bigquery.DatasetReference(_client.project, DATASET_ID)
        try:
            _client.get_dataset(dataset_ref)
        except Exception:
            _client.create_dataset(bigquery.Dataset(dataset_ref))

        _table_id = f"{_client.project}.{DATASET_ID}.{TABLE_ID}"
        try:
            table = _client.get_table(_table_id)
        except Exception:
            table = None

        if table is None:
            _client.create_table(bigquery.Table(_table_id, schema=SCHEMA))
        else:
            # The real production table already existed before the
            # utm_* fields were added (2026-09-24) - SCHEMA alone only
            # governs a freshly created table, so an already-live table
            # needs its own widen-in-place step, the BigQuery equivalent
            # of scrape.py's "ALTER TABLE ADD COLUMN, swallow if it's
            # already there" SQLite migrations. Adding nullable columns
            # is a safe, backward-compatible change - existing rows just
            # read back with those fields null. Kept out of the
            # try/except above so a widen failure can't be mistaken for
            # a missing table and trigger a bogus create_table call.
            existing_names = {f.name for f in table.schema}
            missing = [f for f in SCHEMA if f.name not in existing_names]
            if missing:
                try:
                    table.schema = list(table.schema) + missing
                    table = _client.update_table(table, ["schema"])
                except Exception as widen_error:
                    # Widening must never switch ALL logging off: carry on
                    # with whichever columns the table really has.
                    logger.warning(f"Could not widen analytics table: {widen_error}")
            global _live_fields
            _live_fields = {f.name for f in table.schema}

        _ready = True
    except Exception as e:
        logger.warning(f"BigQuery not available, skipping analytics: {e}")


def build_row(event_type, fields, allowed=None, now=None):
    """Pure: the BigQuery row for one event. Keeps only schema columns
    (and only `allowed` ones - the columns the live table really has),
    truncates strings, coerces integers, drops empty values, and never
    lets a caller set `timestamp`/`event_type` through `fields`."""
    row = {
        "timestamp": now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event_type": event_type,
    }
    allowed = allowed if allowed is not None else set(_SCHEMA_TYPES)
    for name, value in fields.items():
        if name in ("timestamp", "event_type") or name not in _SCHEMA_TYPES or name not in allowed:
            continue
        if value is None or value == "":
            continue
        if _SCHEMA_TYPES[name] == "INTEGER":
            try:
                row[name] = int(value)
            except (TypeError, ValueError):
                continue
        else:
            limit = MAX_RESULT_BRANDS if name == "result_brands" else MAX_STRING
            row[name] = str(value)[:limit]
    return row


def log_event(event_type, query=None, brand=None, product_name=None,
              utm_source=None, utm_medium=None, utm_campaign=None, **extra):
    """Insert one event row. Never raises - a logging failure should
    never break a search or a click-through. `extra` carries the 2026-10-02
    dimensions (see SCHEMA); anything that is not a schema column is
    ignored."""
    try:
        _ensure_ready()
        if not _ready:
            return
        fields = {
            "query": query, "brand": brand, "product_name": product_name,
            "utm_source": utm_source, "utm_medium": utm_medium, "utm_campaign": utm_campaign,
            **extra,
        }
        row = build_row(event_type, fields, allowed=_live_fields)
        errors = _client.insert_rows_json(_table_id, [row])
        if errors:
            logger.warning(f"BigQuery insert errors: {errors}")
    except Exception as e:
        logger.warning(f"Failed to log analytics event: {e}")
