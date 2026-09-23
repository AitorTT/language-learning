"""Export the language-study data to portable formats.

Produces, under --out (default: ./export):
  json/<code>.json      one merged bundle per language (registry + all sections)
  json/all.json         every language in one file
  csv/<code>_*.csv      one CSV per language and section
  language-study.db     SQLite database with a table per section
  language-study-export.zip   everything above, zipped

Usage:
  python export.py                 # all formats
  python export.py --format json   # json | csv | sqlite | all
  python export.py --out dist
  python export.py --lang de --lang fr
"""

import argparse
import csv
import datetime
import json
import os
import sqlite3
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LANGS_DIR = os.path.join(BASE_DIR, "languages")
SECTIONS = ["vocabulary", "texts", "exercises", "grammar"]
PRON_KEYS = ["ipa", "pinyin", "romaji", "translit"]
VOCAB_COLUMNS = ["id", "term"] + PRON_KEYS + ["english", "spanish", "category", "level"]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_languages():
    return load_json(os.path.join(BASE_DIR, "languages.json"))


def load_pack(code):
    pack = {}
    for section in SECTIONS:
        path = os.path.join(LANGS_DIR, code, section + ".json")
        pack[section] = load_json(path) if os.path.exists(path) else []
    return pack


def bundle(cfg, pack):
    out = {
        "code": cfg["code"],
        "name": cfg["name"],
        "flag": cfg.get("flag", ""),
        "speech": cfg.get("speech", ""),
        "termLabel": cfg.get("termLabel", ""),
        "termField": cfg["termField"],
        "targets": cfg.get("targets", []),
        "sections": cfg.get("sections", SECTIONS),
    }
    for key in ("script", "default", "ipa", "pinyin", "romaji", "translit"):
        if key in cfg:
            out[key] = cfg[key]
    out.update(pack)
    return out


def vocab_row(cfg, w):
    row = {"id": w["id"], "term": w.get(cfg["termField"], "")}
    for key in PRON_KEYS:
        row[key] = w.get(key, "")
    row["english"] = w.get("english", "")
    row["spanish"] = w.get("spanish", "")
    row["category"] = w.get("category", "")
    row["level"] = w.get("level", "")
    return row


def write_json(out_dir, bundles):
    json_dir = os.path.join(out_dir, "json")
    os.makedirs(json_dir, exist_ok=True)
    for code, data in bundles.items():
        with open(os.path.join(json_dir, code + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    all_path = os.path.join(json_dir, "all.json")
    with open(all_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "count": len(bundles),
            "languages": bundles,
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return json_dir


def write_csvs(out_dir, bundles, configs):
    csv_dir = os.path.join(out_dir, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    for code, data in bundles.items():
        cfg = configs[code]
        with open(os.path.join(csv_dir, code + "_vocabulary.csv"), "w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=VOCAB_COLUMNS)
            wr.writeheader()
            for w in data["vocabulary"]:
                wr.writerow(vocab_row(cfg, w))
        with open(os.path.join(csv_dir, code + "_texts.csv"), "w", encoding="utf-8", newline="") as f:
            cols = ["id", "level", "title", "body", "translation_en", "translation_es"]
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            for t in data["texts"]:
                wr.writerow({c: t.get(c, "") for c in cols})
        with open(os.path.join(csv_dir, code + "_exercises.csv"), "w", encoding="utf-8", newline="") as f:
            cols = ["exercise_id", "level", "instruction", "item", "sentence", "answer",
                    "translation_en", "translation_es"]
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            for e in data["exercises"]:
                for i, it in enumerate(e.get("items", [])):
                    row = {"exercise_id": e["id"], "level": e.get("level", ""),
                           "instruction": e.get("instruction", ""), "item": i}
                    row.update({c: it.get(c, "") for c in
                                ("sentence", "answer", "translation_en", "translation_es")})
                    wr.writerow(row)
        with open(os.path.join(csv_dir, code + "_grammar.csv"), "w", encoding="utf-8", newline="") as f:
            cols = ["id", "level", "title", "description", "columns", "rows"]
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            for g in data["grammar"]:
                wr.writerow({
                    "id": g["id"], "level": g.get("level", ""), "title": g.get("title", ""),
                    "description": g.get("description", ""),
                    "columns": " | ".join(g.get("columns", [])),
                    "rows": " ;; ".join(" | ".join(r) for r in g.get("rows", [])),
                })
    return csv_dir


def write_sqlite(out_dir, bundles, configs):
    path = os.path.join(out_dir, "language-study.db")
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE languages (
            code TEXT PRIMARY KEY, name TEXT, flag TEXT, speech TEXT,
            term_label TEXT, term_field TEXT, targets TEXT, sections TEXT, script TEXT
        );
        CREATE TABLE vocabulary (
            lang TEXT, id INTEGER, term TEXT, ipa TEXT, pinyin TEXT, romaji TEXT,
            translit TEXT, english TEXT, spanish TEXT, category TEXT, level TEXT,
            PRIMARY KEY (lang, id)
        );
        CREATE TABLE texts (
            lang TEXT, id INTEGER, level TEXT, title TEXT, body TEXT,
            translation_en TEXT, translation_es TEXT, PRIMARY KEY (lang, id)
        );
        CREATE TABLE exercises (
            lang TEXT, id INTEGER, level TEXT, instruction TEXT, PRIMARY KEY (lang, id)
        );
        CREATE TABLE exercise_items (
            lang TEXT, exercise_id INTEGER, position INTEGER, sentence TEXT, answer TEXT,
            translation_en TEXT, translation_es TEXT, PRIMARY KEY (lang, exercise_id, position)
        );
        CREATE TABLE grammar (
            lang TEXT, id INTEGER, level TEXT, title TEXT, description TEXT, columns TEXT,
            PRIMARY KEY (lang, id)
        );
        CREATE TABLE grammar_rows (
            lang TEXT, grammar_id INTEGER, position INTEGER, cells TEXT,
            PRIMARY KEY (lang, grammar_id, position)
        );
        CREATE INDEX idx_vocab_english ON vocabulary (english);
        CREATE INDEX idx_vocab_level ON vocabulary (lang, level);
        CREATE INDEX idx_vocab_category ON vocabulary (lang, category);
    """)
    for code, data in bundles.items():
        cfg = configs[code]
        cur.execute("INSERT INTO languages VALUES (?,?,?,?,?,?,?,?,?)", (
            code, cfg.get("name", ""), cfg.get("flag", ""), cfg.get("speech", ""),
            cfg.get("termLabel", ""), cfg["termField"],
            json.dumps(cfg.get("targets", []), ensure_ascii=False),
            json.dumps(cfg.get("sections", SECTIONS), ensure_ascii=False),
            cfg.get("script", ""),
        ))
        cur.executemany(
            "INSERT INTO vocabulary VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(code, w["id"], w.get(cfg["termField"], ""), w.get("ipa", ""), w.get("pinyin", ""),
              w.get("romaji", ""), w.get("translit", ""), w.get("english", ""),
              w.get("spanish", ""), w.get("category", ""), w.get("level", ""))
             for w in data["vocabulary"]])
        cur.executemany(
            "INSERT INTO texts VALUES (?,?,?,?,?,?,?)",
            [(code, t["id"], t.get("level", ""), t.get("title", ""), t.get("body", ""),
              t.get("translation_en", ""), t.get("translation_es", "")) for t in data["texts"]])
        cur.executemany(
            "INSERT INTO exercises VALUES (?,?,?,?)",
            [(code, e["id"], e.get("level", ""), e.get("instruction", "")) for e in data["exercises"]])
        items = []
        for e in data["exercises"]:
            for i, it in enumerate(e.get("items", [])):
                items.append((code, e["id"], i, it.get("sentence", ""), it.get("answer", ""),
                              it.get("translation_en", ""), it.get("translation_es", "")))
        cur.executemany("INSERT INTO exercise_items VALUES (?,?,?,?,?,?,?)", items)
        cur.executemany(
            "INSERT INTO grammar VALUES (?,?,?,?,?,?)",
            [(code, g["id"], g.get("level", ""), g.get("title", ""), g.get("description", ""),
              json.dumps(g.get("columns", []), ensure_ascii=False)) for g in data["grammar"]])
        rows = []
        for g in data["grammar"]:
            for i, r in enumerate(g.get("rows", [])):
                rows.append((code, g["id"], i, json.dumps(r, ensure_ascii=False)))
        cur.executemany("INSERT INTO grammar_rows VALUES (?,?,?,?)", rows)
    con.commit()
    con.close()
    return path


def write_zip(out_dir, files):
    path = os.path.join(out_dir, "language-study-export.zip")
    if os.path.exists(path):
        os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, os.path.relpath(f, out_dir))
    return path


def main():
    ap = argparse.ArgumentParser(description="Export language-study data.")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "export"))
    ap.add_argument("--format", choices=["all", "json", "csv", "sqlite"], default="all")
    ap.add_argument("--lang", action="append", dest="langs", help="limit to a language code (repeatable)")
    args = ap.parse_args()

    languages = load_languages()
    if args.langs:
        wanted = set(args.langs)
        languages = [l for l in languages if l["code"] in wanted]
        missing = wanted - {l["code"] for l in languages}
        if missing:
            raise SystemExit("unknown language code(s): " + ", ".join(sorted(missing)))

    configs = {l["code"]: l for l in languages}
    bundles = {l["code"]: bundle(l, load_pack(l["code"])) for l in languages}
    os.makedirs(args.out, exist_ok=True)

    produced = []
    if args.format in ("all", "json"):
        produced.append(write_json(args.out, bundles))
    if args.format in ("all", "csv"):
        produced.append(write_csvs(args.out, bundles, configs))
    if args.format in ("all", "sqlite"):
        produced.append(write_sqlite(args.out, bundles, configs))
    if args.format == "all":
        files = []
        for root, _, names in os.walk(args.out):
            for n in names:
                if n != "language-study-export.zip":
                    files.append(os.path.join(root, n))
        produced.append(write_zip(args.out, files))

    total = sum(len(b["vocabulary"]) for b in bundles.values())
    print("languages:", len(bundles), "| vocabulary rows:", total)
    for p in produced:
        print("wrote", os.path.relpath(p, BASE_DIR))


if __name__ == "__main__":
    main()
