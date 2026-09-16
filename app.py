import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEVELS = ["A1", "A2", "B1", "B2"]


def _load(name):
    with open(os.path.join(BASE_DIR, name), encoding="utf-8") as f:
        return json.load(f)


WORDS = _load("vocabulary.json")
TEXTS = _load("texts.json")
EXERCISES = _load("exercises.json")
GRAMMAR = _load("grammar.json")


def _by_level(items, level):
    if not level:
        return items
    return [i for i in items if i.get("level") == level]


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        level = query.get("level", [None])[0]

        if path in ("/", "/index.html"):
            with open(os.path.join(BASE_DIR, "index.html"), encoding="utf-8") as f:
                self._send_html(f.read())
        elif path == "/levels":
            self._send_json(200, LEVELS)
        elif path == "/words":
            q = (query.get("q", [""])[0]).lower()
            results = _by_level(WORDS, level)
            if q:
                results = [
                    w for w in results
                    if q in w["polish"].lower()
                    or q in w["english"].lower()
                    or q in w["spanish"].lower()
                ]
            self._send_json(200, results)
        elif path == "/texts":
            self._send_json(200, _by_level(TEXTS, level))
        elif path == "/exercises":
            self._send_json(200, _by_level(EXERCISES, level))
        elif path == "/grammar":
            self._send_json(200, _by_level(GRAMMAR, level))
        else:
            parts = [p for p in path.split("/") if p]
            if len(parts) == 2 and parts[0] == "words":
                for w in WORDS:
                    if str(w["id"]) == parts[1]:
                        self._send_json(200, w)
                        return
            self._send_json(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving Polish Vocabulary API on port {port}")
    server.serve_forever()
