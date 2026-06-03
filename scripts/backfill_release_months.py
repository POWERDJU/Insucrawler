from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.db.repository import backfill_unknown_release_months


def main() -> None:
    init_db(engine)
    with SessionLocal() as db:
        updated = backfill_unknown_release_months(db)
        db.commit()
    print({"updated_products": updated})


if __name__ == "__main__":
    main()
