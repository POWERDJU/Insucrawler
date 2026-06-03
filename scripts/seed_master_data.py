from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.seed_master_data import company_display_order_summary, seed_all


def main() -> None:
    with SessionLocal() as db:
        print(seed_all(db))
        for insurance_type in ["생명보험", "손해보험"]:
            print(f"{insurance_type} 표시순서:")
            for idx, name, year in company_display_order_summary(db, insurance_type):
                print(f"{idx} {name} {year or 'unknown'}")


if __name__ == "__main__":
    main()
