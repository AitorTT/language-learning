import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "vocabulary.json"), encoding="utf-8") as f:
    WORDS = json.load(f)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self._send(200, {
                "name": "Polish Vocabulary API",
                "total_words": len(WORDS),
                "endpoints": [
                    "GET /words",
                    "GET /words?q=<search>",
                    "GET /words/<id>",
                ],
            })
        elif path == "/words":
            q = (query.get("q", [""])[0]).lower()
            if q:
                results = [
                    w for w in WORDS
                    if q in w["polish"].lower()
                    or q in w["english"].lower()
                    or q in w["spanish"].lower()
                ]
            else:
                results = WORDS
            self._send(200, results)
        else:
            parts = [p for p in path.split("/") if p]
            if len(parts) == 2 and parts[0] == "words":
                for w in WORDS:
                    if str(w["id"]) == parts[1]:
                        self._send(200, w)
                        return
            self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving Polish Vocabulary API on port {port}")
    server.serve_forever()
