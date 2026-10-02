"""
Formground backend.

WHAT THIS DOES:
  One small web app with three routes:
    - /search      the human ask-box hits this (returns results for display)
    - /agent/search   the agent-facing endpoint (returns schema.org
                       Product-shaped JSON, for AI agents querying on
                       someone's behalf)
    - /discover    random browse across the whole catalog, no query - for
                    the "surprise me" chip / typing "random" in the ask box

  /search and /agent/search use the exact same query engine underneath -
  "two surfaces, one engine," per the interface design already decided.

HOW TO RUN THIS LOCALLY (for testing):
    uvicorn main:app --reload

HOW THIS RUNS FOR REAL:
  Deployed to Google Cloud Run (serverless - no server to manage, costs
  close to nothing at low traffic).
"""

import json
from typing import Optional

from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from analytics import log_event
from query_engine import discover, search, search_full, search_more, shape_agent_product

app = FastAPI(title="Formground")

# Allows the frontend (wherever it's hosted) to call this backend.
# POST is needed alongside GET now for /event (the click-tracking
# beacon) - every other route is still read-only GET.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/search")
def human_search(
    q: str = Query(..., description="Natural language search query"),
    tier: Optional[str] = Query(None, description="'independent' or 'established' - the Work page's own chip filter, not part of the natural-language query"),
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_campaign: Optional[str] = None,
):
    """Human-facing search. Returns the fair, per-brand-capped list of
    matching products, plus the raw total_matches/total_brands counts
    and the resolved intent - the latter two exist for the "load more"
    button (see /search/more) so the results page can say how many real
    matches exist and so a "load more" click never re-runs the LLM
    translation step. `tier` rides along in the returned intent, so
    /search/more (which re-sends that same intent) honors it too with
    no extra query param needed there."""
    data = search_full(q, tier=tier)
    log_event("search", query=q, utm_source=utm_source, utm_medium=utm_medium, utm_campaign=utm_campaign)
    return {
        "query": q,
        "results": data["results"],
        "total_matches": data["total_matches"],
        "total_brands": data["total_brands"],
        "intent": data["intent"],
    }


@app.get("/search/more")
def human_search_more(
    q: str = Query(..., description="The same query the original /search call used"),
    intent: str = Query(..., description="The intent object /search returned, JSON-encoded"),
    exclude: str = Query("", description="Comma-separated ids of results already shown"),
):
    """Continuation of an existing /search call for the "load more"
    button. `intent` is exactly what /search's response already
    returned - passing it back here means this never re-hits the LLM,
    it just re-runs the same deterministic matching/ordering. Returns
    every remaining match in one response, round-robin ordered (see
    query_engine.round_robin_order) - the frontend reveals it in its
    own fixed-size chunks per click, no further requests needed."""
    parsed_intent = json.loads(intent)
    exclude_ids = [x for x in exclude.split(",") if x]
    results = search_more(q, parsed_intent, exclude_ids)
    log_event("load_more", query=q)
    return {"results": results}


@app.get("/agent/search")
def agent_search(q: str = Query(..., description="Structured or natural language query from an agent")):
    """
    Agent-facing search. Same engine as /search, but shaped as
    schema.org Product objects for machine consumption.
    """
    results = search(q)
    shaped = [shape_agent_product(r) for r in results]
    return {"query": q, "results": shaped}


@app.get("/discover")
def discover_random(
    tier: Optional[str] = Query(None, description="'independent' or 'established' - the Work page's own chip filter"),
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_campaign: Optional[str] = None,
):
    """Random browse across the whole catalog - no LLM call, no query,
    just a fair sample across every brand. Doesn't hit the LLM at all,
    so it's also free to call as often as someone hits "surprise me"."""
    results = discover(tier=tier)
    log_event("discover", utm_source=utm_source, utm_medium=utm_medium, utm_campaign=utm_campaign)
    return {"results": results}


@app.post("/event")
def track_event(payload: dict = Body(...)):
    """
    Click/share-tracking beacon - the frontend fires this (via
    navigator.sendBeacon, so it doesn't block the navigation to the
    maker's site) when a result card is clicked or its share button is
    used. event_type defaults to "click" (the original, only use of
    this endpoint) so existing callers keep working unchanged; the
    share button (2026-09-24) is the first caller to pass "share"
    explicitly. No cookies, no per-visitor identifier - just which
    brand/product and what query led there, the same anonymous-
    aggregate shape as the search-event logging in /search.
    """
    log_event(
        payload.get("event_type") or "click",
        query=payload.get("query"),
        brand=payload.get("brand"),
        product_name=payload.get("product_name"),
        utm_source=payload.get("utm_source"),
        utm_medium=payload.get("utm_medium"),
        utm_campaign=payload.get("utm_campaign"),
    )
    return {"status": "ok"}


@app.get("/health")
def health():
    """Simple check that the backend is alive - useful for confirming
    a deployment worked."""
    return {"status": "ok"}
