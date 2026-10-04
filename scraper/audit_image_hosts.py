"""Which image hosts have no verified resize rule, and how heavy are their photos? (2026-10-04)

Counts every product and house image the site shows, drops the hosts image_sizes.sized() already resizes, then
measures a few real images per remaining host (bytes and pixel width) and tests whether the host honours a
width in the URL (?w= / ?width= / ?imwidth= / ?resize=, Webflow -p-500, Wix fit). A form that returns a smaller
image on every sample is a candidate for a new rule in image_sizes.py (and the same rule in frontend/search.js).

    python3 audit_image_hosts.py            # hosts with 40+ images
    python3 audit_image_hosts.py --min 15   # include smaller hosts
Read-only: nothing is written; it makes a few hundred requests to makers' image servers.
"""
import argparse
import collections
import io
import json
import random
import re
import sqlite3
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import image_sizes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
H = {"User-Agent": "Mozilla/5.0"}


def fetch(url):
    try:
        r = requests.get(url, headers=H, timeout=20, stream=True)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
            return None
        body = r.raw.read(9_000_000, decode_content=False)
        r.close()
        try:
            width = Image.open(io.BytesIO(body)).size[0]
        except Exception:
            width = None
        return len(body), width
    except Exception:
        return None


def _q(url, **kw):
    p = urlparse(url)
    d = dict(parse_qsl(p.query))
    d.update(kw)
    return urlunparse(p._replace(query=urlencode(d)))


def candidate_urls(url):
    out = {"?width=500": _q(url, width=500), "?w=500": _q(url, w=500), "?imwidth=500": _q(url, imwidth=500),
           "?resize=500": _q(url, resize="500,500")}
    m = re.match(r"(.*)\.(jpe?g|png|webp)$", urlparse(url).path)
    if "website-files.com" in url and m:
        out["-p-500"] = urlunparse(urlparse(url)._replace(path=m.group(1) + "-p-500." + m.group(2)))
    return out


def probe(item):
    host, urls = item
    rows = []
    for u in urls:
        base = fetch(u)
        if not base:
            continue
        works = {}
        for name, v in candidate_urls(u).items():
            r = fetch(v)
            if r and r[0] < base[0] * 0.7 and (r[1] is None or base[1] is None or r[1] < base[1] * 0.9):
                works[name] = r[0] // 1024
        rows.append((base[0] // 1024, base[1], works))
    return host, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=40)
    args = ap.parse_args()
    conn = sqlite3.connect(ROOT / "data" / "formground.db")
    urls = [u for (u,) in conn.execute("SELECT image_url FROM products WHERE image_url != '' AND link_dead = 0")]
    urls += [h["image"] for h in json.loads((ROOT / "data" / "houses.json").read_text()) if h.get("image")]
    by_host = collections.defaultdict(list)
    covered = 0
    for u in urls:
        if image_sizes.sized(u, 500) != u:
            covered += 1
        else:
            by_host[urlparse(u).netloc.lower()].append(u)
    print(f"{len(urls)} images: {covered} on hosts with a resize rule ({covered / len(urls):.0%}), "
          f"{len(urls) - covered} on {len(by_host)} hosts without one")
    random.seed(1)
    work = [(h, random.sample(u, min(3, len(u)))) for h, u in by_host.items() if len(u) >= args.min]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(probe, work))
    print(f"\n{'host':32s}{'images':>7s}{'median KB':>10s}  widths   usable resize form")
    for host, rows in sorted(results, key=lambda r: -len(by_host[r[0]]) * (statistics.median([x[0] for x in r[1]] or [0]))):
        if not rows:
            print(f"{host:32s}{len(by_host[host]):7d}  (no sample loaded)")
            continue
        ok = set.intersection(*[set(r[2]) for r in rows])
        print(f"{host:32s}{len(by_host[host]):7d}{statistics.median(r[0] for r in rows):10.0f}  "
              f"{[r[1] for r in rows]}  {sorted(ok) or '-'}")


if __name__ == "__main__":
    main()
