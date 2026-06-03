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

To refresh the deployed read-only/demo data from your local DB:

```powershell
@'
from pathlib import Path
import gzip
import shutil
import sqlite3

src = Path("data/insurance_news.db")
snapshot = Path("deploy/insurance_news_seed.db")
compressed = Path("deploy/insurance_news_seed.db.gz")
snapshot.parent.mkdir(exist_ok=True)
if snapshot.exists():
    snapshot.unlink()
with sqlite3.connect(src) as conn:
    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    conn.execute(f"VACUUM INTO '{snapshot.as_posix()}'")
if compressed.exists():
    compressed.unlink()
with snapshot.open("rb") as f_in, gzip.GzipFile(
    filename=str(compressed),
    mode="wb",
    compresslevel=9,
    mtime=0,
) as f_out:
    shutil.copyfileobj(f_in, f_out)
snapshot.unlink()
'@ | py -3 -

git add deploy/insurance_news_seed.db.gz
git commit -m "Refresh bundled DB seed"
git push
```

This keeps the large runtime SQLite files out of Git while letting the deployed
web app show the latest locally prepared data.

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

The default Blueprint uses Render's free web service plan and no persistent
disk. On boot, the app restores `deploy/insurance_news_seed.db.gz` to
`data/insurance_news.db` if the DB is not already present. This is best for
read-only demos where the DB is refreshed locally and pushed to GitHub.

If you want data created on Render itself to persist across restarts, switch the
service to a paid plan and add a persistent disk mounted at `/app/data`.

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
