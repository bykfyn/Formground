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
import re
import secrets
from typing import Optional
from urllib.parse import urlsplit

from fastapi import Body, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from analytics import log_event
from query_engine import (
    BRAND_COUNTRIES, BRAND_TIERS, brand_status, discover, search, search_full, search_more, shape_agent_product,
)

AGENT_PRODUCT_SCHEMA = {
    "type": "object",
    "description": "A schema.org Product-shaped record. Optional fields are omitted, never null.",
    "required": ["@type", "name", "brand", "url", "category", "priceStatus", "tier"],
    "properties": {
        "@type": {"type": "string", "enum": ["Product"]},
        "name": {"type": "string"},
        "brand": {
            "type": "object",
            "properties": {"@type": {"type": "string", "enum": ["Brand"]}, "name": {"type": "string"}},
        },
        "url": {
            "type": "string", "format": "uri",
            "description": "The maker's own product page (Formground does not sell anything). "
                           "Falls back to the maker's homepage if the product page is confirmed dead.",
        },
        "category": {"type": "string", "description": "Product type tags as scraped/normalized, comma-separated; may be empty."},
        "priceStatus": {
            "type": "string",
            "enum": ["listed", "on_request", "dealer_priced", "unknown"],
            "description": "listed: price and currency are both known (see offers). on_request: the maker "
                           "prices on application or to commission - send an enquiry. dealer_priced: the maker "
                           "does not set a public price; stockists do. unknown: no price data, no claim made. "
                           "A missing price is often correct, not an error.",
        },
        "offers": {
            "type": "object",
            "description": "Present only when priceStatus is listed. The price exactly as the maker lists it, "
                           "in the maker's own currency - never converted or estimated.",
            "properties": {
                "@type": {"type": "string", "enum": ["Offer"]},
                "price": {"type": "string", "example": "415.00"},
                "priceCurrency": {"type": "string", "description": "ISO 4217 code", "example": "EUR"},
            },
        },
        "tier": {"type": "string", "enum": ["independent", "established"],
                 "description": "Hand-curated: established = well-known or multinational design house."},
        "image": {"type": "string", "format": "uri"},
        "material": {"type": "array", "items": {"type": "string"}, "description": "Material/finish options the maker lists."},
        "creator": {
            "type": "object", "description": "The designer, when the maker names one.",
            "properties": {"@type": {"type": "string", "enum": ["Person"]}, "name": {"type": "string"}},
        },
        "makerCountry": {"type": "string", "description": "Country of the maker's studio/business, when confirmed."},
    },
}

app = FastAPI(
    title="Formground",
    version="0.2.0",
    description=(
        "Formground indexes furniture, lighting and objects from makers and links every "
        "result straight to the maker's own site. /agent/search is the public, machine-readable search; "
        "the other routes serve the formground.com interface. No authentication; please keep request "
        "volume modest."
    ),
)

# Allows the frontend (wherever it's hosted) to call this backend.
# POST is needed alongside GET now for /event (the click-tracking
# beacon) - every other route is still read-only GET.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Analytics helpers (see analytics.py for what is logged and why)
# ---------------------------------------------------------------------------
BOT_UA_RE = re.compile(
    r"bot|crawl|spider|slurp|headless|preview|lighthouse|pagespeed|gtmetrix|uptime|monitor|curl|python-requests",
    re.I,
)


def _is_bot(request: Request) -> bool:
    """Crawlers that execute JS (Googlebot renders pages) would otherwise
    inflate page views. The user agent is only tested here, never stored."""
    return bool(BOT_UA_RE.search(request.headers.get("user-agent", "")))


def _brand_dims(brand):
    """Maker classification stamped at event time, server-side: a client
    can never set it, and later tier changes don't rewrite history."""
    if not brand:
        return {}
    return {
        "brand_tier": BRAND_TIERS.get(brand, "independent"),
        "brand_country": BRAND_COUNTRIES.get(brand),
        "brand_status": brand_status(brand),
    }


def _page_type(path):
    """Coarse page class from a URL path. The raw path is stored too, so a
    change to these rules can be re-applied to history."""
    path = (path or "").split("?")[0]
    if path in ("", "/", "/index.html"):
        return "home"
    # /work/<category>.html (furniture, lighting, objects) are the category pages; every other
    # /work/<x>.html is a type page. /browse/ is the pre-2026-10-04 address (kept so history
    # re-classifies the same way); /edits/<slug>.html are the Edit pages.
    if path.startswith("/work/new"):
        return "new"
    if path in ("/work/furniture.html", "/work/lighting.html", "/work/objects.html", "/work/houses.html", "/browse/", "/browse/index.html"):
        return "browse_hub"
    for prefix, kind in (("/brands/", "brand"), ("/work/", "browse"), ("/browse/", "browse"),
                         ("/edits/", "edit"), ("/designers/", "designer"), ("/architects/", "architect")):
        if path.startswith(prefix):
            return kind
    fixed = {
        "/work.html": "work", "/search.html": "work", "/marketplace.html": "marketplace",
        "/for-creators.html": "for_creators", "/edits.html": "edits_hub", "/new.html": "new",
        "/makers.html": "directory", "/designers.html": "directory", "/architects.html": "directory",
        "/creators.html": "directory", "/about.html": "info", "/contact.html": "info", "/privacy.html": "info",
    }
    return fixed.get(path, "edit_or_category")


# What a click-through lands on, by the kind of page it happened on.
_TARGET_TYPE_BY_PAGE = {"marketplace": "retailer", "for_creators": "creator_tool", "architect": "architect"}


def _result_brands_json(results):
    """[brand, tier] for each distinct maker in a result list, in order:
    what lets per-maker search impressions be counted later."""
    seen, out = set(), []
    for r in results:
        b = r.get("brand")
        if b and b not in seen:
            seen.add(b)
            out.append([b, BRAND_TIERS.get(b, "independent")])
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def _clean_path(value):
    """Path only - never a query string, so no stray parameter can leak in."""
    if not value:
        return None
    return urlsplit(str(value)).path[:300] or None


_VISIT_ID = re.compile(r"^[0-9a-f]{8,32}$")
_RATINGS = {"not_wanted", "close", "spot_on"}


def _is_internal(value):
    """True when the request says it comes from our own team's browser (?internal=1)."""
    return str(value or "").lower() in ("1", "true")


def _clean_visit(value):
    """The random per-tab visit id the browser sends, or None if it isn't one."""
    value = str(value or "").lower()
    return value if _VISIT_ID.match(value) else None


def _intent_fields(intent):
    countries = intent.get("countries") or []
    return {
        "category": intent.get("category"),
        "material": intent.get("material"),
        "intent_countries": ",".join(countries) if countries else None,
        "tier_filter": intent.get("tier"),
    }


@app.get("/search")
def human_search(
    q: str = Query(..., description="Natural language search query"),
    tier: Optional[str] = Query(None, description="'independent' or 'established' - the Work page's own chip filter, not part of the natural-language query"),
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_campaign: Optional[str] = None,
    utm_content: Optional[str] = None,
    landing_page: Optional[str] = None,
    page_path: Optional[str] = None,
    visit_id: Optional[str] = None,
    internal: Optional[str] = None,
    request: Request = None,
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
    # A random id for THIS search only (not a person or a session): echoed
    # back on the click so a click-through joins to the exact search.
    search_id = secrets.token_hex(6)
    if not _is_bot(request) and not _is_internal(internal):
        log_event(
            "search", query=q, utm_source=utm_source, utm_medium=utm_medium, utm_campaign=utm_campaign, utm_content=utm_content,
            surface="work", search_id=search_id, landing_page=_clean_path(landing_page),
            page_path=_clean_path(page_path), visit_id=_clean_visit(visit_id), total_matches=data["total_matches"],
            total_brands=data["total_brands"], result_count=len(data["results"]),
            result_brands=_result_brands_json(data["results"]), **_intent_fields(data["intent"]),
        )
    return {
        "query": q,
        "search_id": search_id,
        "results": data["results"],
        "total_matches": data["total_matches"],
        "total_brands": data["total_brands"],
        "intent": data["intent"],
        "brand_links": data.get("brand_links", []),
    }


@app.get("/search/more")
def human_search_more(
    q: str = Query(..., description="The same query the original /search call used"),
    intent: str = Query(..., description="The intent object /search returned, JSON-encoded"),
    exclude: str = Query("", description="Comma-separated ids of results already shown"),
    search_id: Optional[str] = None,
    visit_id: Optional[str] = None,
    internal: Optional[str] = None,
    request: Request = None,
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
    if not _is_bot(request) and not _is_internal(internal):
        log_event("load_more", query=q, search_id=search_id, visit_id=_clean_visit(visit_id), surface="work",
                  result_count=len(results), **_intent_fields(parsed_intent))
    return {"results": results}


@app.get(
    "/agent/search",
    summary="Search products from makers",
    tags=["agents"],
    responses={200: {
        "description": "Matching products, brand-balanced so no single maker dominates.",
        "content": {"application/json": {"schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "results": {"type": "array", "items": AGENT_PRODUCT_SCHEMA},
            },
        }}},
    }},
)
def agent_search(q: str = Query(..., description="Natural-language query, e.g. 'oak dining table', 'two seater sofa', 'Swedish pendant lamp'. Product type, material, colour, maker country and seat count are understood.", examples=["round dining table"])):
    """
    Agent-facing search. Same engine as /search, but shaped as
    schema.org Product objects for machine consumption.
    """
    data = search_full(q)
    results = data["results"]
    # Agent queries are real demand signal too - logged like human ones,
    # on their own `surface`. Not bot-filtered: agents ARE the audience.
    log_event(
        "search", query=q, surface="agent", search_id=secrets.token_hex(6),
        total_matches=data["total_matches"], total_brands=data["total_brands"],
        result_count=len(results), result_brands=_result_brands_json(results),
        **_intent_fields(data["intent"]),
    )
    shaped = [shape_agent_product(r) for r in results]
    return {"query": q, "results": shaped}


@app.get("/discover")
def discover_random(
    tier: Optional[str] = Query(None, description="'independent' or 'established' - the Work page's own chip filter"),
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_campaign: Optional[str] = None,
    utm_content: Optional[str] = None,
    landing_page: Optional[str] = None,
    page_path: Optional[str] = None,
    visit_id: Optional[str] = None,
    internal: Optional[str] = None,
    request: Request = None,
):
    """Random browse across the whole catalog - no LLM call, no query,
    just a fair sample across every brand. Doesn't hit the LLM at all,
    so it's also free to call as often as someone hits "surprise me"."""
    results = discover(tier=tier)
    search_id = secrets.token_hex(6)
    if not _is_bot(request) and not _is_internal(internal):
        log_event(
            "discover", utm_source=utm_source, utm_medium=utm_medium, utm_campaign=utm_campaign, utm_content=utm_content,
            surface="discover", search_id=search_id, landing_page=_clean_path(landing_page),
            page_path=_clean_path(page_path), visit_id=_clean_visit(visit_id), tier_filter=tier, result_count=len(results),
            result_brands=_result_brands_json(results),
        )
    return {"search_id": search_id, "results": results}


@app.post("/event", include_in_schema=False)
def track_event(request: Request, payload: dict = Body(...)):
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
    if _is_bot(request) or _is_internal(payload.get("internal")):
        return {"status": "ok"}
    event_type = payload.get("event_type") or "click"
    page_path = _clean_path(payload.get("page_path"))
    page_type = _page_type(page_path) if page_path else None
    brand = payload.get("brand")
    result_brands = payload.get("result_brands")
    if isinstance(result_brands, list):
        # a pageview lists the makers shown on the page (names from the
        # client); the tier is looked up here, never taken from the client
        result_brands = json.dumps(
            [[b, BRAND_TIERS.get(b, "independent")] for b in dict.fromkeys(result_brands) if isinstance(b, str)],
            ensure_ascii=False, separators=(",", ":"),
        )
    target_url = payload.get("target_url")
    if target_url:
        parts = urlsplit(str(target_url))
        target_url = f"{parts.scheme}://{parts.netloc}{parts.path}"  # never the query string
    log_event(
        event_type,
        query=payload.get("query"),
        brand=brand,
        product_name=payload.get("product_name"),
        utm_source=payload.get("utm_source"),
        utm_medium=payload.get("utm_medium"),
        utm_campaign=payload.get("utm_campaign"),
        utm_content=payload.get("utm_content"),
        page_path=page_path,
        page_type=page_type,
        landing_page=_clean_path(payload.get("landing_page")),
        referrer_host=(payload.get("referrer_host") or None),
        search_id=payload.get("search_id"),
        visit_id=_clean_visit(payload.get("visit_id")),
        rating=(payload.get("rating") if event_type == "feedback" and payload.get("rating") in _RATINGS else None),
        surface=payload.get("surface"),
        position=payload.get("position"),
        result_brands=result_brands,
        result_count=payload.get("result_count"),
        target_url=target_url,
        target_type=(
            payload.get("target_type")
            or (_TARGET_TYPE_BY_PAGE.get(page_type, "maker") if event_type == "click" else None)
        ),
        **_brand_dims(brand),
    )
    return {"status": "ok"}


@app.get("/health")
def health():
    """Simple check that the backend is alive - useful for confirming
    a deployment worked."""
    return {"status": "ok"}
