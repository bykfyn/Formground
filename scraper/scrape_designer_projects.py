"""
Pilot (2026-10-12): a designer's own project index as a source of PIECES, for makers we do not scrape (blocked, or too large to
show whole). Konstantin Grcic's site lists every project as "Title / Type / Maker Year" in one page; the current products,
furniture and lighting become pieces shown ONLY on his designer page (never as Work or search results), each credited to its
maker and linked to the maker's page when one is supplied in data/designer_piece_links.csv, otherwise to the project page on his site.

    python3 scraper/scrape_designer_projects.py

Writes data/designer_pieces.json (read by generate_designers_pages.py) and refreshes data/designer_piece_links.csv, keeping any
maker_url already filled in. Exhibitions, commissions, art direction, fashion and limited editions are left out.
"""

import csv
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "designer_pieces.json"
LINKS = ROOT / "data" / "designer_piece_links.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

DESIGNERS = {
    "Konstantin Grcic": {"url": "https://konstantin-grcic.com", "index": "https://konstantin-grcic.com/projects/",
                         "types": {"Product", "Furniture", "Lighting"}},
    "Jasper Morrison": {"url": "https://jaspermorrison.com", "site": "morrison",
                        "links": [{"label": "Jasper Morrison Shop", "url": "https://www.jaspermorrisonshop.com"}],
                        "categories": ["chairs", "sofas", "tables", "storage", "lighting", "kitchenware", "accessories", "electrical"]},
}


def biggest(srcset):
    best = (0, "")
    for part in srcset.split(","):
        bits = part.strip().split()
        if len(bits) == 2 and bits[1].endswith("w") and int(bits[1][:-1]) > best[0]:
            best = (int(bits[1][:-1]), bits[0])
    return best[1]


def grcic_pieces(cfg):
    resp = requests.get(cfg["index"], headers=HEADERS, timeout=90)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    pieces = []
    for art in soup.select("article.project"):
        slug = art["id"].split("/projects/")[-1]
        head = art.select_one(".note-heading button")
        parts = [p.strip() for p in re.sub(r"\s+", " ", head.get_text(" ", strip=True) if head else "").split(" / ")]
        if len(parts) < 3 or parts[1] not in cfg["types"]:
            continue
        maker = re.sub(r"\s*(?:19|20)\d\d\s*$", "", parts[2]).strip()
        year = (re.search(r"(?:19|20)\d\d", parts[2]) or re.search(r"(?:19|20)\d\d", " ".join(parts)) or [""])[0]
        image, credit = "", ""
        for img in art.select("img[data-src]"):
            image = biggest(img.get("data-srcset", "")) or img["data-src"]
            credit = img.get("data-credits", "")
            if image:
                break
        if not image:
            continue
        pieces.append({"title": parts[0], "slug": slug, "type": parts[1], "maker": maker, "year": year, "image": image,
                       "credit": credit, "project_url": f"{cfg['url']}/projects/{slug}", "maker_url": ""})
    return pieces


def morrison_pieces(cfg):
    """Category pages list the projects; each project page names the maker ("Produced by Vitra, Switzerland"), year and hero photo.
    One request per project, paced, since the site has no single index."""
    pieces, seen = [], set()
    for cat in cfg["categories"]:
        links, n = [], 1
        while True:                          # 9 projects a page: /projects/chairs, /projects/chairs/page:2, ...
            path = f"{cfg['url']}/projects/{cat}" + (f"/page:{n}" if n > 1 else "")
            cards = BeautifulSoup(requests.get(path, headers=HEADERS, timeout=60).text, "html.parser").select(".c-info-card a[href]")
            fresh = [a["href"] for a in cards if a["href"] not in links]
            if not fresh:
                break
            links += fresh
            n += 1
            time.sleep(0.3)
        for url in links:
            if url in seen:
                continue
            seen.add(url)
            time.sleep(0.4)
            page = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=60).text, "html.parser")
            title = page.select_one(".meta__heading")
            made = next((li.get_text(" ", strip=True) for li in page.select(".meta__links li") if li.get_text().strip().startswith("Produced by")), "")
            hero = page.select_one("figure.hero-image img")
            if not (title and made and hero):
                continue
            maker = re.sub(r"^Produced by\s+", "", made).split(",")[0].strip()
            year = (re.search(r"(?:19|20)\d\d", (page.select_one(".date") or title).get_text()) or [""])[0]
            pieces.append({"title": title.get_text(strip=True), "slug": f"{cat}/{url.rsplit('/', 1)[-1]}", "type": cat.title(),
                           "maker": maker, "year": year, "image": hero["src"], "credit": "", "project_url": url, "maker_url": ""})
    return pieces


def main():
    out = {}
    for name, cfg in DESIGNERS.items():
        out[name] = {"url": cfg["url"], "links": cfg.get("links", []), "pieces": morrison_pieces(cfg) if cfg.get("site") == "morrison" else grcic_pieces(cfg)}
        print(f"{name}: {len(out[name]['pieces'])} pieces")
    existing = {}
    if LINKS.exists():
        with LINKS.open(newline="") as f:
            existing = {(r["designer"], r["slug"]): r["maker_url"] for r in csv.DictReader(f)}
    for name, data in out.items():
        for p in data["pieces"]:
            p["maker_url"] = existing.get((name, p["slug"]), "").strip()
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    with LINKS.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["designer", "slug", "piece", "maker", "year", "maker_url"])
        for name, data in out.items():
            for p in sorted(data["pieces"], key=lambda p: (p["maker"].lower(), p["title"].lower())):
                w.writerow([name, p["slug"], p["title"], p["maker"], p["year"], p["maker_url"]])
    print(f"wrote {OUT.name} and {LINKS.name}")


if __name__ == "__main__":
    sys.exit(main())
