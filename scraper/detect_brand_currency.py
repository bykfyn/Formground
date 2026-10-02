"""
Formground brand-currency detector.

WHAT THIS DOES: for every brand that has stored prices but no stored
currency, fetches a few of that brand's own product pages, reads the
currency from the page's schema.org Offer (priceCurrency) or the
og/product:price meta tags, and records it in scraper/brand_currency.json
ONLY when the page's own price matches the price we stored for that same
product.

WHY: Shopify's /products.json has no currency field (see
_shopify_price_info in scrape.py), so 16,403 stored prices across 121
brands had no currency and could not be published as an schema.org Offer
or agent-facing price (measured 2026-10-02: 18,791 priced products,
3,302 with currency). A store's declared currency can differ from the
prices its feed returns (Shopify Markets), so this never copies a
store-wide value blindly: the price on the page must equal the stored
price, which proves the currency belongs to the number we hold. A brand
that cannot be verified stays currency-less - never guessed.

POLITENESS: at most one request in flight per brand (sequential within a
brand, 1s apart), MAX_SAMPLES_PER_BRAND pages per brand, same HEADERS and
block-status handling as scrape.py; a block status ends that brand.

USED BY: scrape.py's run() loop fills currency from brand_currency.json
when an extractor left it empty. RUN:
    python3 detect_brand_currency.py            # all unresolved brands
    python3 detect_brand_currency.py "Serax"    # one brand
"""

import concurrent.futures
import datetime
import json
import re
import sys
import time
from pathlib import Path

import requests

from scrape import BLOCK_STATUS_CODES, HEADERS, setup_database

OUTPUT_PATH = Path(__file__).parent / "brand_currency.json"
MAX_SAMPLES_PER_BRAND = 4
MIN_MATCHES_TO_VERIFY = 2          # agreeing pages needed (1 if a brand only has 1 priced page)
MAX_CONCURRENT_BRANDS = 8
REQUEST_TIMEOUT = 15
DELAY_BETWEEN_REQUESTS = 1.0
PRICE_TOLERANCE = 0.01             # page price within 1% of the stored price

JSON_LD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
META_RE = re.compile(r'<meta[^>]+(?:property|name)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']', re.I)
META_RE_REVERSED = re.compile(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']([^"\']+)["\']', re.I)
CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")


def _parse_price(raw):
    """'1.234,50' / '1,234.50' / '249' / 249 -> float, or None."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = re.sub(r"[^\d.,]", "", str(raw))
    if not text:
        return None
    if "," in text and "." in text:
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        text = text.replace("." if decimal == "," else ",", "").replace(decimal, ".")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        text = f"{head}.{tail}" if len(tail) in (1, 2) else text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _walk_offers(node, found):
    """Collect (currency, [prices]) from any dict carrying priceCurrency."""
    if isinstance(node, list):
        for item in node:
            _walk_offers(item, found)
    elif isinstance(node, dict):
        currency = node.get("priceCurrency")
        if isinstance(currency, str) and CURRENCY_CODE_RE.match(currency.strip().upper()):
            prices = [_parse_price(node.get(k)) for k in ("price", "lowPrice", "highPrice")]
            prices = [p for p in prices if p is not None]
            if prices:
                found.append((currency.strip().upper(), prices))
        for value in node.values():
            if isinstance(value, (dict, list)):
                _walk_offers(value, found)


def extract_page_offers(page_html):
    """-> list of (currency, [prices]) the page itself declares."""
    found = []
    for block in JSON_LD_RE.findall(page_html):
        try:
            _walk_offers(json.loads(block.strip()), found)
        except ValueError:
            continue
    metas = {}
    for name, content in META_RE.findall(page_html):
        metas.setdefault(name.lower(), content)
    for content, name in META_RE_REVERSED.findall(page_html):
        metas.setdefault(name.lower(), content)
    for cur_key, price_key in (
        ("product:price:currency", "product:price:amount"),
        ("og:price:currency", "og:price:amount"),
    ):
        currency, price = metas.get(cur_key), _parse_price(metas.get(price_key))
        if currency and CURRENCY_CODE_RE.match(currency.strip().upper()) and price is not None:
            found.append((currency.strip().upper(), [price]))
    return found


def _matches(stored_price, page_prices):
    return any(abs(p - stored_price) <= max(0.01, PRICE_TOLERANCE * stored_price) for p in page_prices)


def detect_for_brand(brand, samples):
    """samples: [(product_url, stored_price)]. -> result dict."""
    matched, checked, blocked = [], 0, False
    for url, stored in samples[:MAX_SAMPLES_PER_BRAND]:
        if checked:
            time.sleep(DELAY_BETWEEN_REQUESTS)
        checked += 1
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            continue
        if resp.status_code in BLOCK_STATUS_CODES:
            blocked = True
            break
        if resp.status_code != 200:
            continue
        for currency, prices in extract_page_offers(resp.text):
            if _matches(stored, prices):
                matched.append(currency)
                break
    currencies = set(matched)
    needed = min(MIN_MATCHES_TO_VERIFY, len(samples))
    if len(currencies) == 1 and len(matched) >= needed:
        return {"brand": brand, "currency": matched[0], "matches": len(matched), "checked": checked}
    reason = "blocked" if blocked else ("conflicting currencies" if len(currencies) > 1 else "no price match")
    return {"brand": brand, "currency": None, "matches": len(matched), "checked": checked, "reason": reason}


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    existing = json.loads(OUTPUT_PATH.read_text()) if OUTPUT_PATH.exists() else {}
    conn = setup_database()
    rows = conn.execute(
        "SELECT brand, product_url, price FROM products "
        "WHERE price IS NOT NULL AND price > 0 AND (currency IS NULL OR currency = '') "
        "AND COALESCE(link_dead, 0) = 0 ORDER BY brand, id"
    ).fetchall()
    conn.close()
    by_brand = {}
    for brand, url, price in rows:
        by_brand.setdefault(brand, []).append((url, price))
    todo = {b: s for b, s in by_brand.items() if (only is None or b == only) and b not in existing}
    # Spread samples across each brand's catalog rather than taking the first N.
    for b, s in todo.items():
        step = max(1, len(s) // MAX_SAMPLES_PER_BRAND)
        todo[b] = s[::step]
    print(f"{len(todo)} brands to check ({sum(len(v) for v in by_brand.values())} priced products without currency)")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BRANDS) as pool:
        for r in pool.map(lambda kv: detect_for_brand(*kv), todo.items()):
            results.append(r)
            status = r["currency"] or f"UNRESOLVED ({r['reason']})"
            print(f"  {r['brand']}: {status} [{r['matches']}/{r['checked']} pages matched]")
    today = datetime.date.today().isoformat()
    for r in results:
        if r["currency"]:
            existing[r["brand"]] = {"currency": r["currency"], "verified_matches": r["matches"], "checked": today}
    OUTPUT_PATH.write_text(json.dumps(dict(sorted(existing.items())), indent=2, ensure_ascii=False) + "\n")
    resolved = sum(1 for r in results if r["currency"])
    print(f"Resolved {resolved} of {len(results)} brands -> {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
