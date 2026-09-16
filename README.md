# Polish Vocabulary API

A tiny dependency-free REST API serving Polish vocabulary with English and Spanish translations.

## Endpoints

- `GET /` — API info and endpoint list
- `GET /words` — all words
- `GET /words?q=<search>` — filter by Polish, English, or Spanish
- `GET /words/<id>` — a single word by id

## Run locally

```bash
python app.py
```

Then visit `http://localhost:8000/words`.

## Deploy

This repo includes a Render Blueprint (`render.yaml`). Connect it to Render and it deploys as a free Python web service.
