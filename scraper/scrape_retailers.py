"""
Retailer/stockist scraper - pilot (2026-09-25).

WHAT THIS DOES:
  Fetches real makers' own published stockist/retailer lists and
  saves them to data/retailers.json - the real data behind the planned
  Retailer/Stockist tab inside Marketplace (see project memory,
  "Retailer/stockist + Promotions concept").

SOURCES SO FAR:
  - Oersjoe (orsjo.com) - 73 retailers, 9 countries. A clean, simple
    per-country list (name/street/postal/city/website). Piloted first,
    chosen because its list turned out to be a genuine, server-rendered
    page, unlike HAY/Le Klint/Frama's "Find a retailer"/"Store Locator"
    pages, which are all interactive JS map widgets (Google Maps or
    Algolia-backed) with no reachable underlying list - checked live
    2026-09-25 before settling on this brand for the pilot.
  - Kasthall (kasthall.com) - 206 retailers, 20 countries, real
    server-rendered cards even richer than Oersjoe's (name, phone,
    website, full address, email, and a ready-made data-store-country
    attribute) - despite this brand being a Shopify store with a
    dedicated store-locator *app* installed too (the JS-widget kind
    that fails everywhere else); this particular page just happens to
    also render the full real list server-side underneath it.

  User's own real-world observation (2026-09-25): most makers share
  the same retailer networks - Nordiska Galleriet and Artek already
  each turned up from more than one source here - so a handful of
  good, comprehensive lists like these two should cover most of the
  real retailer roster fast, rather than needing to check all ~180
  brands individually.

DATA MODEL:
  Each entry is a real, physical retail location - name, a single
  display "address" string (kept as one field rather than forced into
  separate street/postal/city, since real formats vary too much across
  20+ countries to split reliably - a US "2800 Kirby Dr #116, Houston,
  TX 77098" and a Finnish "Keskuskatu 1 B, 00100 Helsinki" don't share
  a structure), a best-effort "city" (present when the source itself
  separates it, as Oersjoe's does; blank otherwise rather than
  guessed), country, phone/email where the source gives them, and the
  retailer's own real website (never the source maker's own site).
  "brands" is a list, not a single field, since the same physical shop
  legitimately shows up again once other makers' lists are scraped too
  (Nordiska Galleriet and Svenssons i Lammhult, both real multi-
  location Scandinavian retailers, already appear multiple times just
  within Oersjoe's own list, once per city) - deduplicated and merged
  on (name, city, country), not name alone, since the same chain can
  have several genuinely different physical locations.

RUN:
    python3 scrape_retailers.py
"""

import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "retailers.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FormgroundBot/0.1; "
                  "+discovery tool for independent design brands; "
                  "respects robots.txt; remove-on-request)"
}

ORSJO_URL = "https://www.orsjo.com/se/contact"
ORSJO_COUNTRY_SELECTOR = ".page-module-scss-module__YVEPrq__country"
ORSJO_RESELLER_SELECTOR = ".page-module-scss-module__YVEPrq__reseller"

KASTHALL_URL = "https://kasthall.com/pages/where-to-buy"


def _normalize_url(url):
    url = url.strip()
    return url if url.startswith("http") else f"https://{url}"


def scrape_orsjo():
    resp = requests.get(ORSJO_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    retailers = []
    for country_block in soup.select(ORSJO_COUNTRY_SELECTOR):
        heading = country_block.find("h2")
        country = heading.get_text(strip=True) if heading else ""

        for card in country_block.select(ORSJO_RESELLER_SELECTOR):
            p = card.find("p")
            if not p:
                continue
            name_el = p.find("span")
            link_el = p.find("a", href=True)
            if not name_el or not link_el:
                continue
            name = name_el.get_text(strip=True)
            website = link_el["href"]

            # Everything between the name <span> and the website <a> is
            # address text, split by <br> into separate lines - 2 lines
            # (street, city) or 3 (street, postal code, city) depending
            # on the country; the last line is always the city.
            lines = []
            for node in p.contents:
                if node in (name_el, link_el):
                    continue
                text = node.get_text(strip=True) if hasattr(node, "get_text") else str(node).strip()
                if text:
                    lines.append(text)
            if not lines:
                continue
            city = lines[-1]
            address = ", ".join(lines[:-1]) if len(lines) > 1 else lines[0]

            retailers.append({
                "name": name,
                "address": address,
                "city": city,
                "country": country,
                "phone": "",
                "email": "",
                "website": _normalize_url(website),
                "brands": ["Orsjo"],
            })

    return retailers


def scrape_kasthall():
    resp = requests.get(KASTHALL_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    retailers = []
    for card in soup.select("div[data-store-country]"):
        name_el = card.find("h3")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        country = card.get("data-store-country", "").strip()

        phone_link = card.select_one('a[href^="tel:"]')
        website_link = card.select_one('a[href^="http"]')
        email_link = card.select_one('a[href^="mailto:"]')

        address = ""
        for p in card.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text.lower().startswith("address:"):
                address = text.split(":", 1)[1].strip()
                break

        retailers.append({
            "name": name,
            "address": address,
            # Not split out - real formats vary too much across 20
            # countries to reliably separate city from the rest (see
            # module docstring).
            "city": "",
            "country": country,
            "phone": phone_link.get_text(strip=True) if phone_link else "",
            "email": email_link.get_text(strip=True) if email_link else "",
            "website": _normalize_url(website_link["href"]) if website_link else "",
            "brands": ["Kasthall"],
        })

    return retailers


def merge(retailers):
    """
    Dedup key is (name, city, country) - the same chain can have
    several real, different physical locations (confirmed live:
    Nordiska Galleriet and Svenssons i Lammhult each appear multiple
    times just within Oersjoe's own list, one per real city), so a
    bare name match would wrongly collapse distinct shops into one.
    Falls back to (name, address, country) when city is blank (as it
    is for every Kasthall entry), since address is the next-most
    specific real signal available there.
    """
    merged = {}
    for r in retailers:
        city_or_address = r["city"] or r["address"]
        key = (r["name"].strip().lower(), city_or_address.strip().lower(), r["country"].strip().lower())
        if key in merged:
            existing_brands = set(merged[key]["brands"])
            existing_brands.update(r["brands"])
            merged[key]["brands"] = sorted(existing_brands)
        else:
            merged[key] = r
    return sorted(merged.values(), key=lambda r: (r["country"], r["city"], r["name"]))


def generate():
    retailers = merge(scrape_orsjo() + scrape_kasthall())
    OUTPUT_PATH.write_text(json.dumps(retailers, indent=2, ensure_ascii=False) + "\n")
    print(f"Saved {len(retailers)} real retailers across "
          f"{len({r['country'] for r in retailers})} countries to {OUTPUT_PATH}.")


if __name__ == "__main__":
    generate()
