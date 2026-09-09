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
  3. Among that filtered set, do a live pass for style descriptors
     (e.g. "minimalist", "linear") - these are judgment calls, so they're
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

import json
import os
import random
import re
import sqlite3
from pathlib import Path

import requests
from dotenv import load_dotenv

# Picks up backend/.env locally if present (see .env.example) - does
# nothing if there's no .env file, so this is a no-op in production
# environments (Cloud Run etc.) that set real environment variables directly.
load_dotenv()

DB_PATH = Path(__file__).parent.parent / "data" / "formground.db"

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


def _call_anthropic(system_prompt: str, raw_query: str) -> str:
    response = requests.post(
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
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


def _call_openai(system_prompt: str, raw_query: str) -> str:
    response = requests.post(
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


def translate_query(raw_query: str) -> dict:
    """
    Sends the raw query to whichever LLM is configured (see LLM_PROVIDER/
    LLM_MODEL above) and gets back structured intent. Works the same
    whether raw_query came from a human typing in the ask-box or an
    agent's structured request converted to text.
    """
    system_prompt = (
        "You translate a search query about independent design/furniture "
        "products into structured JSON with these fields: "
        "category (string or null), material (string or null), "
        "style_descriptors (list of strings, e.g. ['minimalist', 'linear']), "
        "color (string or null). "
        "Respond ONLY with the JSON object, nothing else."
    )

    caller = LLM_CALLERS.get(LLM_PROVIDER)
    if caller is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}' - supported: {list(LLM_CALLERS)}"
        )

    text = caller(system_prompt, raw_query)
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


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
        "lighting": ("lamp", "light", "sconce", "pendant", "chandelier",
                     "surface mount", "flush mount", "wall mount"),
        "furniture": ("chair", "table", "stool", "bench", "sofa", "armchair",
                      "ottoman", "console", "bookcase", "modular unit",
                      "seat", "seating", "screen", "desk", "storage",
                      "shelving", "furniture"),
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

    return False


def filter_products(intent: dict) -> list:
    """
    Filters stored products on the hard facts: category + material + has
    a real image. A missing image isn't just a display gap - the whole
    "thumbnail + link-back" model this tool is built on doesn't work
    without one, and in practice a missing image reliably means the
    listing is either a spare-parts/replacement SKU or genuine dead
    weight on the source site (confirmed live: In Common With's
    imageless records are all "Replacement"/"Hidden"-tagged hardware,
    and Another Country's are either that or literal leftover test
    listings like "test 3" and "Product"). Checked before adding this:
    no brand loses all its results, and no brand relies on its imageless
    records to be discoverable at all.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    wanted_category = (intent.get("category") or "").strip()
    wanted_material = (intent.get("material") or "").strip().lower()
    # translate_query() extracts color as its own field, separate from
    # material - it was being parsed and then silently thrown away here,
    # so a query like "black chair" filtered on category alone and could
    # return a chair with no black option at all (confirmed live: "black
    # surface mount" returned In Common With's Mira Surface Mount, which
    # has zero "black" anywhere in its material_options). Checked the same
    # way material is - color names are already embedded in the same
    # compound material_options strings (e.g. "Black / Bone / Hardwire").
    wanted_color = (intent.get("color") or "").strip().lower()

    products = []
    for row in rows:
        product = dict(row)

        if not product["image_url"]:
            continue
        if wanted_category and not _category_matches(product["category"], wanted_category):
            continue
        if wanted_material and wanted_material not in product["material_options"].lower():
            continue
        if wanted_color and wanted_color not in product["material_options"].lower():
            continue

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
    return products


def filter_by_name(raw_query: str) -> list:
    """
    Matches the raw query directly against each product's own name,
    independent of the category/material hard filter above. Confirmed
    live: searching "vaso" for Bitossi Ceramiche's own product literally
    named "Vaso" returned nothing, because filter_products() only ever
    checks category/material - it never looks at product_name at all.
    Category mismatches (Bitossi categorizes by collection line, not
    object type) are a real, separate, harder problem, but a literal
    name match should never depend on solving that first - if the
    product is literally called what the user typed, that's as strong a
    signal as search gets.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products WHERE image_url != ''").fetchall()
    conn.close()

    matches = []
    for row in rows:
        product = dict(row)
        if re.search(rf"\b{re.escape(product['product_name'])}\b", raw_query, re.IGNORECASE):
            product["material_options"] = json.loads(product["material_options"] or "[]")
            product["thin"] = bool(product["thin"])
            matches.append(product)
    return matches


def discover(per_brand: int = DISCOVER_PER_BRAND) -> list:
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
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products WHERE image_url != ''").fetchall()
    conn.close()

    by_brand = {}
    for row in rows:
        product = dict(row)
        product["material_options"] = json.loads(product["material_options"] or "[]")
        product["thin"] = bool(product["thin"])
        by_brand.setdefault(product["brand"], []).append(product)

    sampled = []
    for brand_products in by_brand.values():
        sampled.extend(random.sample(brand_products, min(per_brand, len(brand_products))))

    random.shuffle(sampled)
    return sampled


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


def search(raw_query: str) -> list:
    """The full pipeline: translate, then filter (category/material hard
    facts, plus a direct name match - see filter_by_name), then cap per
    brand. Style-matching over the filtered set is a future step, once
    there's enough real product data to make it meaningful."""
    intent = translate_query(raw_query)
    matches = filter_products(intent)

    seen_ids = {m["id"] for m in matches}
    for m in filter_by_name(raw_query):
        if m["id"] not in seen_ids:
            matches.append(m)
            seen_ids.add(m["id"])

    return cap_per_brand(matches)
