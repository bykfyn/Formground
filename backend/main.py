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

from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from analytics import log_event
from query_engine import discover, search

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
def human_search(q: str = Query(..., description="Natural language search query")):
    """Human-facing search. Returns a plain list of matching products."""
    results = search(q)
    log_event("search", query=q)
    return {"query": q, "results": results}


@app.get("/agent/search")
def agent_search(q: str = Query(..., description="Structured or natural language query from an agent")):
    """
    Agent-facing search. Same engine as /search, but shaped as
    schema.org Product objects for machine consumption.
    """
    results = search(q)
    shaped = [
        {
            "@type": "Product",
            "name": r["product_name"],
            "brand": {"@type": "Brand", "name": r["brand"]},
            # Falls back to the brand's homepage if check_links.py has
            # flagged this product page as a confirmed 404, so an agent
            # never gets handed a dead link between full scrapes.
            "url": r["brand_url"] if r["link_dead"] else r["product_url"],
            "category": r["category"],
        }
        for r in results
    ]
    return {"query": q, "results": shaped}


@app.get("/discover")
def discover_random():
    """Random browse across the whole catalog - no LLM call, no query,
    just a fair sample across every brand. Doesn't hit the LLM at all,
    so it's also free to call as often as someone hits "surprise me"."""
    return {"results": discover()}


@app.post("/event")
def track_event(payload: dict = Body(...)):
    """
    Click-tracking beacon - the frontend fires this (via
    navigator.sendBeacon, so it doesn't block the navigation to the
    maker's site) when a result card is clicked. No cookies, no
    per-visitor identifier - just which brand/product got clicked and
    what query led there, the same anonymous-aggregate shape as the
    search-event logging in /search.
    """
    log_event(
        "click",
        query=payload.get("query"),
        brand=payload.get("brand"),
        product_name=payload.get("product_name"),
    )
    return {"status": "ok"}


@app.get("/health")
def health():
    """Simple check that the backend is alive - useful for confirming
    a deployment worked."""
    return {"status": "ok"}
