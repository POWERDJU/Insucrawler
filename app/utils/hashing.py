from __future__ import annotations

import hashlib


def sha256_text(value: str | None) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def article_dedup_hash(url: str | None, title: str | None = None, description: str | None = None) -> str:
    basis = (url or "").strip() or f"{title or ''}\n{description or ''}"
    return sha256_text(basis)
