"""
Formground analytics logging.

WHAT THIS DOES:
  Fire-and-forget event logging to BigQuery - two event types:
  "search" (the query text) and "click" (which brand/product got
  clicked through, and what query led there). No cookies, no user
  identifiers - just anonymous aggregate signal, matching the rest of
  the site's "no accounts, no tracking of individuals" stance. Feeds
  the eventual Phase 2 "how many people found you" brand-outreach
  summaries.

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
]

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
            _client.get_table(_table_id)
        except Exception:
            _client.create_table(bigquery.Table(_table_id, schema=SCHEMA))

        _ready = True
    except Exception as e:
        logger.warning(f"BigQuery not available, skipping analytics: {e}")


def log_event(event_type, query=None, brand=None, product_name=None):
    """Insert one event row. Never raises - a logging failure should
    never break a search or a click-through."""
    try:
        _ensure_ready()
        if not _ready:
            return
        row = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_type": event_type,
            "query": query,
            "brand": brand,
            "product_name": product_name,
        }
        errors = _client.insert_rows_json(_table_id, [row])
        if errors:
            logger.warning(f"BigQuery insert errors: {errors}")
    except Exception as e:
        logger.warning(f"Failed to log analytics event: {e}")
