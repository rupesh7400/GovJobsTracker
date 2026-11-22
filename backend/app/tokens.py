"""Stateless user tokens: base64url(user_id).HMAC-SHA256. No passwords; each install is one anonymous user."""
import base64, hashlib, hmac, uuid
from .config import settings

def _sig(payload: str) -> str:
    if not settings.token_secret:
        raise RuntimeError("TOKEN_SECRET is not set")
    return hmac.new(settings.token_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:40]

def make_token(user_id: uuid.UUID) -> str:
    p = base64.urlsafe_b64encode(str(user_id).encode()).decode().rstrip("=")
    return f"{p}.{_sig(p)}"

def parse_token(tok: str):
    try:
        p, s = tok.split(".", 1)
        if not hmac.compare_digest(s, _sig(p)):
            return None
        return uuid.UUID(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)).decode())
    except Exception:
        return None
