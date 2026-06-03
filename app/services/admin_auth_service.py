from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from app.utils.dates import utcnow


_SESSIONS: dict[str, datetime] = {}


class AdminAuthService:
    def _password_configured(self) -> bool:
        return bool(os.getenv("ADMIN_BATCH_PASSWORD") or os.getenv("ADMIN_BATCH_PASSWORD_HASH"))

    def verify_password(self, password: str) -> bool:
        configured_hash = os.getenv("ADMIN_BATCH_PASSWORD_HASH")
        if configured_hash:
            digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
            return hmac.compare_digest(digest, configured_hash)
        configured_password = os.getenv("ADMIN_BATCH_PASSWORD")
        if not configured_password:
            return False
        return hmac.compare_digest(password, configured_password)

    def create_token(self, password: str) -> dict[str, str | bool]:
        if not self._password_configured() or not self.verify_password(password):
            return {"ok": False}
        ttl_minutes = int(os.getenv("ADMIN_SESSION_TTL_MINUTES", "30"))
        token = secrets.token_urlsafe(32)
        expires_at = utcnow() + timedelta(minutes=ttl_minutes)
        _SESSIONS[token] = expires_at
        return {"ok": True, "token": token, "expires_at": expires_at.isoformat()}

    def validate_token(self, token: str) -> bool:
        expires_at = _SESSIONS.get(token)
        if not expires_at:
            return False
        if expires_at < utcnow():
            _SESSIONS.pop(token, None)
            return False
        return True


def clear_admin_sessions() -> None:
    _SESSIONS.clear()
