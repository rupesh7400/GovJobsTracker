import hmac, uuid
from fastapi import Header, HTTPException
from .config import settings
from .tokens import make_token, parse_token

def current_user(authorization: str = Header(default="")) -> uuid.UUID:
    uid = parse_token(authorization.removeprefix("Bearer ").strip()) if authorization else None
    if not uid:
        raise HTTPException(401, "Missing or invalid token")
    return uid

def admin(x_admin_key: str = Header(default="")):
    if not settings.admin_api_key or not hmac.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(401, "Invalid admin key")
