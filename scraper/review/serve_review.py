"""Local review page for the chair family: serves review/chair_review.html and saves each answer to data/category_review_chairs.json.

    python3 scraper/review/serve_review.py        # then open http://localhost:8094/
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).parent
SAVE = HERE.parent.parent / "data" / "category_review_chairs.json"


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/items.json"):
            self._send((HERE / "chairs_items.json").read_bytes())
        elif self.path.startswith("/decisions.json"):
            self._send(SAVE.read_bytes() if SAVE.exists() else b"{}")
        else:
            self._send((HERE / "chair_review.html").read_bytes(), "text/html")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        SAVE.write_text(json.dumps(json.loads(body), ensure_ascii=False, indent=1))
        self._send('{"ok":true}')

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("review page on http://localhost:8094/")
    HTTPServer(("127.0.0.1", 8094), Handler).serve_forever()
