from __future__ import annotations

import os

import httpx


class ArticleFetcher:
    def __init__(self, enabled: bool | None = None) -> None:
        env_enabled = os.getenv("ENABLE_ARTICLE_BODY_FETCH", "false").lower() == "true"
        self.enabled = env_enabled if enabled is None else enabled

    def fetch(self, url: str) -> str | None:
        if not self.enabled:
            return None
        response = httpx.get(url, timeout=20)
        response.raise_for_status()
        return response.text
