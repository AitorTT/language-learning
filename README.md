# Language Learning

A dependency-free multi-language study app: flashcards, reading texts, drag-the-words
exercises, grammar grids and a password-protected writing area.

## Languages

Each language is a data pack under `languages/<code>/` (vocabulary, texts, exercises,
grammar) described in `languages.json`.

- Polish (pl) — English + Español
- English (en) — Español
- German (de) — English + Español
- Italian (it) — English + Español
- Portuguese (pt, Brazilian) — English + Español
- Swedish (sv) — English + Español, with IPA pronunciation

## API

- `GET /languages` — available languages and their configuration
- `GET /api/<lang>/vocabulary?level=&q=` — words
- `GET /api/<lang>/texts?level=`
- `GET /api/<lang>/exercises?level=`
- `GET /api/<lang>/grammar?level=`
- `GET /notes`, `POST /notes`, `DELETE /notes/<id>` — writing (password required)

`level` is one of `A1`, `A2`, `B1`, `B2`. The web UI is served at `/`.

## Run locally

```bash
python app.py
```

Then visit `http://localhost:8000/`.

### Environment variables

- `WRITE_PASSWORD` — enables the research/writing area
- `UPSTASH_REDIS_URL` — persists notes in Redis (falls back to a local file otherwise)

## Deploy

Hosted as a Python web service on Render (`build: pip install -r requirements.txt`,
`start: python app.py`).
