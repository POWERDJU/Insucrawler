from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.exclusive_right_service import ExclusiveRightService


def main() -> None:
    parser = argparse.ArgumentParser(description="List exclusive-use-right extraction queue status.")
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    args = parser.parse_args()
    with SessionLocal() as db:
        status = ExclusiveRightService().queue_status(db, date_from=args.date_from, date_to=args.date_to)
    print(json.dumps(status, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

