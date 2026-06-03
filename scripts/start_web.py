from __future__ import annotations

import gzip
import os
import shutil
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import DATABASE_URL, SessionLocal, engine
from app.db.migrations import init_db
from app.db.seed_master_data import seed_all


def _sqlite_db_path() -> Path | None:
    if not DATABASE_URL.startswith("sqlite:///"):
        return None
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    if db_path == ":memory:":
        return None
    path = Path(db_path)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _ensure_bundled_seed_db() -> None:
    if os.getenv("USE_BUNDLED_DB_SEED", "true").lower() in {"0", "false", "no"}:
        return

    target = _sqlite_db_path()
    if target is None:
        return
    if target.exists() and target.stat().st_size > 4096:
        return

    seed_db = ROOT / "deploy" / "insurance_news_seed.db"
    seed_gz = ROOT / "deploy" / "insurance_news_seed.db.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_target = target.with_suffix(target.suffix + ".tmp")

    if seed_db.exists():
        shutil.copy2(seed_db, tmp_target)
    elif seed_gz.exists():
        with gzip.open(seed_gz, "rb") as src, tmp_target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    else:
        return

    tmp_target.replace(target)


def main() -> None:
    _ensure_bundled_seed_db()
    init_db(engine)
    with SessionLocal() as db:
        seed_all(db)

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.api.main:app", host=host, port=port, proxy_headers=True)


if __name__ == "__main__":
    main()
