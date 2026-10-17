"""
IndexNow ping (2026-10-17): tells Bing, Yandex, Naver and the other IndexNow engines which pages changed, right after a push, so
they crawl them within minutes instead of days. Google does not use IndexNow (its manual requests stay manual).

The addresses sent are the sitemap entries whose "lastmod" changed in the last commit (data/sitemap_lastmod.json), so a push that
changes 40 pages pings those 40. The key file is docs/<key>.txt (public by design: it proves the site is ours).

    python3 scraper/indexnow_ping.py                  # the pages changed in the last commit (HEAD~1 -> HEAD)
    python3 scraper/indexnow_ping.py --since HEAD~5   # everything changed since a commit
    python3 scraper/indexnow_ping.py --all            # every sitemap address (the first time, or after a big rebuild)
    python3 scraper/indexnow_ping.py --dry-run        # print, send nothing
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
HOST = "formground.com"
ENDPOINT = "https://api.indexnow.org/IndexNow"


def key():
    files = [p for p in (ROOT / "docs").glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", p.stem)]
    if len(files) != 1:
        sys.exit("expected exactly one IndexNow key file docs/<32 hex>.txt")
    return files[0].stem


def lastmods(ref=None):
    if ref is None:
        return json.loads((ROOT / "data" / "sitemap_lastmod.json").read_text())
    out = subprocess.run(["git", "show", f"{ref}:data/sitemap_lastmod.json"], cwd=ROOT, capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else {}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="HEAD~1")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    now = lastmods()
    if args.all:
        urls = list(now)
    else:
        before = lastmods(args.since)
        urls = [u for u, v in now.items() if before.get(u, {}).get("lastmod") != v.get("lastmod")]
    urls = [u for u in urls if u.startswith(f"https://{HOST}/")]
    print(f"{len(urls)} addresses")
    if not urls or args.dry_run:
        print("\n".join(urls[:20]))
        return
    k = key()
    for i in range(0, len(urls), 9000):
        r = requests.post(ENDPOINT, json={"host": HOST, "key": k, "keyLocation": f"https://{HOST}/{k}.txt", "urlList": urls[i:i + 9000]}, timeout=60)
        print("IndexNow answered", r.status_code, r.text[:200])


if __name__ == "__main__":
    main()
