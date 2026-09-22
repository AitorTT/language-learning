import datetime
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LANGS_DIR = os.path.join(BASE_DIR, "languages")
LEVELS = ["A1", "A2", "B1", "B2"]
SECTIONS = ["vocabulary", "texts", "exercises", "grammar"]
DEFAULT_LANG = "en"

NOTES_FILE = os.path.join(BASE_DIR, "notes.json")
WRITE_PASSWORD = os.environ.get("WRITE_PASSWORD", "")
REDIS_URL = os.environ.get("UPSTASH_REDIS_URL", "")
NOTES_KEY = "pv:notes"

try:
    import redis
except ImportError:
    redis = None

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None and REDIS_URL and redis is not None:
        url = REDIS_URL
        if url.startswith("redis://"):
            url = "rediss://" + url[len("redis://"):]
        _redis_client = redis.from_url(url, decode_responses=True, socket_timeout=15)
    return _redis_client


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Language registry
LANGUAGES = _load_json(os.path.join(BASE_DIR, "languages.json"))
LANG_BY_CODE = {lang["code"]: lang for lang in LANGUAGES}


def _load_pack(code):
    pack = {}
    for section in SECTIONS:
        path = os.path.join(LANGS_DIR, code, section + ".json")
        pack[section] = _load_json(path) if os.path.exists(path) else []
    return pack


PACKS = {lang["code"]: _load_pack(lang["code"]) for lang in LANGUAGES}

COMPARE_WORDS = [
    "hello", "goodbye", "good morning", "good night", "thank you",
    "please", "sorry", "yes", "no", "help",
]

_compare_cache = None


def _english_alternatives(value):
    text = str(value).strip().lower().rstrip("?").strip()
    return [p.strip() for p in text.split("/") if p.strip()]


def _build_compare():
    global _compare_cache
    if _compare_cache is not None:
        return _compare_cache
    languages = [
        {
            "code": lang["code"],
            "name": lang["name"],
            "flag": lang.get("flag", ""),
            "speech": lang.get("speech", ""),
            "termLabel": lang.get("termLabel", ""),
        }
        for lang in LANGUAGES
    ]
    words = []
    for concept in COMPARE_WORDS:
        terms = {}
        for lang in LANGUAGES:
            code = lang["code"]
            field = lang["termField"]
            for entry in PACKS[code].get("vocabulary", []):
                if concept in _english_alternatives(entry.get("english", "")):
                    terms[code] = entry.get(field, "")
                    break
        words.append({"concept": concept, "terms": terms})
    _compare_cache = {"languages": languages, "words": words}
    return _compare_cache


def _load_notes():
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(NOTES_KEY)
            return json.loads(raw) if raw else []
        except Exception:
            return []
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return []
    return []


def _save_notes(notes):
    client = _get_redis()
    if client is not None:
        client.set(NOTES_KEY, json.dumps(notes, ensure_ascii=False))
        return
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


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

    def _authorized(self):
        return bool(WRITE_PASSWORD) and self.headers.get("X-Password") == WRITE_PASSWORD

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw) if raw else {}
        except ValueError:
            return None

    def _serve_section(self, code, section, query):
        if code not in PACKS or section not in SECTIONS:
            self._send_json(404, {"error": "not found"})
            return
        items = _by_level(PACKS[code][section], query.get("level", [None])[0])
        if section == "vocabulary":
            q = (query.get("q", [""])[0]).lower()
            if q:
                cfg = LANG_BY_CODE[code]
                fields = [cfg["termField"]] + [t["field"] for t in cfg["targets"]]
                items = [
                    w for w in items
                    if any(q in str(w.get(f, "")).lower() for f in fields)
                ]
        self._send_json(200, items)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            with open(os.path.join(BASE_DIR, "index.html"), encoding="utf-8") as f:
                self._send_html(f.read())
        elif path == "/languages":
            self._send_json(200, LANGUAGES)
        elif path == "/levels":
            self._send_json(200, LEVELS)
        elif path == "/compare":
            self._send_json(200, _build_compare())
        elif path == "/notes":
            if not WRITE_PASSWORD:
                self._send_json(503, {"error": "saving is not configured"})
            elif not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
            else:
                self._send_json(200, list(reversed(_load_notes())))
        else:
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 3 and parts[0] == "api":
                code, section = parts[1], parts[2]
                if len(parts) == 4 and section == "vocabulary" and code in PACKS:
                    for w in PACKS[code]["vocabulary"]:
                        if str(w["id"]) == parts[3]:
                            self._send_json(200, w)
                            return
                    self._send_json(404, {"error": "not found"})
                else:
                    self._serve_section(code, section, query)
            elif path in ("/words", "/texts", "/exercises", "/grammar"):
                section = {"words": "vocabulary", "texts": "texts",
                           "exercises": "exercises", "grammar": "grammar"}[parts[0]]
                self._serve_section(DEFAULT_LANG, section, query)
            else:
                self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/notes":
            self._send_json(404, {"error": "not found"})
            return
        if not WRITE_PASSWORD:
            self._send_json(503, {"error": "saving is not configured"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        data = self._read_body()
        if data is None:
            self._send_json(400, {"error": "invalid json"})
            return
        content = (data.get("content") or "").strip()
        if not content:
            self._send_json(400, {"error": "content is required"})
            return
        title = (data.get("title") or "").strip() or "Untitled"
        notes = _load_notes()
        note = {
            "id": str(int(time.time() * 1000)),
            "title": title,
            "content": content,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        }
        notes.append(note)
        _save_notes(notes)
        self._send_json(201, note)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        if not (len(parts) == 2 and parts[0] == "notes"):
            self._send_json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        notes = _load_notes()
        remaining = [n for n in notes if str(n["id"]) != parts[1]]
        _save_notes(remaining)
        self._send_json(200, {"deleted": len(notes) - len(remaining)})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving Polish Vocabulary API on port {port}")
    server.serve_forever()
