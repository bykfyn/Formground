"""
Query engine.

WHAT THIS DOES:
  Takes a raw search - either a messy human sentence ("a warm-toned side
  table, something sculptural") or a structured request from an AI agent -
  and turns it into the same intermediate form before matching it against
  the stored product data. This is the "two surfaces, one engine" design:
  humans and agents both go through this same translation step.

HOW IT WORKS:
  1. Send the raw query to an LLM, asking it to extract structured intent
     (category, material, style descriptors) as JSON.
  2. Filter stored products on the hard facts: category + material.
  3. Among that filtered set, narrow further by style descriptors
     (e.g. "globe", "round") when doing so still leaves real matches
     (see _narrow_by_style) - these are judgment calls, so they're
     never stored as permanent tags, only matched at query time.

SWAPPING THE LLM PROVIDER/MODEL (e.g. to cut cost):
  Set these environment variables - no code changes needed:
    LLM_PROVIDER   "anthropic" (default) or "openai"
    LLM_MODEL      overrides the default for whichever provider is
                   selected (see DEFAULT_MODELS below) - e.g. a cheaper
                   or faster model, since this is a small structured-
                   extraction task (a few hundred tokens) that doesn't
                   need a top-tier model to do well.
    ANTHROPIC_API_KEY / OPENAI_API_KEY   whichever matches LLM_PROVIDER.
"""

import copy
import datetime
import hashlib
import json
import os
import random
import re
import sqlite3
import threading
import unicodedata
from pathlib import Path

import requests
from dotenv import load_dotenv

# Picks up backend/.env locally if present (see .env.example) - does
# nothing if there's no .env file, so this is a no-op in production
# environments (Cloud Run etc.) that set real environment variables directly.
load_dotenv()

DB_PATH = Path(__file__).parent.parent / "data" / "formground.db"
BRANDS_PATH = Path(__file__).parent.parent / "scraper" / "brands.json"
HOUSES_PATH = Path(__file__).parent.parent / "data" / "houses.json"

# Words that mean "the user is looking for a house," not a product - the
# LLM already extracts category as a free string (no fixed enum), so a
# query like "a minimalist house in Sweden" already comes back with
# category="house" today without any prompt change. This is the other
# half: which extracted categories should route to houses.json instead
# of (or alongside) the products table. Deliberately narrow - a real
# house is what data/houses.json actually has; "home" is included since
# it's a common way to say the same thing ("a modern family home").
HOUSE_CATEGORY_WORDS = {"house", "houses", "villa", "villas", "home", "homes"}

# The homepage's category tiles send the bare umbrella word itself
# ("furniture", "objects", ...) as the whole query. Confirmed live
# 2026-09-20, two separate LLM failure modes for these single-word
# queries: (1) category often comes back null (too generic to pick a
# specific object type like 'chair'), which skips the category filter
# in filter_products() entirely and returns the whole unfiltered
# catalog; (2) for "ceramics" specifically, the LLM sometimes echoes the
# same word into BOTH category and material - and since filter_products()
# correctly ANDs those two together for a real compound query like
# "black chair", that redundant double-encoding of one single-word query
# was cutting real results down to a handful. A bare word from this set
# means "browse this whole category," never "and also match this as a
# material/color" - so search() below replaces the LLM's intent outright
# for these, rather than patching just the missing-category case.
#
# A dict, not a set, mapping each recognized word to its canonical
# English umbrella value (what filter_products()/_category_matches()'s
# HYPERNYM_WORDS actually expect) - added Swedish equivalents
# 2026-09-29 (campaign rebuilt Swedish-first): bare "möbler" ("furniture")
# was falling through to the same null-category/whole-catalog bug this
# dict was built to fix for English, since it wasn't recognized as an
# umbrella word at all. Mapping to the canonical value (not the matched
# word itself) means "möbler" sets category="furniture", not the literal
# Swedish string, so it reaches _category_matches with a value it
# already knows how to expand.
BROWSE_CATEGORY_WORDS = {
    "furniture": "furniture", "möbler": "furniture",
    "lighting": "lighting", "belysning": "lighting",
    "ceramics": "ceramics", "keramik": "ceramics",
    "objects": "objects", "object": "objects", "föremål": "objects",
}

# Duplicated from scraper/generate_brand_pages.py's own
# NEW_ARRIVALS_WINDOW_DAYS, not imported - the Cloud Run Docker image
# only ships backend/, data/, and the single file scraper/brands.json
# (see the Dockerfile's own comment on why), so generate_brand_pages.py
# is never present in production. Keep this value in sync with that
# file's if it ever changes - same cross-boundary-constant pattern
# already accepted there for brands.json itself.
NEW_ARRIVALS_WINDOW_DAYS = 90

# Phrases checked before the bare word "new" itself, so "new arrivals"
# doesn't also need "arrivals" to independently mean anything.
NEW_ARRIVAL_PHRASES = ("new arrivals", "newly added", "recently added")


def _wants_new_arrivals(stripped_query: str) -> bool:
    """
    True when the query is asking for recently-added items (2026-09-28)
    - "new", "new chairs", "new arrivals", "recently added" - not a
    product that literally happens to be named "New" something (no real
    product in this catalog is, but the same word-boundary care
    GENERIC_PRODUCT_NAMES already takes elsewhere applies here too).
    Checked as its own function so _resolve_intent's own logic stays
    readable and this one rule is independently testable.
    """
    if any(phrase in stripped_query for phrase in NEW_ARRIVAL_PHRASES):
        return True
    return bool(re.search(r"\bnew\b", stripped_query))


def _load_hidden_brands() -> set:
    """
    A brand marked "hidden": true in brands.json keeps being scraped
    and its data stays in the database (so it's ready to switch back on
    later), but is excluded from every surface here - search, name
    matching, and discover. Distinct from "scrapable": false, which
    only stops future scraping and does nothing about data already in
    the database - "hidden" is for a brand you want to pause showing
    without losing its data or its place in the scrape schedule, e.g.
    a design direction that no longer fits well next to the others
    right now, as opposed to a permanent remove-on-request case (which
    just deletes the brand's rows outright).
    """
    try:
        brands = json.loads(BRANDS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
    return {b["name"] for b in brands if b.get("hidden")}


HIDDEN_BRANDS = _load_hidden_brands()


def _load_brand_countries() -> dict:
    """
    Brand -> country, same source and same "only ever present when
    genuinely confirmed, never guessed" discipline as
    generate_brand_pages.py's own load_countries() (duplicated, not
    imported - see that function's docstring; the Docker image ships
    scraper/brands.json but never generate_brand_pages.py itself, same
    boundary already documented for NEW_ARRIVALS_WINDOW_DAYS above).
    Reads the same BRANDS_PATH file HIDDEN_BRANDS already reads, just a
    second field off the same records.
    """
    try:
        brands = json.loads(BRANDS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {b["name"]: b["country"] for b in brands if b.get("country")}


BRAND_COUNTRIES = _load_brand_countries()


def _load_brand_tiers() -> dict:
    """
    Brand -> "established", same source/shape as BRAND_COUNTRIES above.
    "established" is only ever set by hand in brands.json (2026-09-30,
    same 39-brand list generate_brand_pages.py's makers.html filter
    uses) for a genuinely well-known/multinational/legacy design house,
    or a brand added specifically to fill a paid-ad keyword gap rather
    than as an independent-maker pick - never inferred from catalog
    size. A brand with no "tier" field (the norm, not the exception) is
    "independent" by default - see filter_products()'s own use of this
    dict for where that default is applied.
    """
    try:
        brands = json.loads(BRANDS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {b["name"]: "established" for b in brands if b.get("tier") == "established"}


BRAND_TIERS = _load_brand_tiers()


def _load_brand_pricing() -> dict:
    """
    Brand -> "on_request" or "dealer_priced", from the optional "pricing"
    field in brands.json (same source/shape as BRAND_COUNTRIES). A missing
    price is often the CORRECT data: some makers price on application or
    build to commission, and others sell only through dealers who set the
    price (73 of 219 brands had no stored price at all, 2026-10-02). A
    brand with no field makes no claim - its products are "listed" when
    they carry a price and verified currency, otherwise "unknown". Never
    inferred from the absence of a price.
    """
    try:
        brands = json.loads(BRANDS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {b["name"]: b["pricing"] for b in brands if b.get("pricing") in ("on_request", "dealer_priced")}


BRAND_PRICING = _load_brand_pricing()


# A maker's listing state in the Sheerd repository model (2026-10-02 strategy
# session): "scraped" - collected from the maker's public site, the state of
# every brand today - or "approved" - the maker's listing has been verified
# and approved (free self-serve approval via a back-office diagnostic, paid
# tiers above it, later). "Shown on Formground" is a separate, third state
# that already exists as the `hidden` flag above (a brand is shown unless
# hidden), so it is not duplicated here. Stored as the optional "status"
# field in brands.json; absence means "scraped". Built ahead of use: nothing
# sets "approved" yet, it is stamped on analytics events so the history
# accumulates, and it is deliberately NOT in the public /agent/search payload
# or docs until the approval mechanism is real.
BRAND_STATUS_VALUES = ("scraped", "approved")


def _load_brand_status() -> dict:
    """Brand -> "approved", for the (currently empty) set of approved
    brands. Anything else, including a typo, stays "scraped": a value is
    only ever promoted by writing exactly "approved"."""
    try:
        brands = json.loads(BRANDS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {b["name"]: "approved" for b in brands if b.get("status") == "approved"}


BRAND_STATUS = _load_brand_status()


def brand_status(brand: str) -> str:
    """"approved" or "scraped" - see BRAND_STATUS_VALUES."""
    return BRAND_STATUS.get(brand, "scraped")


def price_status(product: dict) -> str:
    """"listed" (price AND currency stored), "on_request", "dealer_priced",
    or "unknown". A product-level price always wins over a brand-level
    status, and a price without a verified currency is not "listed"."""
    if product.get("price") and product.get("currency"):
        return "listed"
    return BRAND_PRICING.get(product["brand"], "unknown")


def shape_agent_product(r: dict) -> dict:
    """One search result as the schema.org-Product-shaped object
    /agent/search returns. An Offer appears only when price and currency
    are both stored (never a guessed currency, never a converted price);
    priceStatus says why there is no Offer otherwise. Optional fields are
    omitted rather than null so an agent only sees what is real."""
    out = {
        "@type": "Product",
        "name": r["product_name"],
        "brand": {"@type": "Brand", "name": r["brand"]},
        # Falls back to the brand's homepage if check_links.py has
        # flagged this product page as a confirmed 404, so an agent
        # never gets handed a dead link between full scrapes.
        "url": r["brand_url"] if r.get("link_dead") else r["product_url"],
        "category": r["category"],
        "priceStatus": price_status(r),
        "tier": BRAND_TIERS.get(r["brand"], "independent"),
    }
    if r.get("image_url"):
        out["image"] = r["image_url"]
    if out["priceStatus"] == "listed":
        out["offers"] = {"@type": "Offer", "price": f'{r["price"]:.2f}', "priceCurrency": r["currency"]}
    materials = r.get("material_options")
    if isinstance(materials, str):
        try:
            materials = json.loads(materials or "[]")
        except ValueError:
            materials = []
    if materials:
        out["material"] = materials
    if r.get("designer"):
        out["creator"] = {"@type": "Person", "name": r["designer"]}
    if BRAND_COUNTRIES.get(r["brand"]):
        out["makerCountry"] = BRAND_COUNTRIES[r["brand"]]
    return out

# Real country values confirmed present in brands.json as of 2026-09-28
# (see BRAND_COUNTRIES) mapped from how someone actually asks for them -
# a region/demonym is not a literal country name, so this needs its own
# small lookup rather than relying on the LLM to reliably resolve
# "Scandinavian" to a set of real countries on its own (same class of
# LLM-reliability gap already found and fixed for umbrella category
# words and "new" - see _resolve_intent's own docstring). Deliberately
# only covers terms with real, confirmed brand data behind them today;
# extend this dict, not a new mechanism, as more countries get real
# brand coverage.
GEOGRAPHY_GROUPS = {
    "scandinavia": {"Sweden", "Denmark", "Norway"},
    "scandinavian": {"Sweden", "Denmark", "Norway"},
    "nordic": {"Sweden", "Denmark", "Norway", "Finland"},
    "sweden": {"Sweden"}, "swedish": {"Sweden"},
    "denmark": {"Denmark"}, "danish": {"Denmark"},
    "norway": {"Norway"}, "norwegian": {"Norway"},
    "finland": {"Finland"}, "finnish": {"Finland"},
    "italy": {"Italy"}, "italian": {"Italy"},
    "france": {"France"}, "french": {"France"},
    # Swedish-language forms (2026-09-29, campaign rebuilt Swedish-first -
    # keyword research showed "skandinaviskt matbord" has real volume but
    # returned the same count as bare "matbord", i.e. no geography filter
    # was applying at all). Swedish adjectives inflect by the noun's
    # gender/number (en/ett-word, singular/plural) - all confirmed common,
    # neuter, and plural/definite forms included, same as "scandinavian"
    # alone already covers only the one English form needed.
    "skandinavien": {"Sweden", "Denmark", "Norway"},
    "skandinavisk": {"Sweden", "Denmark", "Norway"},
    "skandinaviskt": {"Sweden", "Denmark", "Norway"},
    "skandinaviska": {"Sweden", "Denmark", "Norway"},
    "norden": {"Sweden", "Denmark", "Norway", "Finland"},
    "nordisk": {"Sweden", "Denmark", "Norway", "Finland"},
    "nordiskt": {"Sweden", "Denmark", "Norway", "Finland"},
    "nordiska": {"Sweden", "Denmark", "Norway", "Finland"},
    "sverige": {"Sweden"}, "svensk": {"Sweden"}, "svenskt": {"Sweden"}, "svenska": {"Sweden"},
    "danmark": {"Denmark"}, "dansk": {"Denmark"}, "danskt": {"Denmark"}, "danska": {"Denmark"},
    "norge": {"Norway"}, "norsk": {"Norway"}, "norskt": {"Norway"}, "norska": {"Norway"},
    "finskt": {"Finland"}, "finska": {"Finland"}, "finsk": {"Finland"},
}


def _wanted_countries(stripped_query: str, llm_location) -> set:
    """
    Real countries (matching BRAND_COUNTRIES' own values) a query is
    asking for - combines deterministic region/demonym word-matching
    (the part the LLM can't be trusted to resolve on its own, same as
    the umbrella-category and "new" fixes) with the LLM's own
    `location` field when it directly names a known country/demonym
    already in GEOGRAPHY_GROUPS (covers the simple "a chair from
    Sweden" case, where the LLM's existing location extraction already
    works fine).
    """
    countries = set()
    for word in re.findall(r"[a-zà-ÿ]+", stripped_query):
        if word in GEOGRAPHY_GROUPS:
            countries |= GEOGRAPHY_GROUPS[word]
    if llm_location and isinstance(llm_location, str):
        loc = llm_location.strip().lower()
        if loc in GEOGRAPHY_GROUPS:
            countries |= GEOGRAPHY_GROUPS[loc]
    return countries


# Real seat-count phrasing confirmed live in product names (2026-09-28,
# ad keyword research for "two seater sofa"/"three seater sofa"): both
# digit and word forms appear across real brands - "2-seater" (31),
# "3 seater" (30), "two seater" (30), "3-seater" (25), "three seater"
# (21), "one seater" (20), "5-seater"/"5 seater" (34 combined), "4
# seater"/"4-seater" (15 combined), "1-seater"/"1 seater" (10 combined).
# No product uses bare "seat" without "-er" in its own name - but a
# real searcher does sometimes type "two seat sofa" rather than "two
# seater sofa" (confirmed live 2026-09-29: it returned only 4 results,
# same small count "two seater" itself used to return before this
# whole feature existed). The "-er" stays optional in this QUERY-side
# pattern for that reason, even though it's never optional in
# _product_matches_seat_count's product-name check below - a search
# for "two seat" should still match a product literally named "Two
# Seater Sofa". A seat count is a real, literal fact embedded in a
# product's own name, not a structured database column - the same
# "read it from the name, don't invent a new field" approach
# GENERIC_PRODUCT_NAMES/filter_by_name already use elsewhere, just
# applied via a dedicated hard filter here since a plain name-substring
# search (filter_by_name) already confirmed live to under-match it
# (only 4 of 56 real "two seater" matches).
SEAT_COUNT_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
SEAT_COUNT_NUMBER_WORDS = {v: k for k, v in SEAT_COUNT_WORDS.items()}
SEAT_COUNT_PATTERN = re.compile(r"\b(\d+|one|two|three|four|five|six)[\s-]?seat(?:er)?s?\b", re.IGNORECASE)

# Swedish seat-count phrasing (2026-09-29, campaign rebuilt Swedish-first):
# "tvåsits"/"2-sits" is the real Swedish furniture term for a seat count
# (literally "two-seat") - "tvåsits soffa" returned 0 results before this,
# since only the English pattern above was ever recognized. Kept as its
# own dict/pattern rather than merged into SEAT_COUNT_WORDS above:
# product names in this catalog are in English, so
# _product_matches_seat_count's reverse int->word lookup
# (SEAT_COUNT_NUMBER_WORDS) must stay English-only regardless of which
# language the query itself arrived in.
SWEDISH_SEAT_COUNT_WORDS = {"en": 1, "två": 2, "tre": 3, "fyra": 4, "fem": 5, "sex": 6}
SWEDISH_SEAT_COUNT_PATTERN = re.compile(r"\b(\d+|en|två|tre|fyra|fem|sex)[\s-]?sits\b", re.IGNORECASE)


def _wanted_seat_count(stripped_query: str):
    """
    A seat count ("two seater", "2-seater", "3 seat sofa", or the
    Swedish "tvåsits"/"2-sits") a query is asking for, or None. Digit
    and word forms both recognized in either language, matching the
    real variety already confirmed in the data (see above) - the LLM's
    own style_descriptors handling can't be trusted to extract this
    reliably or consistently (same LLM-reliability gap as every other
    deterministic fix today), and even when it does, a bare
    substring/style-descriptor match against product names is too
    fragile (confirmed: filter_by_name("two seater sofa") finds only 4
    of the 56 real matches).
    """
    m = SEAT_COUNT_PATTERN.search(stripped_query)
    if m:
        token = m.group(1).lower()
        return int(token) if token.isdigit() else SEAT_COUNT_WORDS.get(token)
    m = SWEDISH_SEAT_COUNT_PATTERN.search(stripped_query)
    if m:
        token = m.group(1).lower()
        return int(token) if token.isdigit() else SWEDISH_SEAT_COUNT_WORDS.get(token)
    return None


def _product_matches_seat_count(product_name: str, seat_count: int) -> bool:
    """True if a product's own name literally states this seat count,
    in either digit or word form (see SEAT_COUNT_NUMBER_WORDS)."""
    number_word = SEAT_COUNT_NUMBER_WORDS.get(seat_count)
    alternatives = "|".join(str(a) for a in (seat_count, number_word) if a is not None)
    return bool(re.search(rf"\b({alternatives})[\s-]?seaters?\b", product_name, re.IGNORECASE))


# Real, reliable naming convention confirmed live 2026-09-29 (ad keyword
# research for "uppladdningsbar bordslampa"/"portabel bordslampa" -
# cordless/rechargeable table lamps, among the cheapest-CPC terms
# researched): 28 real table lamps across 6 brands (New Works DK,
# 101cph, In Common With, Audo, Porta Romana, Louise Roe) literally say
# "Portable" in their own product name - the lighting industry's own
# established term for a cordless/battery lamp, same shape as the seat-
# count fact above (a real fact embedded in the name, not a structured
# database column - no separate battery/power-source field exists).
# Query-side recognition covers English and Swedish search terms; the
# product-name check itself only ever needs to look for the English
# word "Portable", since that's the term real brands actually use in
# this catalog regardless of what language the query arrived in - same
# principle as SWEDISH_SEAT_COUNT_PATTERN feeding into an English-only
# product-name check.
PORTABLE_LAMP_WORDS = {
    "portable", "cordless", "rechargeable", "battery",
    "uppladdningsbar", "portabel", "sladdlös", "batteridriven",
}


def _wants_portable(stripped_query: str) -> bool:
    """True when the query is asking for a cordless/rechargeable/
    portable lamp, in English or Swedish (see PORTABLE_LAMP_WORDS)."""
    words = set(re.findall(r"[a-zà-ÿ]+", stripped_query))
    return bool(words & PORTABLE_LAMP_WORDS)


def _product_is_portable(product_name: str) -> bool:
    """True if a product's own name literally says "Portable" - the
    real, confirmed naming convention this catalog's brands already use
    for cordless/rechargeable lamps (see PORTABLE_LAMP_WORDS above)."""
    return bool(re.search(r"\bportable\b", product_name, re.IGNORECASE))


LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")

# These are settings to revisit occasionally, not set-once values - model
# names get renamed/deprecated and cheaper or better options appear over
# time. Before assuming these are still right, check that the name below
# still exists and is still the best cost/quality tradeoff for this task
# (a small structured-extraction call, not one that needs a top-tier model).
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",  # small structured-extraction task, doesn't need a bigger model
    "openai": "gpt-4o-mini",
}
LLM_MODEL = os.environ.get("LLM_MODEL", DEFAULT_MODELS.get(LLM_PROVIDER, ""))

# Set these as environment variables - never hardcode an API key in the file.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


# One keep-alive session for LLM calls: no new TLS handshake per search.
_HTTP = requests.Session()


def _call_anthropic(system_prompt: str, raw_query: str) -> str:
    response = _HTTP.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "max_tokens": 300,
            "system": system_prompt,
            "messages": [{"role": "user", "content": raw_query}],
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


def _call_openai(system_prompt: str, raw_query: str) -> str:
    response = _HTTP.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "content-type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "max_tokens": 300,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_query},
            ],
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# Add a new provider by writing one function like the two above (raw
# query + system prompt in, raw text out) and registering it here -
# nothing else in this file needs to change.
LLM_CALLERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}

# A brand with a large real catalog (In Common With has ~550 products vs.
# Kieran Kinsella's 6) could otherwise fill an entire results page by
# itself. Capping keeps that from "smothering" smaller makers who might be
# just as relevant a match. Raised from 3 to 6 (2026-09-08) after
# checking real query data: a broad query like "chunky table" had 59 raw
# matches across 5 brands but only showed 15 at cap=3 - the cap, not
# data scarcity, was the actual bottleneck for broad queries. Still easy
# to retune from here once there's real usage to test against.
MAX_RESULTS_PER_BRAND = 6

# Random discovery (see discover() below) uses a higher per-brand cap than
# a real search - there's no relevance signal being diluted here, just an
# even browse across brands, so it's fine to show more per brand while
# still giving every brand a genuinely equal shot at appearing.
DISCOVER_PER_BRAND = 6

# A per-brand cap alone no longer bounds the page length now that there are
# ~50+ scrapable brands - up to 300+ results forced an endless scroll for
# what's meant to be a quick "surprise me" browse. Capped at a fixed total
# instead so the whole result fits within a modest scroll; hitting
# "Surprise me" again re-samples a fresh, different set rather than
# needing to scroll through everything at once. Raised from the original
# 24 (2026-09-12) once the frontend gained its own trim-to-full-row logic
# (see renderResults' trimToFullRows) - this number no longer needs to be
# a common multiple of likely column counts itself, since the actual
# rendered column count is measured and trimmed to client-side; this is
# just "how big a pool is worth fetching for one browse."
DISCOVER_TOTAL_CAP = 30

# Houses are part of Work, so "Surprise me" includes them (2026-10-04) - but there are only ~430 against ~28,000
# products, so they appear sparingly: each browse gets 1 to DISCOVER_HOUSES_MAX houses, every one from a different
# practice (a practice is the "brand" of a house, same fairness rule as products), inside the same total cap.
# Not offered under the Independent / Established chips: those filter makers, and a practice has no tier.
DISCOVER_HOUSES_MAX = 3


_TRANSLATE_SYSTEM_PROMPT = (
    "You translate a search query about independent design - furniture/"
    "lighting/ceramics/objects, or an architect-designed house - into "
    "structured JSON with these fields: "
    "category (string or null - the object type, e.g. 'chair', 'lamp', "
    "'house'. If the query names a specific PLACEMENT OR FUNCTION "
    "subtype, keep the full two-word phrase instead of reducing it to "
    "the bare noun - e.g. 'table lamp' stays 'table lamp', not 'lamp'; "
    "'floor lamp' stays 'floor lamp', not 'lamp'; 'dining chair' stays "
    "'dining chair', not 'chair'; 'coffee table' stays 'coffee table', "
    "not 'table'. But if the modifier instead describes SHAPE, "
    "MATERIAL, or another style trait (e.g. 'ball lamp', 'round table', "
    "'globe lamp', 'oval table'), use only the bare noun for category "
    "('lamp', 'table') and put the shape/material word in "
    "style_descriptors instead - do NOT invent a compound category "
    "that isn't a real placement/function subtype. Only use the bare "
    "noun with no style_descriptors when the query has no modifier at "
    "all, e.g. a query that's just 'lamp' or 'chair'), "
    "material (string or null), "
    "style_descriptors (list of strings, e.g. ['minimalist', 'linear', "
    "'ball', 'round', 'globe']), "
    "color (string or null), "
    "location (string or null, e.g. 'Sweden', 'Stockholm' - only set this "
    "when the query names a real place, mainly relevant for house queries). "
    "Respond ONLY with the JSON object, nothing else."
)


def translate_query(raw_query: str) -> dict:
    """
    Sends the raw query to whichever LLM is configured (see LLM_PROVIDER/
    LLM_MODEL above) and gets back structured intent. Works the same
    whether raw_query came from a human typing in the ask-box or an
    agent's structured request converted to text.

    The reading of a query never changes for a given model and prompt, so it is
    remembered (2026-10-04): identical queries skip the ~1s LLM call entirely.
    A prepared set of common queries ships in intent_cache.json (built by
    build_intent_cache.py) so even a freshly started server answers them
    instantly; anything new is learned in memory as it is asked.
    """
    key = _normalise_query(raw_query)
    cached = _intent_cache_get(key)
    if cached is not None:
        return cached

    caller = LLM_CALLERS.get(LLM_PROVIDER)
    if caller is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}' - supported: {list(LLM_CALLERS)}"
        )

    text = caller(_TRANSLATE_SYSTEM_PROMPT, raw_query)
    text = text.replace("```json", "").replace("```", "").strip()
    intent = json.loads(text)
    _intent_cache_put(key, intent)
    return copy.deepcopy(intent)


def _normalise_query(raw_query: str) -> str:
    return " ".join((raw_query or "").lower().split())


_PROMPT_HASH = hashlib.sha1(_TRANSLATE_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12]
INTENT_CACHE_PATH = Path(__file__).parent / "intent_cache.json"
INTENT_CACHE_MAX = 5000
_INTENT_CACHE = {}


def _load_seed_intents():
    """Prepared readings of common queries. Used only if they were made with
    this exact prompt AND model - a changed prompt or model silently ignores
    the file instead of serving stale readings."""
    try:
        seed = json.loads(INTENT_CACHE_PATH.read_text())
    except (OSError, ValueError):
        return
    if seed.get("prompt_hash") == _PROMPT_HASH and seed.get("model") == LLM_MODEL:
        _INTENT_CACHE.update(seed.get("intents", {}))


def _intent_cache_get(key):
    hit = _INTENT_CACHE.get(key)
    return copy.deepcopy(hit) if hit is not None else None


def _intent_cache_put(key, intent):
    if len(_INTENT_CACHE) >= INTENT_CACHE_MAX:
        _INTENT_CACHE.pop(next(iter(_INTENT_CACHE)))  # drop the oldest entry
    _INTENT_CACHE[key] = copy.deepcopy(intent)


def _call_with_retry(raw_query: str) -> dict:
    """One uncached LLM reading (one retry on a transient error) - used by
    build_intent_cache.py, never by a live search."""
    last = None
    for _ in range(2):
        try:
            caller = LLM_CALLERS[LLM_PROVIDER]
            text = caller(_TRANSLATE_SYSTEM_PROMPT, raw_query)
            return json.loads(text.replace("```json", "").replace("```", "").strip())
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


_load_seed_intents()


def _category_matches(category_field: str, wanted: str) -> bool:
    """
    A plain substring match ("%table%") is too crude - confirmed live:
    searching "chunky table" surfaced Minimalux lamps, In Common With
    lamps, and an Another Country carafe ahead of real tables, because
    their raw category tags (e.g. "Table Lamps", "Table and Glassware",
    "Phone & Tablet Sleeves") happen to contain the substring "table"
    without being tables at all. Real table categories in the actual
    scraped data are consistently "<modifier> Table(s)" - "Coffee Table",
    "Dining Tables", bare "Table" - i.e. the wanted word is the tag's own
    trailing word. A category is only "wanted" as a whole word, so a
    tag has to actually end with it: this naturally excludes "Table
    Lamps" (ends in "Lamps"), "Tableware"/"Table and Glassware" (end in
    "ware"/"Glassware"), and "Tablet Sleeves" (not even a word-boundary
    match for "table" at all).

    "wanted" itself can already be plural (confirmed live: the category
    browse chips send "tables"/"ceramics" as-is) - appending "s?" to an
    already-plural word requires a double-s ending and wrongly excludes
    every brand storing the singular form ("Table", "Coffee Table"),
    which is why the "Tables" chip only ever matched Another Country and
    Verk (the only brands whose tags happen to already be plural). Tries
    both the word as given and its singular form (trailing "s" stripped)
    so either a singular or plural stored tag matches regardless of
    which form the query arrived in.
    """
    candidates = {wanted}
    if wanted.lower().endswith("s"):
        candidates.add(wanted[:-1])

    tags = [t.strip() for t in category_field.split(",")]
    for candidate in candidates:
        pattern = re.compile(rf"\b{re.escape(candidate)}s?$", re.IGNORECASE)
        if any(pattern.search(tag) for tag in tags):
            return True

    # A handful of category words are hypernyms that don't literally
    # appear in most brands' own, more specific per-object-type tags -
    # confirmed live for both entries below by pulling every real
    # category tag across brands: "lighting" is never in In Common
    # With's "Sconce"/"Flush Mount" or 101cph's "Chandelier"/"Wall Lamp";
    # "furniture" is never in Baleri Italia's "Stackable chair" or
    # Verk's "Stools"/"Sofas" - a plain word-ending match only ever
    # caught the one brand that happens to use the hypernym itself as a
    # literal tag (Another Country, for both). Deliberately bounded to
    # these two words rather than a general taxonomy system - each list
    # was built from this project's own real category data, not guessed,
    # and "furniture" deliberately excludes tableware/decor words some
    # brands mix into the same tag set (e.g. 101cph's Vase/Bowl/Cutlery).
    HYPERNYM_WORDS = {
        # Nordic-language words added 2026-09-26 after auditing every
        # distinct category tag in the DB for real lighting/furniture
        # products hiding under the "Objects" catch-all (~680 products
        # found): most were the brand's own real category, just in
        # Danish/Swedish/Polish rather than English - "Belysning"
        # (Swedish "lighting"), "lampa"/"Lampy" (Swedish/Polish "lamp"),
        # and compound words like "Gulvlamper"/"Loftlamper"/"Væglamper"/
        # "Bordlamper"/"Sengelamper" (Danish "floor/ceiling/wall/table/
        # bed lamps" - one word, so still a real suffix match) and
        # "Pendler" (Danish "pendants"). These are added as their own
        # hyponym strings, matched the same end-anchored way as the
        # English ones - safe because they're distinctive foreign words
        # with no unrelated English collision risk, unlike a generic
        # word such as "light" would be if matched as a bare substring.
        "lighting": ("lamp", "light", "sconce", "pendant", "chandelier",
                     "surface mount", "flush mount", "wall mount",
                     "belysning", "lampa", "lampy", "lamper", "gulvlamper",
                     "loftlamper", "væglamper", "bordlamper", "sengelamper",
                     "projektbelysning", "pendler"),
        # cabinet/sideboard/footstool/daybed/wardrobe/drawers/shelf added
        # 2026-09-26, same audit as above - all real, common furniture
        # words that were simply missing from this list (e.g. Cabinet:
        # 99 products, Sideboard: 73, Footstool: 52, all invisible to a
        # "furniture" search before this). "benches"/"shelves" are each
        # added as their OWN string (not just relying on the trailing
        # "s?" appended to "bench"/"shelf") since both pluralize
        # irregularly (bench->benches, shelf->shelves, not "benchs"/
        # "shelfs") - the existing "s?" suffix can't produce either.
        "furniture": ("chair", "table", "stool", "bench", "benches", "sofa",
                      "armchair", "ottoman", "console", "bookcase",
                      "modular unit", "seat", "seating", "screen", "desk",
                      "storage", "shelving", "shelving system", "shelf",
                      "shelf library", "shelves", "cabinet", "sideboard",
                      "footstool", "daybed", "wardrobe", "drawers",
                      "furniture"),
        # Built the same way as furniture/lighting above - pulled every
        # real category tag across brands the site's own umbrella
        # classifier (generate_brand_pages.py) already calls Ceramics,
        # confirmed 2026-09-20: overwhelmingly "Vase(s)", "Bowl(s)",
        # "Plate(s)", plus a handful of "Cup"/"Carafe"/"Pitcher".
        "ceramics": ("vase", "bowl", "plate", "cup", "carafe", "pitcher"),
    }
    for hypernym, hyponyms in HYPERNYM_WORDS.items():
        if wanted.lower() not in (hypernym, hypernym + "s"):
            continue
        # Each hyponym gets the same end-anchored, optional-plural check
        # as the main word above, not a raw substring - a plain "in tag"
        # check reintroduces the exact "Table Lamps" problem for a
        # different word: "table" as a furniture hyponym would otherwise
        # match Minimalux's "Table Lamps" (confirmed live), since it's a
        # real substring there even though it's a lamp, not a table.
        for h in hyponyms:
            pattern = re.compile(rf"\b{re.escape(h)}s?$", re.IGNORECASE)
            if any(pattern.search(tag) for tag in tags):
                return True

    # A real Danish tag shape the suffix check above can't reach: "Lamper
    # til badeværelset" ("Lamps for the bathroom"), "Lamper til entré",
    # etc. - confirmed live 2026-09-26, ~15 real tag variants across
    # ~60 products, all genuine lighting. Danish's "noun til noun"
    # phrasing puts the real object-type word FIRST and a room name
    # LAST, the opposite of the "modifier then noun" order every other
    # hyponym check in this function assumes (e.g. "Coffee Table") - a
    # trailing-word match can never catch this shape, so this checks the
    # tag's own first word instead, scoped to exactly this one real
    # prefix rather than a general "contains anywhere" rule.
    if wanted.lower() in ("lighting", "lightings"):
        if any(tag.lower().startswith("lamper ") for tag in tags):
            return True

    # "Objects" isn't a real taxonomy word anyone's tags use - it's this
    # site's own catch-all for whatever doesn't match Furniture/Lighting
    # (see generate_brand_pages.py's DEFAULT_UMBRELLA). So it's matched
    # the same way it's assigned: by exclusion, not by keyword. Ceramics
    # is deliberately NOT excluded here (unlike furniture/lighting) -
    # the homepage's Objects tile folded Ceramics into it 2026-09-20 (see
    # project memory), so this residual now has to actually include real
    # ceramics products, not just the old leftover-everything-else set,
    # or the merge would be a lie the UI tells but the search results
    # contradict. A standalone "ceramics" query still works on its own,
    # unaffected - only the Objects catch-all's own definition widened.
    if wanted.lower() in ("object", "objects"):
        return not any(
            _category_matches(category_field, other)
            for other in ("furniture", "lighting")
        )

    return False


# Real product names describe the same shape with different words -
# confirmed live 2026-09-25: a search for "ball lamp" found nothing to
# narrow to on its own, even though the DB has real "Globe ... Table
# lamp" products - "ball" and "globe" mean the same shape, but a plain
# word match only ever catches whichever single word the query itself
# used. Each group below is real synonyms for ONE shape, not merely
# related shapes - "round" and "oval" are deliberately kept as separate
# groups, since conflating them would match the wrong shape entirely.
STYLE_SYNONYMS = {
    "ball": ("ball", "globe", "sphere", "orb"),
    "globe": ("ball", "globe", "sphere", "orb"),
    "sphere": ("ball", "globe", "sphere", "orb"),
    "orb": ("ball", "globe", "sphere", "orb"),
    "round": ("round", "circular"),
    "circular": ("round", "circular"),
    "oval": ("oval", "elliptical"),
    "elliptical": ("oval", "elliptical"),
    "rectangular": ("rectangular", "rectangle"),
    "rectangle": ("rectangular", "rectangle"),
}


def _expand_style_synonyms(style_descriptors: list) -> set:
    expanded = set()
    for d in style_descriptors:
        expanded.update(STYLE_SYNONYMS.get(d.lower(), (d,)))
    return expanded


def _narrow_by_style(products: list, style_descriptors: list) -> list:
    """
    Among an already category/material/color-filtered set, prefers
    products whose own name contains one of the requested style/shape
    words (e.g. "globe", "round") - confirmed live 2026-09-25: "globe
    table lamp" and "round table" both had translate_query() correctly
    extract a real style descriptor, but it was captured into the intent
    dict and then never applied anywhere, so a shape-specific search
    quietly fell back to the same results as the bare object-type search.

    Deliberately a narrow-if-possible pass, not a hard filter or a
    numeric score - this file's whole matching model treats a result as
    either in or out, with no per-item ranking (see cap_per_brand's own
    "capping should never quietly become a new de facto ranking
    signal"). A hard filter here would also risk emptying a search
    whenever a real matching product doesn't happen to spell the shape
    word out in its own name - most product names aren't rigid taxonomy
    strings - so this only narrows when doing so still leaves real
    matches, and returns the unnarrowed set otherwise.
    """
    if not style_descriptors:
        return products

    expanded_descriptors = _expand_style_synonyms(style_descriptors)

    def _name_matches_any(name: str) -> bool:
        return any(
            re.search(rf"\b{re.escape(d)}\b", name, re.IGNORECASE)
            for d in expanded_descriptors
        )

    narrowed = [p for p in products if _name_matches_any(p["product_name"])]
    return narrowed if narrowed else products


# An individual, numbered build-your-own module/component of a modular
# furniture system (e.g. "Shore Dining Curved End Left, Plinth, Module
# 41", "Livello Middle Module 95cm") - a real, individually-orderable
# replacement/build part, but not something a category search should
# surface as if it were a complete, standalone piece. Found live
# 2026-09-29: "Shore Dining Curved End Left, Plinth, Module 41" (New
# Works DK) surfaced under a plain "sofa" search. Confirmed the real
# pattern across 2 brands, 12 total items: the word "Module" followed
# by any numbered/sized code (a bare number, or a code like "L200"/
# "95cm"). Deliberately doesn't match "Shore Modular Sofa, Configuration
# N" (New Works DK's own real, complete pre-built configurations, which
# use "Modular"/"Configuration", never "Module <code>") - checked live,
# 0 false positives/negatives across all 690 real sofa-category results.
MODULAR_COMPONENT_PATTERN = re.compile(r"\bModule\s+\w*\d")


def _is_modular_component(product_name: str) -> bool:
    return bool(MODULAR_COMPONENT_PATTERN.search(product_name))


# A protective cover FOR a piece of furniture, not the furniture itself -
# found live 2026-09-29 while building the Two Seater Sofas theme:
# Serax lists "protection cover 2 seater rudolph"/"protection cover 2
# seater bea mombaers" under category "Sofa" (and a 1-seater/3-seater/
# ottoman version of each, 9 total), so a plain "sofa" search surfaced
# a fabric cover as if it were a sofa. Scoped tightly to the literal
# phrase actually found, not a broader "cover" match, since a real
# product could legitimately be named e.g. "seat cover" as its own
# upholstery product.
PROTECTIVE_COVER_PATTERN = re.compile(r"protection cover", re.IGNORECASE)


def _is_protective_cover(product_name: str) -> bool:
    return bool(PROTECTIVE_COVER_PATTERN.search(product_name))


_PRODUCT_ROWS_CACHE = {"key": None, "rows": [], "first_scan": {}, "undated": set()}
_PRODUCT_ROWS_LOCK = threading.Lock()


def _all_product_rows() -> list:
    """Every product row as a plain dict, read from SQLite once and reused
    (2026-10-04). Each search used to re-read and re-wrap all ~28,000 rows
    twice (filter_products and filter_by_name), ~0.2s each on a laptop and far
    more on a throttled Cloud Run CPU. The data only changes when the
    database file does, so the cache is keyed on its mtime/size and rebuilt
    when it changes. The dicts are SHARED: callers must treat them as
    read-only and copy (dict(row)) a row before changing it."""
    stat = DB_PATH.stat()
    key = (stat.st_mtime_ns, stat.st_size)
    cache = _PRODUCT_ROWS_CACHE
    if cache["key"] != key:
        with _PRODUCT_ROWS_LOCK:
            if cache["key"] != key:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                rows = [dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
                conn.close()
                cache["first_scan"], cache["undated"] = _new_piece_context(rows)
                cache["rows"], cache["key"] = rows, key
    return cache["rows"]


# "New" = new from the maker (2026-10-04), not "first seen by our scraper" (that is "Recently added": mostly whole
# catalogs scanned for the first time). A piece is New when
#   - it carries the maker's own date (products.released_at: Shopify created/published, WordPress post date)
#     within the window; or
#   - it has no maker date (the platform exposes none) but we first saw it more than a week AFTER our first scan
#     of that maker - i.e. it appeared in the maker's catalog while we were watching - within the window.
# A maker whose EARLIEST maker date is under a year old is treated as undated: its store was probably (re)built
# recently, which would make its whole catalog look new.
NEW_FIRST_SCAN_GRACE_DAYS = 7
NEW_YOUNG_STORE_DAYS = 365


def _new_piece_context(rows):
    """({brand: day of our first scan}, {brands treated as undated}) for _is_new_piece."""
    today = datetime.date.today()
    young_cutoff = (today - datetime.timedelta(days=NEW_YOUNG_STORE_DAYS)).isoformat()
    first_scan, epoch = {}, {}
    for r in rows:
        b = r["brand"]
        fs = r.get("first_seen")
        if fs and (b not in first_scan or fs < first_scan[b]):
            first_scan[b] = fs
        ra = r.get("released_at")
        if ra and (b not in epoch or ra < epoch[b]):
            epoch[b] = ra
    undated = {b for b, e in epoch.items() if e > young_cutoff}
    grace = datetime.timedelta(days=NEW_FIRST_SCAN_GRACE_DAYS)
    first_scan = {b: (datetime.date.fromisoformat(d) + grace).isoformat() for b, d in first_scan.items()}
    return first_scan, undated


def new_cutoff_day():
    return (datetime.date.today() - datetime.timedelta(days=NEW_ARRIVALS_WINDOW_DAYS)).isoformat()


def is_new_piece(product, cutoff=None):
    """True when the piece is New from the maker (see the note above). Needs the row cache to be loaded."""
    cutoff = cutoff or new_cutoff_day()
    _all_product_rows()
    ra = product.get("released_at")
    if ra and product["brand"] not in _PRODUCT_ROWS_CACHE["undated"]:
        return ra >= cutoff
    fs = product.get("first_seen")
    if not fs or fs < cutoff:
        return False
    return fs > _PRODUCT_ROWS_CACHE["first_scan"].get(product["brand"], "")


def filter_products(intent: dict) -> list:
    """
    Filters stored products on the hard facts: category + material +
    new_only (recency, see _wants_new_arrivals) + countries (see
    _wanted_countries) + seat_count (see _wanted_seat_count) +
    portable_only (see _wants_portable/_product_is_portable) + tier (see
    BRAND_TIERS - explicit chip selection only, never inferred from
    query text) + not an
    individual modular-system build component (see
    _is_modular_component) + not a protective cover for the furniture
    rather than the furniture itself (see _is_protective_cover) + has a
    real image. A
    missing image isn't just a display gap - the whole "thumbnail +
    link-back" model this tool is built on doesn't work without one,
    and in practice a missing image reliably means the listing is
    either a spare-parts/replacement SKU or genuine dead weight on the
    source site (confirmed live: In Common With's imageless records are
    all "Replacement"/"Hidden"-tagged hardware, and Another Country's
    are either that or literal leftover test listings like "test 3" and
    "Product"). Checked before adding this: no brand loses all its
    results, and no brand relies on its imageless records to be
    discoverable at all.
    """
    rows = _all_product_rows()

    wanted_category = (intent.get("category") or "").strip()
    wanted_material = (intent.get("material") or "").strip().lower()
    # Same 90-day window /new.html itself uses (see NEW_ARRIVALS_WINDOW_DAYS
    # above) - computed once per call, not per row.
    new_cutoff = new_cutoff_day() if intent.get("new_only") else None
    # translate_query() extracts color as its own field, separate from
    # material - it was being parsed and then silently thrown away here,
    # so a query like "black chair" filtered on category alone and could
    # return a chair with no black option at all (confirmed live: "black
    # surface mount" returned In Common With's Mira Surface Mount, which
    # has zero "black" anywhere in its material_options). Checked the same
    # way material is - color names are already embedded in the same
    # compound material_options strings (e.g. "Black / Bone / Hardwire").
    wanted_color = (intent.get("color") or "").strip().lower()
    wanted_countries = set(intent.get("countries") or [])
    wanted_seat_count = intent.get("seat_count")
    wanted_portable = bool(intent.get("portable_only"))
    # Never set by query-text parsing (unlike every other intent field
    # here) - this only ever arrives explicitly from the Work page's own
    # Independent/Established chips (see main.py's tier query param),
    # not inferred from what someone typed. "independent" or
    # "established"; anything else (including absent) means no filter.
    wanted_tier = intent.get("tier")
    wanted_brands = set(intent.get("brands") or [])
    raw_style_descriptors = intent.get("style_descriptors") or []
    wanted_style_descriptors = [
        d.strip().lower() for d in raw_style_descriptors
        if isinstance(d, str) and d.strip()
    ]

    products = []
    for row in rows:
        product = row  # shared, read-only: copied below once the row survives every filter

        if not product["image_url"]:
            continue
        if product["brand"] in HIDDEN_BRANDS:
            continue
        if wanted_brands and product["brand"] not in wanted_brands:
            continue
        if wanted_category and not _category_matches(product["category"], wanted_category):
            continue
        if wanted_category and _is_modular_component(product["product_name"]):
            continue
        if wanted_category and _is_protective_cover(product["product_name"]):
            continue
        if wanted_material and wanted_material not in product["material_options"].lower():
            continue
        if wanted_color and wanted_color not in product["material_options"].lower():
            continue
        if new_cutoff and not is_new_piece(product, new_cutoff):
            continue
        if wanted_countries and BRAND_COUNTRIES.get(product["brand"]) not in wanted_countries:
            continue
        if wanted_seat_count is not None and not _product_matches_seat_count(product["product_name"], wanted_seat_count):
            continue
        if wanted_portable and not _product_is_portable(product["product_name"]):
            continue
        if wanted_tier and BRAND_TIERS.get(product["brand"], "independent") != wanted_tier:
            continue

        product = dict(row)

        # A product with many raw finish/color combos merged into one
        # entry (see extract_shopify's grouping) picks just one for its
        # thumbnail at scrape time - if the user searched for a specific
        # material/color and it matched here, that confirms it exists
        # even when what's pictured is something else entirely (e.g.
        # "black chair" matching a listing photographed in red).
        # Surfacing the confirmed term(s) directly is more useful and
        # less noisy than a bare variant count ever was.
        matched_terms = [t for t in (wanted_material, wanted_color) if t]
        if matched_terms:
            product["matched_material"] = ", ".join(matched_terms)

        # Stored as a JSON string (see scraper/scrape.py's save_product) -
        # callers of this API should get a real array, not a string they
        # have to parse themselves.
        product["material_options"] = json.loads(product["material_options"] or "[]")
        product["thin"] = bool(product["thin"])
        products.append(product)
    return _narrow_by_style(products, wanted_style_descriptors)


# A product whose entire name is nothing but a bare object-type word
# carries no more information than its own category field already does
# - so letting it match the forward name_in_query direction below is
# pure noise, not a real name match: it fires for ANY query that
# happens to contain that one common word, no matter how much other,
# unrelated content the rest of the query has. Confirmed live 2026-09-25:
# Moebe's product literally named "Table" matched the query "globe table
# lamp" in full, surfacing a sofa-system side table for a lamp search -
# category filtering alone couldn't catch it either, since Moebe's own
# site had mistakenly grouped that product under its "Modular Sofa"
# collection (fixed directly in the data). Built from the real bare
# object-type names that exist in the DB today (see project memory),
# not a general English word list - a name that's actually descriptive
# ("Boyd sofa", "Vaso") is unaffected either way.
GENERIC_PRODUCT_NAMES = {
    "table", "lamp", "chair", "stool", "vase", "bench", "sofa", "bowl",
}


def filter_by_name(raw_query: str, tier=None) -> list:
    """
    Matches the raw query against each product's own name, independent
    of the category/material hard filter above - checked in both
    directions. The original direction (product_name found inside the
    query) confirmed live: searching "vaso" surfaced Bitossi Ceramiche's
    own product literally named "Vaso", since filter_products() only
    ever checks category/material - it never looks at product_name at
    all. But that direction alone only works when the query happens to
    equal (or fully contain) the whole name - a real partial-name
    search, someone typing "Boyd" for Pinch's "Boyd sofa," matched
    nothing (confirmed live 2026-09-21), because the longer name was
    never going to be found inside the shorter query. Also checking the
    reverse direction (the query found inside the name) fixes that. The
    length-3 floor keeps that reverse check from firing on short
    connector words ("a", "or") that the LLM's category/material
    extraction already handles better on its own. See
    GENERIC_PRODUCT_NAMES above for why the forward direction is
    additionally skipped for a bare object-type name.

    tier (see BRAND_TIERS), when given, applies here too - a direct
    name match still has to respect the Independent/Established chip,
    the same as filter_products() already does, otherwise a name-match
    fallback would silently defeat the filter whenever the query itself
    happened to also name the product.
    """
    rows = _all_product_rows()

    stripped_query = raw_query.strip()
    # Compiled ONCE per search. This loop used to build a fresh regex for
    # every one of ~28,000 products (Python's own regex cache holds 512), which
    # was ~1.4s of a 1.8s match step. Same matches, no per-product compile.
    query_pattern = (
        re.compile(rf"\b{re.escape(stripped_query)}\b", re.IGNORECASE)
        if len(stripped_query) >= 3 else None
    )
    query_lower = raw_query.lower()
    query_ascii = raw_query.isascii()
    matches = []
    for row in rows:
        if not row["image_url"]:
            continue
        if row["brand"] in HIDDEN_BRANDS:
            continue
        if tier and BRAND_TIERS.get(row["brand"], "independent") != tier:
            continue
        name = row["product_name"]
        name_in_query = False
        if name.strip().lower() not in GENERIC_PRODUCT_NAMES:
            if query_ascii and name.isascii():
                # a whole-word, case-insensitive match can only exist if the name
                # is a plain substring of the query, so skip the regex otherwise
                # (ASCII only: IGNORECASE folds some non-ASCII characters this
                # shortcut would not know about)
                name_in_query = name.lower() in query_lower and bool(
                    re.search(rf"\b{re.escape(name)}\b", raw_query, re.IGNORECASE))
            else:
                name_in_query = bool(re.search(rf"\b{re.escape(name)}\b", raw_query, re.IGNORECASE))
        query_in_name = bool(query_pattern and query_pattern.search(name))
        if name_in_query or query_in_name:
            product = dict(row)
            product["material_options"] = json.loads(product["material_options"] or "[]")
            product["thin"] = bool(product["thin"])
            matches.append(product)
    return matches


def _load_houses() -> list:
    """
    Reads data/houses.json fresh on every call rather than caching -
    only 54 real rows today (see scrape_architect_projects.py), so the
    cost is negligible, and it means a re-scrape is picked up on the
    next search with no backend restart needed. No Style facet here on
    purpose (see site_restructuring project memory) - real per-firm
    style tagging is a manual-triage decision that hasn't happened yet,
    so this never fabricates one at query time either.
    """
    if not HOUSES_PATH.exists():
        return []
    return json.loads(HOUSES_PATH.read_text())


def _normalize_house(house: dict, matched_location=None) -> dict:
    """
    Shapes a raw houses.json record into the same card-renderable shape
    products already have, so the frontend can reuse most of its
    existing renderCard() logic rather than needing a parallel one.
    `brand` is deliberately aliased to the firm name - cap_per_brand()
    only ever reads `p["brand"]` to group its fairness cap, so a house
    competes for its "one firm shouldn't crowd out others" slot the
    exact same way a product does, with no changes to that function.
    `product_name`/`product_url` are aliased too so click-tracking
    (which reads those two fields) keeps working unmodified - only the
    card's visual template needs a real per-type branch.
    """
    return {
        "type": "house",
        "id": f"house:{house.get('url')}",
        "name": house.get("name"),
        "product_name": house.get("name"),
        "firm": house.get("firm"),
        "brand": house.get("firm"),
        "location": house.get("location"),
        "region": house.get("region"),
        "year": house.get("year"),
        "description": house.get("description"),
        "image_url": house.get("image"),
        "product_url": house.get("url"),
        "brand_url": house.get("url"),
        "link_dead": False,
        "matched_location": matched_location,
    }


def filter_houses(intent: dict, houses=None) -> list:
    """
    Only runs at all when the extracted category is house-like (see
    HOUSE_CATEGORY_WORDS) - a query about a chair should never surface
    houses just because it also named a place. Once triggered, location
    narrows the real 54-house set the same way category/material narrow
    products: a plain case-insensitive substring check against each
    house's own real location/region text, not a geocoded match - real
    strings like "Nacka (Lännersta), Stockholm" and "Skåne" are what's
    actually stored, no fabricated geo-taxonomy beyond that.

    `houses` defaults to the real data/houses.json (see _load_houses)
    but can be injected with synthetic records - same dependency-
    injection shape as filter_products() taking `rows` implicitly via
    the DB, kept explicit here so tests/test_query_engine.py can cover
    the real matching logic without depending on real scraped data
    staying a fixed shape/count.
    """
    wanted_category = (intent.get("category") or "").strip().lower()
    if wanted_category not in HOUSE_CATEGORY_WORDS:
        return []

    wanted_location = (intent.get("location") or "").strip().lower()
    matches = []
    for house in (houses if houses is not None else _load_houses()):
        if wanted_location:
            haystack = f"{house.get('location') or ''} {house.get('region') or ''}".lower()
            if wanted_location not in haystack:
                continue
        matches.append(_normalize_house(house, matched_location=intent.get("location") if wanted_location else None))
    return matches


def filter_houses_by_name(raw_query: str, houses=None) -> list:
    """Same direct-name-match rationale as filter_by_name() for
    products - a query literally naming a real house ("H House") should
    match regardless of whether category extraction recognized it as a
    house query at all."""
    matches = []
    for house in (houses if houses is not None else _load_houses()):
        name = house.get("name")
        if name and re.search(rf"\b{re.escape(name)}\b", raw_query, re.IGNORECASE):
            matches.append(_normalize_house(house))
    return matches


def discover(per_brand: int = DISCOVER_PER_BRAND, total_cap: int = DISCOVER_TOTAL_CAP, tier=None) -> list:
    """
    Random browse across the whole catalog, no query/filtering involved -
    for "surprise me" / typing "random" instead of a real search. Samples
    up to per_brand items from *every* brand rather than taking a uniform
    random sample of all products, which would be dominated by the
    largest catalogs (In Common With alone is a third of all valid
    records) and would rarely surface a brand with only a handful of
    products at all. Same "brand is the minimum unit of inclusion"
    principle as cap_per_brand, just applied to a browse instead of a
    search result.

    The per-brand pool is then cut down to total_cap (see its own comment)
    - a random total_cap-sized slice of an already-shuffled list, so which
    brands make the cut varies call to call rather than always favoring
    the same ones alphabetically or by ID.

    tier (see BRAND_TIERS), when given, restricts the whole sample to
    just that tier before any sampling happens - same explicit,
    chip-only filter as filter_products()'s own tier check, not
    something Discover's "no query at all" nature would otherwise have
    any way to express.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products WHERE image_url != ''").fetchall()
    conn.close()

    by_brand = {}
    for row in rows:
        product = dict(row)
        if product["brand"] in HIDDEN_BRANDS:
            continue
        if tier and BRAND_TIERS.get(product["brand"], "independent") != tier:
            continue
        product["material_options"] = json.loads(product["material_options"] or "[]")
        product["thin"] = bool(product["thin"])
        by_brand.setdefault(product["brand"], []).append(product)

    sampled = []
    for brand_products in by_brand.values():
        sampled.extend(random.sample(brand_products, min(per_brand, len(brand_products))))

    random.shuffle(sampled)
    houses = [] if tier else _discover_houses()
    results = sampled[:total_cap - len(houses)]
    for house in houses:                       # scattered at random positions, not bunched at one end
        results.insert(random.randint(0, len(results)), house)
    return results


def _discover_houses() -> list:
    """1 to DISCOVER_HOUSES_MAX random houses from different practices, as cards (see _normalize_house)."""
    by_firm = {}
    for house in _load_houses():
        if house.get("image") and house.get("url") and house.get("firm"):
            by_firm.setdefault(house["firm"], []).append(house)
    if not by_firm:
        return []
    firms = random.sample(sorted(by_firm), min(random.randint(1, DISCOVER_HOUSES_MAX), len(by_firm)))
    return [_normalize_house(random.choice(by_firm[firm])) for firm in firms]


def cap_per_brand(products: list, max_per_brand: int = MAX_RESULTS_PER_BRAND) -> list:
    """
    Limits how many results from any single brand can appear in one
    search's results, so a brand with a large catalog can't crowd out
    smaller makers who might match just as well with only a handful of
    listed products - directly serves the "brand is the minimum unit of
    inclusion" principle: a big catalog shouldn't count for more just
    because it's big.

    Which items get kept (per brand) and the final order are both
    randomized, consistent with the "equally relevant results are shown
    in randomized order" decision - capping should never quietly become
    a new de facto ranking signal.
    """
    by_brand = {}
    for p in products:
        by_brand.setdefault(p["brand"], []).append(p)

    capped = []
    for brand_products in by_brand.values():
        random.shuffle(brand_products)
        capped.extend(brand_products[:max_per_brand])

    random.shuffle(capped)
    return capped


def _resolve_intent(raw_query: str, llm_intent: dict) -> dict:
    """
    Overrides the LLM's intent with a clean, category-only one whenever
    the whole query is exactly one of BROWSE_CATEGORY_WORDS (only ever
    sent by the homepage's own category tiles, never typed by a person).
    Kept as its own pure function, independent of the real translate_query()
    LLM call, so this override logic can be unit tested directly rather
    than only through a live search() call.

    Second, broader fallback (2026-09-28): the same null-category failure
    the bare-word case above already works around also happens for a real
    multi-word query built around one of these umbrella words - confirmed
    live: "furniture" alone and "handmade furniture" both correctly
    resolve category="furniture", but "furniture makers", "Scandinavian
    furniture", and "independent furniture makers" all come back
    category=null from the LLM, since its own prompt asks for a specific
    object type ("chair", "lamp"), not a broad grouping word, and it
    isn't reliable about falling back to the grouping word once another
    word is attached. A null category here means filter_products() skips
    its category filter entirely and returns the whole catalog, which
    _narrow_by_style then either hands back completely unfiltered (if the
    leftover style word matches no product name) or narrows by pure
    incidental substring match (e.g. "modern furniture design" narrowing
    to 8 products just because they happen to say "Modern" in their
    name, including a hand lotion and a poster) - both equally unrelated
    to what was actually asked. Only fires when the LLM left category
    null; a real, specific category it did find (e.g. "coffee table")
    always wins over this broader fallback.

    Third, "new"/"new arrivals" recognition (2026-09-28): typing "new"
    or "new chairs" into Work's search box has a reasonable expectation
    of behaving like the dedicated New Arrivals page - see project
    memory, first_seen_new_arrivals_bug_fixed, and the homepage's own
    "See all N new chairs" links, which need this to actually deliver
    what they promise. Without this, "new" falls through to the LLM's
    generic style_descriptors handling, which does a literal text-match
    against product NAMES (see _narrow_by_style) - unrelated to
    recency, and would either return the whole catalog unfiltered or
    narrow by incidental coincidence, the same failure class the
    umbrella-word fix above already solved for "furniture". Sets
    `new_only` as a plain filter (is this product's first_seen within
    the same 90-day window /new.html itself uses), never a sort order -
    results still shuffle randomly like every other search, consistent
    with this engine never ranking results (see
    product_interface_decisions.md's "no ranking" principle); /new.html
    remains the place to see this sorted chronologically. Strips "new"
    out of style_descriptors when this fires so it isn't also literal-
    text-matched against product names on top of the real recency
    filter - pure noise otherwise, same reasoning as GENERIC_PRODUCT_NAMES.

    Fourth, geography (2026-09-28): "Scandinavian dining table" is a
    real, valuable ad phrase - the planned paid-traffic experiment's own
    geography targeting is Sweden/Scandinavia (see project memory,
    monetization_build_sequencing_and_shared_primitive) - but product
    search never filtered on location at all before this; `location`
    was only ever wired into house search. A region word like
    "Scandinavian" also isn't a literal country name the LLM's own
    `location` field can resolve on its own (same LLM-reliability gap
    as the umbrella-category and "new" fixes above - it's an adjective
    describing a group of countries, not a place name). See
    _wanted_countries/GEOGRAPHY_GROUPS: matches real, confirmed country
    data from brands.json (BRAND_COUNTRIES), combining deterministic
    region/demonym word-matching with the LLM's own location field for
    the simple single-country case. Sets `countries` as a hard filter
    (a product's brand must be from one of the matched countries),
    combinable with category same as material - "Scandinavian dining
    table" becomes category=dining table AND countries={Sweden,Denmark,
    Norway}. Strips the matched geography word out of style_descriptors
    for the same reason "new" is stripped - avoids double-duty noise-
    matching against product names.

    Fifth, seat count (2026-09-28): "two seater sofa"/"three seater
    sofa" are real ad keywords with real search volume - and a real
    fact genuinely embedded in many product names ("2-Seater," "Three
    Seater"), just not as a structured database column. Checked live
    that the existing plain-substring name search (filter_by_name)
    badly under-matches this - only 4 of 56 real "two seater" products,
    since it requires the whole query or whole name to appear inside
    the other, not a flexible digit/word-form regex. See
    _wanted_seat_count/_product_matches_seat_count: sets `seat_count`
    as a hard filter, combinable with category exactly like the others,
    matching either digit or word form in the product's own name.
    Swedish query forms added 2026-09-29 (SWEDISH_SEAT_COUNT_PATTERN) -
    "tvåsits"/"2-sits" is the real Swedish furniture term, and returned
    zero results before this despite real matching inventory.

    Sixth, portable/cordless lamps (2026-09-29, campaign rebuilt
    Swedish-first): "uppladdningsbar bordslampa"/"portable table lamp"
    are real, high-value ad keywords, and "Portable" is a real naming
    convention 28 products across 6 brands already use for a cordless/
    rechargeable lamp - see PORTABLE_LAMP_WORDS/_product_is_portable.
    Sets `portable_only` as a hard filter, combinable with category
    exactly like the others.
    """
    stripped = raw_query.strip().lower()
    if stripped in BROWSE_CATEGORY_WORDS:
        intent = {"category": BROWSE_CATEGORY_WORDS[stripped]}
    elif not llm_intent.get("category"):
        intent = llm_intent
        for word in re.findall(r"[a-zà-ÿ]+", stripped):
            if word in BROWSE_CATEGORY_WORDS:
                intent = {**llm_intent, "category": BROWSE_CATEGORY_WORDS[word]}
                break
    else:
        intent = llm_intent

    if _wants_new_arrivals(stripped):
        intent = dict(intent)
        intent["new_only"] = True
        style_descriptors = intent.get("style_descriptors")
        if style_descriptors:
            intent["style_descriptors"] = [
                d for d in style_descriptors if not (isinstance(d, str) and d.strip().lower() == "new")
            ]

    wanted_countries = _wanted_countries(stripped, llm_intent.get("location"))
    if wanted_countries:
        intent = dict(intent)
        intent["countries"] = sorted(wanted_countries)
        style_descriptors = intent.get("style_descriptors")
        if style_descriptors:
            matched_words = {w for w in re.findall(r"[a-zà-ÿ]+", stripped) if w in GEOGRAPHY_GROUPS}
            intent["style_descriptors"] = [
                d for d in style_descriptors
                if not (isinstance(d, str) and d.strip().lower() in matched_words)
            ]

    wanted_seat_count = _wanted_seat_count(stripped)
    if wanted_seat_count is not None:
        intent = dict(intent)
        intent["seat_count"] = wanted_seat_count
        style_descriptors = intent.get("style_descriptors")
        if style_descriptors:
            intent["style_descriptors"] = [
                d for d in style_descriptors
                if not (isinstance(d, str) and _wanted_seat_count(d.strip().lower()) == wanted_seat_count)
            ]
        # The LLM's own category extraction sometimes echoes the whole
        # raw query back verbatim instead of isolating the real category
        # word - confirmed live 2026-09-29: "two seater sofa" (and the
        # "2-seater"/"three seater" forms) all resolved to
        # category="two seater sofa" etc., which matches almost no real
        # product's category tag, collapsing 56 real matches down to 3-4.
        # seat_count itself was already extracted correctly above (it
        # comes from the raw query text directly, not the LLM's category
        # field) - this just cleans the seat-count phrase back out of
        # category too, same as it's already stripped from
        # style_descriptors above.
        category = intent.get("category")
        if isinstance(category, str) and category:
            cleaned_category = SEAT_COUNT_PATTERN.sub("", category).strip()
            cleaned_category = SWEDISH_SEAT_COUNT_PATTERN.sub("", cleaned_category).strip()
            if cleaned_category != category:
                intent["category"] = cleaned_category or None

    if _wants_portable(stripped):
        intent = dict(intent)
        intent["portable_only"] = True
        style_descriptors = intent.get("style_descriptors")
        if style_descriptors:
            intent["style_descriptors"] = [
                d for d in style_descriptors
                if not (isinstance(d, str) and d.strip().lower() in PORTABLE_LAMP_WORDS)
            ]

    return intent


# Single-word brand names that are also ordinary words people put in a
# description ("oak grain table", "northern light"). Such a brand is only
# recognised when the WHOLE query is its name, never as one word inside a
# longer query. Every other brand name is also recognised inside a longer
# query ("serax vase", "piet hein eek chair").
AMBIGUOUS_BRAND_WORDS = {
    "grain", "noah", "zero", "blond", "northern", "resident", "pulpo", "sekt",
    "laun", "verk", "pode", "pinch",
}


# A brand known by a shorter name than its full one: "Rieul Lighting" is "Rieul", "Tlachï Design" is "tlachi". The
# trailing generic word is dropped to make a second name for it (found 2026-10-09: "rieul" and "tlachi chair" matched
# nothing and fell through to the whole catalogue). Only when that leaves 4+ letters, the brand doesn't START with a
# generic word ("Objects for Objects"), and no other brand has the same short name or full name.
GENERIC_BRAND_SUFFIXES = {
    "design", "designs", "lighting", "studio", "studios", "furniture", "ceramics", "objects", "editions", "edition",
    "collection", "workshop", "atelier",
}
# Short names that are also ordinary words ("lemon", "oven", "kann" = jug): recognised only when the WHOLE query is
# the name, like AMBIGUOUS_BRAND_WORDS, never inside a longer query ("lemon squeezer", "oven glove").
AMBIGUOUS_BRAND_ALIASES = {"lemon", "oven", "omelette", "seer", "fleur", "kann", "cultivation", "valerie"}


def _fold(text: str) -> str:
    """Lower-case, accent-free, punctuation-free form of a name or query:
    "Källemo" -> "kallemo", "B&B Italia" -> "b b italia"."""
    ascii_only = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_only.lower()).split())


_BRAND_FOLDS_CACHE = {"key": None, "folds": {}}


def _brand_folds() -> dict:
    """{folded name: real brand name} for every visible brand in the DB.
    Rebuilt when the DB file changes (same key as _all_product_rows)."""
    rows = _all_product_rows()
    cache = _BRAND_FOLDS_CACHE
    if cache["key"] is not rows:
        folds = {}
        for brand in {r["brand"] for r in rows}:
            if brand in HIDDEN_BRANDS:
                continue
            f = _fold(brand)
            if f:
                folds[f] = brand
        aliases = {}
        for f, brand in folds.items():
            words = f.split()
            if words[0] in GENERIC_BRAND_SUFFIXES:
                continue
            while len(words) > 1 and words[-1] in GENERIC_BRAND_SUFFIXES:
                words = words[:-1]
            alias = " ".join(words)
            if alias != f and len(alias) >= 4 and alias not in folds:
                aliases.setdefault(alias, set()).add(brand)
        for alias, owners in aliases.items():
            if len(owners) == 1:                       # two brands sharing a short name: neither gets it
                folds[alias] = next(iter(owners))
        cache["folds"], cache["key"] = folds, rows
    return cache["folds"]


def detect_brands(raw_query: str) -> list:
    """Real brand names the query is about: the whole query is a brand's
    name ("HAY", "ligne roset", "kallemo"), or a longer query contains an
    unambiguous brand name as whole words ("serax vase"). Before this a
    brand-name search matched no filter at all and fell through to the
    entire catalog (confirmed 2026-10-05: 'HAY' -> 28,026 results)."""
    query = _fold(raw_query)
    if not query:
        return []
    folds = _brand_folds()
    if query in folds:
        return [folds[query]]
    found = []
    padded = f" {query} "
    # longest name first, and a name inside an already-found longer one is skipped
    for f in sorted(folds, key=len, reverse=True):
        if f in AMBIGUOUS_BRAND_WORDS or f in AMBIGUOUS_BRAND_ALIASES:
            continue
        if f" {f} " in padded and not any(f in other for other in (_fold(b) for b in found)):
            found.append(folds[f])
    return found


_HARD_FILTER_KEYS = ("category", "material", "color", "new_only", "countries",
                     "seat_count", "portable_only", "brands")


def _has_hard_filter(intent: dict) -> bool:
    """True when the intent narrows the catalog at all. filter_products()
    with none of these returns EVERY product, which is right only for an
    explicit browse, never for a query nothing recognised ("xyzzyqwerty")."""
    return any(intent.get(k) not in (None, "", [], False) for k in _HARD_FILTER_KEYS)


def brand_links(intent: dict) -> list:
    """[{name, slug}] for the brands in an intent, so the results page can
    link to each maker's own page. The slug rule is a copy of
    scraper/generate_brand_pages.slugify (the scraper package isn't in the
    Cloud Run image); a test keeps the two identical."""
    out = []
    for name in intent.get("brands") or []:
        ascii_only = unicodedata.normalize("NFKD", name.replace("Ł", "L").replace("ł", "l")).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower() or "brand"
        out.append({"name": name, "slug": slug})
    return out


def _match_all(raw_query: str, intent: dict) -> list:
    """The shared matching pipeline - filter (category/material hard
    facts, a style-descriptor narrow-if-possible pass, plus a direct
    name match - see filter_by_name), given an already-resolved intent.
    Split out of search() (2026-09-27) so the "load more" pipeline
    (search_more(), below) can re-run the exact same matching logic
    against a query's already-resolved intent without a second LLM
    call - translate_query() is the only step that costs a real API
    call, and it only ever needs to run once per typed query.

    Houses (see filter_houses) are folded into the same matches list,
    not returned separately - "two surfaces, one engine" extends to
    "one result list," so a house and a product compete for the same
    per-firm/per-brand fairness cap via the same cap_per_brand() call,
    unmodified (see _normalize_house's "brand" alias)."""
    matches = filter_products(intent) if _has_hard_filter(intent) else []

    # Skipped for a house-intent query (e.g. "house", "villa in Sweden") -
    # a house search should only ever surface real architect-designed
    # houses, not a maker's product whose name happens to contain the
    # same word by coincidence. Confirmed live 2026-09-24: "house"
    # matched Joy Objects' "HOUSE MUSIC VOLUME 01" (an apparel item)
    # purely on substring, with no relation to architecture at all.
    is_house_intent = (intent.get("category") or "").lower() in HOUSE_CATEGORY_WORDS
    seen_ids = {m["id"] for m in matches}
    if not is_house_intent:
        wanted_brands = set(intent.get("brands") or [])
        for m in filter_by_name(raw_query, tier=intent.get("tier")):
            if wanted_brands and m["brand"] not in wanted_brands:
                continue
            if m["id"] not in seen_ids:
                matches.append(m)
                seen_ids.add(m["id"])

    # Houses are deliberately never tier-filtered - architecture firms
    # aren't part of BRAND_TIERS' established/independent taxonomy at
    # all (that's a product-brand distinction), so applying intent.get
    # ("tier") here would just default every firm to "independent" and
    # silently hide every house whenever "Established" is selected.
    for h in filter_houses(intent):
        if h["id"] not in seen_ids:
            matches.append(h)
            seen_ids.add(h["id"])
    for h in filter_houses_by_name(raw_query):
        if h["id"] not in seen_ids:
            matches.append(h)
            seen_ids.add(h["id"])

    return matches


def round_robin_order(products: list) -> list:
    """Orders a pool of leftover matches (everything cap_per_brand()
    trimmed away) for the search page's "See more" button, so repeated
    clicks stay mixed across brands all the way to the end instead of
    the last few clicks being 100% one brand.

    Takes exactly 1 item per brand per pass (reusing cap_per_brand()
    itself, with max_per_brand=1) and repeats until the pool is empty,
    building one fully interleaved sequence. Mocked up and measured
    against a real "chair" search (1,418 raw matches, 90 brands) before
    building this: a flat, larger per-round cap (e.g. 12/brand) drains
    small-catalog brands within the first round or two, leaving the
    biggest catalogs (there, Mater) to fill the last several clicks
    entirely on their own - confirmed live, the last 3 of 11 "load
    more" clicks came back 100% Mater. This 1-per-pass version never
    dropped below 5 brands in any click on the same data, in 6 clicks
    instead of 11. A same-brand run can still appear once every other
    brand's supply is genuinely exhausted (unavoidable once only one
    brand has anything left - the real floor there is just however much
    bigger that one brand's catalog is than the next-biggest), but it's
    no longer possible for an entire "load more" click to be one brand
    while others still have items left.

    The frontend slices this single ordered list into its own
    fixed-size reveal chunks for pacing - that chunking is a UI choice,
    kept independent of the fairness ordering computed here."""
    ordered = []
    pool = list(products)
    while pool:
        batch = cap_per_brand(pool, max_per_brand=1)
        if not batch:
            break
        ordered.extend(batch)
        batch_ids = {p["id"] for p in batch}
        pool = [p for p in pool if p["id"] not in batch_ids]
    return ordered


def search(raw_query: str) -> list:
    """The full pipeline: translate, then match (see _match_all), then
    cap per brand. Used by /agent/search, which only ever wants the
    plain result list - /search itself calls search_full() below for
    the extra fields (total_matches, total_brands, intent) the "load
    more" button needs."""
    return search_full(raw_query)["results"]


def search_full(raw_query: str, tier=None) -> dict:
    """Like search(), but also returns what the "load more" UI needs:
    the resolved intent (so a later search_more() call can skip the
    LLM translation step entirely) and the raw pre-cap match/brand
    counts (so the results page can honestly say how many real matches
    exist, not just how many are shown - see project memory,
    [[search_load_more_design]]).

    tier (see BRAND_TIERS) comes straight from the Work page's own
    Independent/Established chips, not from anything _resolve_intent
    extracted from the query text - stamped into intent right after
    resolution so it's just one more thing filter_products()/
    filter_by_name() already know how to honor, and so it round-trips
    into search_more() for free (the frontend already sends this same
    intent object back unchanged on every "load more" click)."""
    if not (raw_query or "").strip():
        return {"results": [], "total_matches": 0, "total_brands": 0,
                "intent": {}, "brand_links": []}
    intent = _resolve_intent(raw_query, translate_query(raw_query))
    if tier:
        intent["tier"] = tier
    brands = detect_brands(raw_query)
    if brands:
        intent["brands"] = brands
    matches = _match_all(raw_query, intent)
    if not matches:
        # The model sometimes invents a compound category that is no real
        # tag ("lamp for bedroom" -> "bedroom lamp"): retry with the head noun.
        words = (intent.get("category") or "").split()
        if len(words) > 1:
            fallback = dict(intent, category=words[-1])
            retried = _match_all(raw_query, fallback)
            if retried:
                intent, matches = fallback, retried
    return {
        "results": cap_per_brand(matches),
        "total_matches": len(matches),
        "total_brands": len({m["brand"] for m in matches}),
        "intent": intent,
        "brand_links": brand_links(intent),
    }


def search_more(raw_query: str, intent: dict, exclude_ids) -> list:
    """Continuation of an existing /search call, for the "load more"
    button. Takes the intent /search already resolved (no second LLM
    call) and the ids of everything shown so far, re-runs the same
    matching pipeline, and returns whatever's left, ordered by
    round_robin_order() so the brand mix stays fair all the way to the
    end - see that function's docstring for why a flat per-round cap
    isn't used here instead."""
    matches = _match_all(raw_query, intent)
    exclude = {str(x) for x in exclude_ids}
    remaining = [m for m in matches if str(m["id"]) not in exclude]
    return round_robin_order(remaining)
