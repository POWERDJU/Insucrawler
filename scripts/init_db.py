from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.db.seed_master_data import seed_all


def main() -> None:
    init_db(engine)
    with SessionLocal() as db:
        result = seed_all(db)
    print({"status": "ok", "seeded": result})


if __name__ == "__main__":
    main()
