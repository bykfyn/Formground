"""Local review page for the chair family: serves review/chair_review.html and saves each answer to data/category_review_chairs.json.

    python3 scraper/review/serve_review.py        # then open http://localhost:8094/
"""
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent.parent / "data"
FAMILIES = {"chairs": ("chairs_items.json", "category_review_chairs.json"), "tables": ("tables_items.json", "category_review_tables.json"),
            "lighting": ("lighting_items.json", "category_review_lighting.json"), "sofas": ("sofas_items.json", "category_review_sofas.json"),
            "objects": ("objects_items.json", "category_review_objects.json"),
            "storage": ("storage_items.json", "category_review_storage.json")}


def family_of(path):
    m = re.search(r"family=(\w+)", path)
    return m.group(1) if m and m.group(1) in FAMILIES else "chairs"


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        fam = family_of(self.path)
        save = DATA / FAMILIES[fam][1]
        if self.path.startswith("/items.json"):
            self._send((HERE / FAMILIES[fam][0]).read_bytes())
        elif self.path.startswith("/check.json"):
            self._send((HERE / "check_items.json").read_bytes())
        elif self.path.startswith("/decisions.json"):
            self._send(save.read_bytes() if save.exists() else b"{}")
        else:
            self._send((HERE / "chair_review.html").read_bytes(), "text/html")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        (DATA / FAMILIES[family_of(self.path)][1]).write_text(json.dumps(json.loads(body), ensure_ascii=False, indent=1))
        self._send('{"ok":true}')

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("review page on http://localhost:8094/  (tables: ?family=tables, lighting: ?family=lighting, sofas: ?family=sofas, objects: ?family=objects, storage: ?family=storage)")
    HTTPServer(("127.0.0.1", 8094), Handler).serve_forever()
