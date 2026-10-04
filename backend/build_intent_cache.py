"""
Builds backend/intent_cache.json - prepared readings of common search queries.

Every search first asks an LLM to read the query into structured intent
(~1s). The reading of a given query never changes for a given model and
prompt, so the common ones are read once here, offline, and shipped with the
backend: the server loads the file at start-up and answers them with no LLM
call (anything new is learned in memory). The file records the prompt hash and
model it was made with - query_engine ignores it if either has changed, so
re-run this script after editing the system prompt or switching model.

Seed queries: the object-type words the scraper knows (+ plurals), every Edit
and Browse page title, the ad-style multi-word phrases, and a core set.

RUN (needs the LLM API key in backend/.env, ~600 cheap calls, about a minute):
    python3 build_intent_cache.py
"""

import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))

import query_engine as qe  # noqa: E402

CORE = [
    "table lamp", "sofa", "round coffee table", "pendant lamp", "two seater sofa", "three seater sofa",
    "oak dining table", "black chair", "floor lamp", "ceiling lamp", "wall light", "candle holder",
    "footstool", "rug", "mirror", "bowl", "vase", "ceramic vase", "modern vase", "contemporary ceramics",
    "minimalist lamp", "ball lamp", "scandinavian dining table", "scandinavian lighting", "swedish chair",
    "nordic lighting", "portable lamp", "wood sofa", "designer lighting", "danish furniture",
    "house in sweden", "architect designed house", "new arrivals", "round dining table",
]


def seed_queries():
    import scrape
    import generate_browse_pages as browse
    import generate_themed_edit_pages as edits

    qs = set(CORE)
    qs.update(t["title"].lower() for t in edits.THEMES)
    qs.update(c["title"].lower() for c in browse.BROWSE_CATEGORIES)
    for phrase, _category in scrape.ENGLISH_OBJECT_TYPE_KEYWORDS:
        qs.add(phrase.lower())
    plurals = set()
    for q in qs:
        plurals.add(q if q.endswith("s") else q + ("es" if q.endswith(("ch", "sh", "x")) else "s"))
    qs |= plurals
    return sorted(qs)


def read_one(q):
    try:
        return q, qe._call_with_retry(q)
    except Exception as e:  # noqa: BLE001
        return q, f"ERR {type(e).__name__}"


def main():
    queries = seed_queries()
    print(f"{len(queries)} seed queries")
    intents, failed = {}, []
    with cf.ThreadPoolExecutor(6) as ex:
        for q, result in ex.map(read_one, queries):
            if isinstance(result, dict):
                intents[qe._normalise_query(q)] = result
            else:
                failed.append((q, result))
    out = {"prompt_hash": qe._PROMPT_HASH, "model": qe.LLM_MODEL, "intents": intents}
    qe.INTENT_CACHE_PATH.write_text(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True))
    print(f"wrote {len(intents)} readings to {qe.INTENT_CACHE_PATH.name}; {len(failed)} failed {failed[:5]}")


if __name__ == "__main__":
    main()
