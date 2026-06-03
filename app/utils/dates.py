from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def current_year_month(dt: datetime | None = None) -> str:
    value = dt or utcnow()
    return value.strftime("%Y-%m")
