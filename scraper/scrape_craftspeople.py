"""
Craftspeople scraper - Formground's own copy of the Joiners &
Craftspeople data, previously built and maintained in the separate
Archframe project.

WHAT THIS DOES:
  Fetches two real, already-vetted Swedish craft/production
  associations - Interior Cluster Sweden and Föreningen
  Skråhantverkarna - saves each source's raw member listing to
  data/sources/*.json, then merges them into one deduplicated
  data/craftspeople.json: the real data behind Formground's Joiners &
  Craftspeople section (see generate_craftspeople_pages.py for the
  pages built from it).

WHY THIS EXISTS HERE, NOT IN ARCHFRAME:
  Per the 2026-09-17 ecosystem pivot, this tier now belongs to
  Formground itself (a section, not a separate product/domain) - so
  Formground owns and re-runs this scrape on its own schedule, the
  same way it already owns its 74 maker-brand scrapers, rather than
  staying dependent on a second, separately-maintained codebase.
  Scraping/merge logic ported directly from
  archframe/scraper/scrape_interior_cluster.py,
  scrape_skrahantverkarna.py, and merge_partners.py - see those files'
  own docstrings for the fuller story of each source's selectors and
  the WOG Metall / WOG Trä merge-key lesson. Archframe/sheerd.world
  keeps running unchanged; this is a fork of the data pipeline, not a
  migration that removes anything from Archframe.

DATA MODEL:
  Each entry is a craftsperson/workshop entity - name, craft area
  tag(s), country/city where known, external website, real photo, and
  which association(s) it was found via (a company found through more
  than one association is a legitimacy signal, unioned rather than
  duplicated - see merge()).

CRAFT RELEVANCE FILTER:
  Not every craft Skråhantverkarna lists belongs on Formground - the
  same category-by-category allowlist already agreed on the Archframe
  side (RELEVANT_AREAS_BY_ASSOCIATION below) carries over unchanged.
  Interior Cluster needs no filter; it's already a furniture-industry
  cluster.

RUN:
    python3 scrape_craftspeople.py
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data"
SOURCES_DIR = DATA_DIR / "sources"
OUTPUT_PATH = DATA_DIR / "craftspeople.json"

INTERIOR_CLUSTER_URL = "https://interiorcluster.se/medlemmar"
TARGET_MEDLEMSTYP = "underleverantör"
IC_PLACEHOLDER_IMAGE = "medlemsbild_1080x6802.jpg"

SKRA_LISTING_URL = "https://skrahantverkarna.se/all-listing/"
SKRA_REQUEST_DELAY_SECONDS = 0.2
SWEDISH_POSTCODE = re.compile(r"^\d{3}\s?\d{2}\s+")

MERGEABLE_FIELDS = ["city", "country", "website", "image_url", "areas"]

# Ported unchanged from archframe/scraper/merge_partners.py - agreed
# with the user category-by-category before it was first built there.
# An association with no entry here is unfiltered.
RELEVANT_AREAS_BY_ASSOCIATION = {
    "skrahantverkarna": {
        "Bildhuggeri", "Ciselör", "Damastvävare", "Dekorationsmålare",
        "Finsnickare", "Förgyllare", "Inredningssnickare", "Konservator",
        "Konstgjutare", "Konstglasmästare", "Konstinramare",
        "Kopparslagarmästare", "Korgmakare", "Metallkonservator",
        "Metallkonstnär", "Möbelrenoverare", "Möbelsnickare",
        "Rottingmöbelfabrikör", "Snickare", "Stenhuggare", "Stenmontör",
        "Tapetmakare", "Tapetserare",
    },
}


def _background_image_url(style_attr):
    if not style_attr:
        return None
    match = re.search(r'url\(["\']?(.*?)["\']?\)', style_attr)
    return match.group(1) if match else None


def scrape_interior_cluster():
    resp = requests.get(INTERIOR_CLUSTER_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    columns = [
        col for col in soup.select(".member-column")
        if (col.get("data-medlemstyp") or "").strip().lower() == TARGET_MEDLEMSTYP
    ]
    if not columns:
        raise RuntimeError(
            f'No .member-column elements found with data-medlemstyp="{TARGET_MEDLEMSTYP}" - '
            "Interior Cluster's page structure may have changed."
        )

    partners = []
    for col in columns:
        name = (col.get("data-name") or "").strip()
        areas = [a.strip() for a in (col.get("data-omrade") or "").split("\t") if a.strip()]

        link_el = col.select_one(".button-primary a[href]")
        website = link_el["href"].strip() if link_el else None

        bg_el = col.select_one(".member-card-bg")
        image = _background_image_url(bg_el.get("style", "")) if bg_el else None
        if image and IC_PLACEHOLDER_IMAGE in image:
            image = None

        partners.append({
            "name": name,
            "areas": areas,
            "country": "Sweden",
            "website": website,
            "image_url": image,
            "associations": ["interior-cluster"],
        })

    (SOURCES_DIR / "interior_cluster.json").parent.mkdir(parents=True, exist_ok=True)
    (SOURCES_DIR / "interior_cluster.json").write_text(json.dumps(partners, ensure_ascii=False, indent=2))
    print(f"Interior Cluster: saved {len(partners)} partners.")
    return partners


def _split_address(raw_address):
    parts = [p.strip() for p in raw_address.split(",")]
    if len(parts) < 2:
        return raw_address.strip(), None
    street = ", ".join(parts[:-1])
    city = SWEDISH_POSTCODE.sub("", parts[-1]).strip()
    return street, city or None


def _contact_field(detail_soup, icon_class):
    li = detail_soup.select_one(f"div.atbd_contact_info li:has(span.{icon_class})")
    if not li:
        return None
    value_el = li.select_one(".atbd_info")
    if not value_el:
        return None
    link = value_el.find("a")
    return (link.get_text(strip=True) if link else value_el.get_text(strip=True)) or None


def _detail_website(detail_soup):
    li = detail_soup.select_one("div.atbd_contact_info li:has(span.la-globe)")
    if not li:
        return None
    link = li.select_one("a[href]")
    return link["href"].strip() if link else None


def scrape_skrahantverkarna():
    resp = requests.get(SKRA_LISTING_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cards = soup.select("div.atbd_single_listing")
    if not cards:
        raise RuntimeError(
            "No div.atbd_single_listing cards found - Skråhantverkarna's page "
            "structure may have changed."
        )

    partners = []
    for card in cards:
        title_link = card.select_one("h4.atbd_listing_title > a")
        name = title_link.get_text(strip=True) if title_link else None
        detail_url = title_link["href"] if title_link else None
        if not name or not detail_url:
            continue

        img_el = card.select_one(".atbd_listing_image img[src]")
        image = img_el["src"].strip() if img_el else None

        category_el = card.select_one(".atbd_listting_category a")
        area = category_el.get_text(strip=True) if category_el else None

        detail_resp = requests.get(detail_url, timeout=30)
        detail_resp.raise_for_status()
        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

        raw_address = _contact_field(detail_soup, "la-map-marker")
        _, city = _split_address(raw_address) if raw_address else (None, None)
        website = _detail_website(detail_soup)

        partners.append({
            "name": name,
            "areas": [area] if area else [],
            "city": city,
            "country": "Sweden" if city else None,
            "website": website,
            "image_url": image,
            "associations": ["skrahantverkarna"],
        })

        time.sleep(SKRA_REQUEST_DELAY_SECONDS)

    (SOURCES_DIR / "skrahantverkarna.json").write_text(json.dumps(partners, ensure_ascii=False, indent=2))
    print(f"Skråhantverkarna: saved {len(partners)} partners.")
    return partners


def is_relevant(partner):
    for association_id in partner.get("associations", []):
        allowlist = RELEVANT_AREAS_BY_ASSOCIATION.get(association_id)
        if allowlist is None:
            return True
        if allowlist.intersection(partner.get("areas", [])):
            return True
    return False


def normalize_website(url):
    if not url:
        return None
    parsed = urlparse(url if "://" in url else f"//{url}")
    domain = re.sub(r"^www\.", "", parsed.netloc.lower())
    path = parsed.path.rstrip("/")
    return f"{domain}{path}" if domain else None


def normalize_name(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def merge_key(partner):
    website_key = normalize_website(partner.get("website"))
    return f"website:{website_key}" if website_key else f"name:{normalize_name(partner['name'])}"


def merge_into(existing, incoming):
    for aid in incoming.get("associations", []):
        if aid not in existing["associations"]:
            existing["associations"].append(aid)
    for field in MERGEABLE_FIELDS:
        if not existing.get(field) and incoming.get(field):
            existing[field] = incoming[field]


def merge_and_filter(all_partners):
    merged = {}
    filtered_out = 0
    for partner in all_partners:
        if not is_relevant(partner):
            filtered_out += 1
            continue
        key = merge_key(partner)
        if key in merged:
            merge_into(merged[key], partner)
        else:
            merged[key] = {**partner, "associations": list(partner.get("associations", []))}

    partners = sorted(merged.values(), key=lambda p: p["name"].lower())
    OUTPUT_PATH.write_text(json.dumps(partners, ensure_ascii=False, indent=2))

    multi_association = sum(1 for p in partners if len(p["associations"]) > 1)
    print(
        f"Merged into {len(partners)} unique craftspeople ({multi_association} found via "
        f"more than one association, {filtered_out} excluded as not relevant) -> {OUTPUT_PATH}"
    )
    return partners


def main():
    interior_cluster = scrape_interior_cluster()
    skrahantverkarna = scrape_skrahantverkarna()
    merge_and_filter(interior_cluster + skrahantverkarna)


if __name__ == "__main__":
    main()
