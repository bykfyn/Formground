"""
Generates project-docs/Brand_Status.csv - a human-readable, spreadsheet-
editable table of every brand looked at so far (brands.json), with a
live product count from the actual database where available.

Run manually whenever brands.json changes and you want an updated
review table (not wired into the scrape/check-link workflows - this is
a personal review doc, not something that needs to regenerate on every
run):

    python scraper/generate_brand_status.py
"""

import csv
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BRANDS_JSON = BASE_DIR / "scraper" / "brands.json"
DB_PATH = BASE_DIR / "data" / "formground.db"
OUT_CSV = BASE_DIR / "project-docs" / "Brand_Status.csv"

# Brands considered but never added to brands.json at all (no matching
# site was ever found), kept here so the table stays a complete record
# of everything looked at, not just what made it into the scraper.
NOT_FOUND = [
    {
        "name": "20by8",
        "notes": "No matches found across multiple search attempts and spelling variants - not a design brand, ceramics studio, or maker under any tried search.",
    }
]


def classify_status(brand):
    if brand.get("scrapable"):
        return "Live"
    notes = brand.get("notes", "")
    if "robots.txt" in notes or "Cloudflare" in notes or "bot management" in notes:
        return "Excluded (blocked)"
    if "Deferred" in notes or "deferred" in notes:
        return "Deferred"
    return "Excluded"


def load_counts():
    if not DB_PATH.exists():
        return {}
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT brand, COUNT(*) FROM products GROUP BY brand")
    counts = dict(cur.fetchall())
    con.close()
    return counts


def main():
    brands = json.loads(BRANDS_JSON.read_text())
    counts = load_counts()

    rows = []
    for b in brands:
        status = classify_status(b)
        rows.append(
            {
                "Brand": b["name"],
                "Status": status,
                "Product Count": counts.get(b["name"], "") if status == "Live" else "",
                "Country": b.get("country", ""),
                "URL": b.get("url", ""),
                "Notes": b.get("notes", ""),
            }
        )

    for b in NOT_FOUND:
        rows.append(
            {
                "Brand": b["name"],
                "Status": "Not found",
                "Product Count": "",
                "Country": "",
                "URL": "",
                "Notes": b["notes"],
            }
        )

    rows.sort(key=lambda r: r["Brand"])

    OUT_CSV.parent.mkdir(exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Brand", "Status", "Product Count", "Country", "URL", "Notes"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
