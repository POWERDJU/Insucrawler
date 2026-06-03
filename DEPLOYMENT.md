# Ins-news Web App Deployment

This repository is a FastAPI web app.

## Local Run

```powershell
python scripts/start_web.py
```

Open:

```text
http://127.0.0.1:8000/
```

The start script runs DB initialization and reference-data seeding before
starting Uvicorn.

## Bundled Data Snapshot

The repository includes a compressed SQLite snapshot at:

```text
deploy/insurance_news_seed.db.gz
```

When `USE_BUNDLED_DB_SEED=true` (the default), `scripts/start_web.py` restores
that snapshot to `data/insurance_news.db` only when the target DB is missing or
empty. Existing runtime data is not overwritten.

Runtime DB files under `data/` are ignored by Git. Commit only the compressed
seed snapshot when the deployed app should start with the current article,
product, and exclusive-right data.

## Required Environment Variables

Keep secrets in the hosting provider environment settings. Do not commit `.env`.

- `ADMIN_API_TOKEN`
- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`
- `GEMINI_API_KEY`
- `QWEN_API_KEY`
- `DATABASE_URL`
- `USE_BUNDLED_DB_SEED`

Safe defaults:

- `ENABLE_ARTICLE_BODY_FETCH=false`
- `ENABLE_GEMINI_GROUNDING=false`
- `EXCLUSIVE_RIGHT_EXTRACTION_DEFAULT_MODE=enqueue_only`
- `USE_BUNDLED_DB_SEED=true`

## Render

The repo includes `render.yaml`.

1. Create a new Render Blueprint from `https://github.com/POWERDJU/Ins-news`.
2. Fill secret environment variables in Render.
3. Deploy.

The included disk mounts `/app/data` so the SQLite DB can persist. On the first
boot, the app restores `deploy/insurance_news_seed.db.gz` into that disk if the
DB is not already present.

## Docker

```bash
docker build -t ins-news .
docker run --rm -p 8000:8000 --env-file .env ins-news
```

For persistent SQLite data:

```bash
docker run --rm -p 8000:8000 --env-file .env -v ./data:/app/data ins-news
```

## Heroku/Railway-Style Procfile

`Procfile`:

```text
web: python scripts/start_web.py
```

The app uses the `PORT` environment variable automatically.
