"""
The next pages to request in Search Console, without the ones Google already has (2026-10-17).

Search Console's Pages report can export the list of INDEXED pages (Indexing > Pages > the "Indexed" row > Export > Download CSV).
Put the export (the Table.csv with the columns URL, Last crawled) in project-docs/GCS-indexed/. This script takes every address in
the sitemap that is not in any such file and has not already been ticked [x] in project-docs/Search_Console_Indexing_Requests.md
(the export runs a few days behind, so pages requested since are not in it yet), and orders them by the strategy's priority: hubs and type pages, Edits and Guides, makers' and designers' pages that
have a profile text, then the rest. It prints the next N (default 10) and writes nothing.

    python3 scraper/indexing_queue.py            # the next 10
    python3 scraper/indexing_queue.py -n 25
"""
import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scraper"))


def indexed_set(folder):
    out = set()
    for path in sorted(folder.glob("*.csv")):
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                if row and row[0].startswith("http"):
                    out.add(row[0].strip().rstrip("/").lower())
    return out


def requested_set(path):
    """Addresses already ticked [x] in the request log."""
    if not path.exists():
        return set()
    return {u.rstrip("/").lower() for u in re.findall(r"\[x\]\s+(https://formground\.com/\S+)", path.read_text())}


def role(url, texts):
    path = url.replace("https://formground.com", "")
    if path in ("/", "/work.html", "/work/furniture.html", "/work/lighting.html", "/work/objects.html", "/creators.html", "/edits.html", "/guides.html"):
        return 0
    if path.startswith("/work/"):
        return 1
    if path.startswith(("/edits/", "/guides/")):
        return 2
    slug = path.rsplit("/", 1)[-1].replace(".html", "")
    if path.startswith("/brands/"):
        return 3 if f"makers:{slug}" in texts else 5
    if path.startswith("/designers/"):
        return 3 if f"designers:{slug}" in texts else 5
    if path.startswith("/architects/"):
        return 4
    return 6


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=10)
    args = ap.parse_args()
    folder = ROOT / "project-docs" / "GCS-indexed"
    if not folder.exists() or not list(folder.glob("*.csv")):
        sys.exit("no export in project-docs/GCS-indexed/ yet: export the Indexed pages list from Search Console first (see the top of this file)")
    import creator_texts
    texts = set(creator_texts.load_all())
    have = indexed_set(folder) | requested_set(ROOT / "project-docs" / "Search_Console_Indexing_Requests.md")
    sitemap = (ROOT / "docs" / "sitemap.xml").read_text()
    todo = [u for u in re.findall(r"<loc>([^<]+)</loc>", sitemap) if u.rstrip("/").lower() not in have]
    lighting = re.compile(r"lamp|light|chandelier|pendant|sconce")       # the strategy leads with lighting (2026-10-17)
    todo.sort(key=lambda u: (role(u, texts), not lighting.search(u), u))
    print(f"{len(todo)} sitemap addresses are neither in the indexed export nor already requested ({len(have)} addresses known). Next {args.n}:")
    for u in todo[:args.n]:
        print("  -", u)


if __name__ == "__main__":
    main()
