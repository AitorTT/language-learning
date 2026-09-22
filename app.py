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

# Broad IPA for the languages whose vocabulary packs carry no pronunciation field.
COMPARE_PRON = {
    "pl": {"hello": "t͡ʂɛɕt͡ɕ", "goodbye": "dɔ viˈd͡zɛɲa", "good morning": "d͡ʑɛɲ ˈdɔbrɨ",
           "good night": "dɔˈbranɔt͡s", "thank you": "d͡ʑɛŋˈkujɛ", "please": "ˈprɔʂɛ",
           "sorry": "pʂɛˈpraʂam", "yes": "tak", "no": "ɲɛ", "help": "ˈpɔmɔt͡s"},
    "en": {"hello": "həˈləʊ", "goodbye": "ɡʊdˈbaɪ", "good morning": "ɡʊd ˈmɔːnɪŋ",
           "good night": "ɡʊd naɪt", "thank you": "ˈθæŋk juː", "please": "pliːz",
           "sorry": "ˈsɒri", "yes": "jɛs", "no": "nəʊ", "help": "hɛlp"},
    "de": {"hello": "ˈhaloː", "goodbye": "aʊf ˈviːdɐzeːən", "good morning": "ˈɡuːtn̩ ˈmɔʁɡn̩",
           "good night": "ˈɡuːtə naxt", "thank you": "ˈdaŋkə", "please": "ˈbɪtə",
           "sorry": "ɛntˈʃʊldɪɡʊŋ", "yes": "jaː", "no": "naɪn", "help": "diː ˈhɪlfə"},
    "it": {"hello": "ˈtʃaːo", "goodbye": "arriveˈdertʃi", "good morning": "bwɔnˈdʒorno",
           "good night": "bwɔnaˈnɔtte", "thank you": "ˈɡrattsje", "please": "ˈprɛːɡo",
           "sorry": "ˈskuːza", "yes": "si", "no": "nɔ", "help": "laˈjuːto"},
    "pt": {"hello": "oˈla", "goodbye": "ˈtʃaw", "good morning": "bõ ˈdʒiɐ",
           "good night": "ˈboɐ ˈnojti", "thank you": "obɾiˈɡadu", "please": "poʁ faˈvoʁ",
           "sorry": "desˈkuwpi", "yes": "sĩ", "no": "nɐ̃w̃", "help": "a aˈʒudɐ"},
    "eu": {"hello": "ˈkai̯ʃo", "goodbye": "aɡur", "good morning": "eɡun on",
           "good night": "ɡau̯ on", "thank you": "es̺kerik as̺ko", "please": "mes̺edes̻",
           "sorry": "barkatu", "yes": "bai̯", "no": "es̻", "help": "laɡunt͡s̻a"},
    "fr": {"hello": "bɔ̃ˈʒuʁ", "goodbye": "o ʁəˈvwaʁ", "good morning": "bɔ̃ˈʒuʁ",
           "good night": "bɔn nɥi", "thank you": "mɛʁˈsi", "please": "sil vu plɛ",
           "sorry": "dezoˈle", "yes": "wi", "no": "nɔ̃", "help": "ɛd"},
    "tr": {"hello": "meɾhaˈba", "goodbye": "ˈhoʃtʃa kal", "good morning": "ɡynajˈdɯn",
           "good night": "iji ɟedʒeˈleɾ", "thank you": "teʃecˈcyɾ edeˈɾim", "please": "ˈlytfen",
           "sorry": "øˈzyɾ edeˈɾim", "yes": "eˈvet", "no": "haˈjɯɾ", "help": "jaɾˈdɯm"},
    "uk": {"hello": "prɪˈʋit", "goodbye": "dɔ pɔˈbat͡ʃenʲːɐ", "good morning": "ˈdɔbrɔɦɔ ˈrankʊ",
           "good night": "na dɔˈbranʲit͡ʃ", "thank you": "ˈdʲakujʊ", "please": "budʲ ˈlaskɐ",
           "sorry": "ˈʋɪbat͡ʃte", "yes": "tak", "no": "nʲi", "help": "dɔpɔˈmɔɦɐ"},
    "nl": {"hello": "ɦɑˈloː", "goodbye": "tɔt ˈzins", "good morning": "ˌɣudəˈmɔrɣə(n)",
           "good night": "ˌɣudəˈnɑxt", "thank you": "ˈdɑŋk jə", "please": "ˌɑlsjəˈblift",
           "sorry": "ˈsɔri", "yes": "jaː", "no": "neː", "help": "ɦʏlp"},
    "ro": {"hello": "ˈbu.nə", "goodbye": "la re.veˈde.re", "good morning": "ˈbu.nə di.miˈne̯a.t͡sa",
           "good night": "ˈno̯ap.te ˈbu.nə", "thank you": "mul.t͡suˈmesk", "please": "te roɡ",
           "sorry": "ɨmʲ ˈpa.re rəw", "yes": "da", "no": "nu", "help": "a.ʒuˈtor"},
    "lt": {"hello": "ˈlaːbɐs", "goodbye": "ˈvʲɪso ˈɡʲɛːro", "good morning": "ˈlaːbɐs ˈriːtɐs",
           "good night": "lɐbɐˈnakt", "thank you": "ɐˈt͡ʃʲuː", "please": "prɐˈʃɐʊ",
           "sorry": "ɐt͡sʲɪprɐˈʃɐʊ", "yes": "tɐɪp", "no": "nʲɛ", "help": "pɐˈɡɐlbɐ"},
    "fi": {"hello": "hei", "goodbye": "ˈnækemiːn", "good morning": "ˈhyʋæː ˈhuo̯mentɑ",
           "good night": "ˈhyʋæː ˈyø̯tæ", "thank you": "ˈkiːtos", "please": "ˈole ˈhyʋæ",
           "sorry": "ˈɑnteːksi", "yes": "ˈkylːæ", "no": "ei", "help": "ˈɑpu"},
    "da": {"hello": "hɑj", "goodbye": "fɑˈvɛl", "good morning": "ɡoˈmɔːɐn",
           "good night": "ɡoˈnat", "thank you": "tɑk", "please": "væɐ̯sˈɡoː",
           "sorry": "ˈɔnskyld", "yes": "ja", "no": "nɑj", "help": "jɛlp"},
    "et": {"hello": "ˈtere", "goodbye": "ˈheɑ̯d ˈɑe̯ɡ̊ɑ", "good morning": "ˈtere ˈhomːikust",
           "good night": "ˈheɑ̯d ˈøːd̥", "thank you": "ˈɑi̯tæh", "please": "ˈpɑlun",
           "sorry": "ˈvɑb̥ɑnd̥ust", "yes": "jɑh", "no": "ei̯", "help": "ˈɑbi"},
}

_compare_cache = None


def _english_alternatives(value):
    text = str(value).strip().lower().rstrip("?").strip()
    return [p.strip() for p in text.split("/") if p.strip()]


def _pronunciation(code, concept, entry):
    if not entry:
        return "", ""
    for key in ("ipa", "pinyin", "romaji", "translit"):
        if entry.get(key):
            return entry[key], key
    return COMPARE_PRON.get(code, {}).get(concept, ""), "ipa"


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
            "hasIpa": bool(lang.get("ipa")),
        }
        for lang in LANGUAGES
    ]
    words = []
    for concept in COMPARE_WORDS:
        terms = {}
        for lang in LANGUAGES:
            code = lang["code"]
            field = lang["termField"]
            entry = next((e for e in PACKS[code].get("vocabulary", [])
                          if concept in _english_alternatives(e.get("english", ""))), None)
            pron, kind = _pronunciation(code, concept, entry)
            terms[code] = {
                "term": entry.get(field, "") if entry else "",
                "pron": pron,
                "kind": kind,
            }
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
