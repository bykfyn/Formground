"""
Stockist LEADS loader - records a maker's own published list of stockists in
the database WITHOUT publishing it anywhere.

WHAT THIS DOES: fetches a maker's own "stores" page and saves every listed
location into the `stockist_leads` table of data/formground.db. Nothing reads
that table: no generator, no page, no API route. It exists so the list is not
lost, and so the real follow-up - finding each retailer's own website - can
be done later and in bulk.

WHY NOT retailers.json / THE MARKETPLACE: user decision 2026-10-03 - a
stockist with no link of its own is not shown ("stockists are a nice to have,
not a must have"; every result links to a firm's OWN site). A row here has
website NULL and website_status 'needs_site'; when someone finds the site,
set website + website_status='found', and only THEN promote the row into
retailers.json.

SOURCES SO FAR:
  - Magis (magisdesign.com/stores/): 488 server-rendered locations (462
    retailers, 23 sales agents, 2 showrooms, headquarters), with name,
    address, phone, email and coordinates - but NO websites.

RUN (idempotent; never overwrites a website someone has filled in):
    python3 scrape_stockist_leads.py
Find rows still waiting for a website:
    SELECT brand, name, country FROM stockist_leads WHERE website_status = 'needs_site';
"""

import datetime
import re

import requests
from bs4 import BeautifulSoup

from scrape import HEADERS, _site_robots, setup_database

SOURCES = [
    {"brand": "Magis", "base": "https://www.magisdesign.com", "path": "/stores/"},
]

COUNTRY_FIXES = {"turchia": "Turkey", "usa": "United States", "serbia and montenegro": "Serbia"}


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stockist_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            name TEXT NOT NULL,
            kind TEXT,
            address TEXT,
            country TEXT,
            phone TEXT,
            email TEXT,
            lat REAL,
            lng REAL,
            source_url TEXT,
            fetched_at TEXT,
            website TEXT,
            website_status TEXT DEFAULT 'needs_site',
            UNIQUE (brand, name, lat, lng)
        )
    """)
    conn.commit()


def parse_magis_stores(page_html):
    """-> list of dicts, one per .marker element on Magis's /stores/ page."""
    soup = BeautifulSoup(page_html, "html.parser")
    rows = []
    for el in soup.select(".marker[data-lat]"):
        title = el.select_one(".title")
        para = el.select_one("p.address")
        if not title:
            continue
        lines = [re.sub(r"\s+", " ", x).strip() for x in (para.get_text("\n").split("\n") if para else [])]
        lines = [x for x in lines if x]
        phone = next((x[2:].strip() for x in lines if x.startswith("T ")), None)
        address_lines = [x for x in lines if not x.startswith(("T ", "Email", "Directions"))]
        country = None
        if address_lines:
            # "72015 Fasano - Italy" (the usual shape), else a trailing
            # ", Italy"; the candidate must be a short, letters-only word or
            # two (an address can contain a dash or commas of its own).
            m = (re.search(r"\s-\s([A-Za-z][A-Za-z .']{1,30})$", address_lines[-1])
                 or re.search(r",\s*([A-Za-z][A-Za-z .']{1,30})$", address_lines[-1]))
            if m:
                country = m.group(1).strip()
                country = COUNTRY_FIXES.get(country.lower(), country)
        mail = para.find("a", href=re.compile(r"^mailto:", re.I)) if para else None
        try:
            lat, lng = float(el["data-lat"]), float(el["data-lng"])
        except (KeyError, ValueError):
            continue
        rows.append({
            "name": title.get_text(strip=True), "kind": el.get("data-icon"),
            "address": ", ".join(address_lines) or None, "country": country,
            "phone": phone, "email": mail["href"][7:].strip() if mail else None,
            "lat": lat, "lng": lng,
        })
    return rows


def main():
    conn = setup_database()
    ensure_table(conn)
    today = datetime.date.today().isoformat()
    for src in SOURCES:
        url = src["base"] + src["path"]
        robots = _site_robots(src["base"])
        if not robots.can_fetch("FormgroundBot", url):
            print(f"{src['brand']}: robots.txt disallows {url} - skipping.")
            continue
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        rows = parse_magis_stores(resp.text)
        for r in rows:
            conn.execute("""
                INSERT INTO stockist_leads (brand, name, kind, address, country, phone, email, lat, lng, source_url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (brand, name, lat, lng) DO UPDATE SET
                    kind = excluded.kind, address = excluded.address, country = excluded.country,
                    phone = excluded.phone, email = excluded.email, fetched_at = excluded.fetched_at
            """, (src["brand"], r["name"], r["kind"], r["address"], r["country"], r["phone"], r["email"],
                  r["lat"], r["lng"], url, today))
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM stockist_leads WHERE brand = ?", (src["brand"],)).fetchone()[0]
        print(f"{src['brand']}: parsed {len(rows)} locations; {total} rows now in stockist_leads.")
    conn.close()


if __name__ == "__main__":
    main()
