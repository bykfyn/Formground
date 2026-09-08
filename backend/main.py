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

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from query_engine import discover, search

app = FastAPI(title="Formground")

# Allows the frontend (wherever it's hosted) to call this backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/search")
def human_search(q: str = Query(..., description="Natural language search query")):
    """Human-facing search. Returns a plain list of matching products."""
    results = search(q)
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
            "url": r["product_url"],
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


@app.get("/health")
def health():
    """Simple check that the backend is alive - useful for confirming
    a deployment worked."""
    return {"status": "ok"}
